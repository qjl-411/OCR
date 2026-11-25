import json
import logging
import mimetypes
import os
import re
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import config, db, reader, service
from .auth_api import router as auth_router, current_user
from .exporter import export
from .parser import CATEGORIES, FIELD_NAMES, money, validate

logging.basicConfig(level=logging.INFO)

# 业务接口是否强制校验登录令牌。PIAO_AUTH_REQUIRED=1 时启用；
# 测试与本地演示默认不拦截，保证既有接口测试与演示流程可用。
AUTH_REQUIRED = (os.getenv('PIAO_AUTH_REQUIRED', '0') == '1')
PUBLIC_API = ('/api/auth/', '/api/health', '/api/meta', '/docs', '/openapi.json')


@asynccontextmanager
async def lifespan(app):
    from scripts.restore_models import restore
    restore()
    db.init();db.interrupted_jobs()
    if os.getenv('INVOICE_SEED_DEMO','1')=='1':
        from .demo import seed_if_empty
        seed_if_empty()
    yield


app=FastAPI(title='票序 智能发票系统',version='2.0.0',description='本地 PDF 提取、离线 OCR 与发票复核 API',lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Content-Type','Authorization'])
app.include_router(auth_router)


@app.middleware('http')
async def headers(request,call_next):
    if request.headers.get('content-length','').isdigit() and int(request.headers['content-length'])>config.MAX_BATCH+2*1024*1024:
        return JSONResponse({'detail':'单批上传不能超过 100 MB。'},status_code=413)
    # Reject cross-site browser mutations. Native clients without Origin remain
    # supported; production multi-user deployments require independent auth.
    origin=request.headers.get('origin')
    if request.method in ['POST','PATCH','DELETE'] and origin:
        from urllib.parse import urlparse
        if urlparse(origin).netloc!=request.headers.get('host') and origin not in ['http://localhost:5173','http://127.0.0.1:5173']:
            return JSONResponse({'detail':'不允许跨站写入请求。'},status_code=403)
    # When authentication is enforced, business endpoints need a valid token.
    if AUTH_REQUIRED and request.url.path.startswith('/api/'):
        if not any(request.url.path.startswith(prefix) for prefix in PUBLIC_API):
            try:
                current_user(request.headers.get('authorization',''))
            except HTTPException as error:
                return JSONResponse({'detail':error.detail},status_code=error.status_code)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control']='no-store'
    return response


@app.get('/api/health')
def health():
    return {'status':'ok','version':'2.0.0','ocr_available':reader.available()}


@app.get('/docs',include_in_schema=False,response_class=HTMLResponse)
def offline_docs():
    from .openapi_ui import render
    return HTMLResponse(render(app.openapi()))


@app.get('/api/meta')
def meta():
    return {'settings':db.settings(),'categories':CATEGORIES,'ocr_available':reader.available(),
            # pipelines 为 API 层能力说明与诊断信息；界面不提供引擎选择入口。
            # 指定网络为 classic，ppocr 仅供对照测试，指定网络不可用时直接报错不回退。
            'pipelines':{'default':'classic','classic':{'available':reader.available(),'name':'CTPN → CRNN → CTC'},'ppocr':{'available':reader.ppocr_available(),'name':'PP-OCR（对照通道）'}},
            'provided_count':len(list((config.ROOT/'data'/'provided').glob('*.pdf'))),
            'demo_count':len(list((config.ROOT/'data'/'demo').glob('demo-*'))),
            'limits':{'max_file_mb':20,'max_batch_mb':100,'max_files':100,'max_pdf_pages':10}}


@app.get('/api/dashboard')
def dashboard(start:str='',end:str='',source:str=''):
    return service.dashboard(start,end,source)


@app.get('/api/invoices')
def invoices(q:str='',status:str='',category:str='',source:str='',start:str='',end:str='',sort:str='newest',page:int=Query(1,ge=1),page_size:int=Query(10,ge=1,le=100)):
    result=service.filtered(q,status,category,start,end,sort,source)
    return {'items':result[(page-1)*page_size:page*page_size],'total':len(result),'page':page,'page_size':page_size}


@app.get('/api/invoices/{invoice_id}')
def invoice(invoice_id:str):
    record=service.get_record(invoice_id)
    if not record:raise HTTPException(404,'发票不存在。')
    return record


def get_invoice_file(invoice_id,preview):
    with db.connection() as con:
        row=con.execute('SELECT * FROM invoices WHERE id=?',(invoice_id,)).fetchone()
    if not row:raise HTTPException(404,'发票不存在。')
    path=Path(row['preview_path' if preview else 'original_path'])
    if not path.is_file() or not path.is_relative_to(config.DATA):raise HTTPException(404,'原始文件不存在。')
    return FileResponse(path,media_type='image/jpeg' if preview else mimetypes.guess_type(path)[0],
                        filename=None if preview else row['filename'],content_disposition_type='inline')


@app.get('/api/invoices/{invoice_id}/preview')
def preview(invoice_id:str):
    return get_invoice_file(invoice_id,True)


@app.get('/api/invoices/{invoice_id}/original')
def original(invoice_id:str):
    return get_invoice_file(invoice_id,False)


class PatchInvoice(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    revision:int
    invoice_number:str=Field(max_length=32)
    invoice_code:str=Field(default='',max_length=20)
    invoice_date:str=Field(max_length=20)
    invoice_type:str=Field(max_length=40)
    buyer_name:str=Field(max_length=200)
    buyer_tax_id:str=Field(default='',max_length=32)
    seller_name:str=Field(max_length=200)
    seller_tax_id:str=Field(default='',max_length=32)
    subtotal:str|None=None
    tax_amount:str|None=None
    total:str|None=None
    tax_rates:str=Field(default='',max_length=80)
    category:Literal['差旅交通','餐饮招待','办公采购','技术服务','其他费用']
    remark:str=Field(default='',max_length=2000)

    @field_validator('subtotal','tax_amount','total')
    @classmethod
    def valid_money(cls,v):
        if v is None or v=='':return None
        result=money(v)
        if result is None:raise ValueError('金额格式不正确。')
        return result


@app.patch('/api/invoices/{invoice_id}')
def patch(invoice_id:str,patch:PatchInvoice):
    with service.mutation_lock:
        with db.connection() as con:
            row=con.execute('SELECT * FROM invoices WHERE id=?',(invoice_id,)).fetchone()
            if not row:raise HTTPException(404,'发票不存在。')
            if patch.revision!=row['revision']:raise HTTPException(409,'票据已被修改，请关闭后重新打开。')
            d=json.loads(row['doc']);updates=patch.model_dump(exclude={'revision'})
            changes={k:{'before':d.get(k),'after':v} for k,v in updates.items() if d.get(k)!=v}
            d.update(updates)
            d['completeness']=round(sum(d.get(k) is not None and d.get(k)!='' for k in FIELD_NAMES)/len(FIELD_NAMES)*100)
            if changes:
                d['manually_edited']=True
                con.execute("UPDATE invoices SET doc=?,status='needs_review',revision=revision+1,updated_at=? WHERE id=?",(json.dumps(d,ensure_ascii=False),db.now(),invoice_id))
                db.audit('edit','保存人工修订，等待确认',invoice_id,changes,con)
                service.reconcile_duplicates(con)
        return service.get_record(invoice_id)


class Review(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int
    verdict:Literal['approved','rejected','needs_review']
    note:str=Field(default='',max_length=1000)


@app.post('/api/invoices/{invoice_id}/review')
def review(invoice_id:str,body:Review):
    with service.mutation_lock:
        r=service.get_record(invoice_id)
        if not r:raise HTTPException(404,'发票不存在。')
        if r['revision']!=body.revision:raise HTTPException(409,'票据已被修改，请重新打开。')
        if body.verdict=='approved' and any(i['severity']=='error' for i in r['issues']):
            raise HTTPException(422,'请先修正必填字段、金额异常或重复票据。')
        if body.verdict=='approved' and any(other['id']!=r['id'] and other['status']!='rejected'
                                           and other.get('invoice_number')==r.get('invoice_number')
                                           and other.get('invoice_code','')==r.get('invoice_code','')
                                           for other in service.records()):
            raise HTTPException(422,'该票号已有保留的记录，不能重新确认重复票据。')
        if body.verdict=='rejected' and not body.note.strip():raise HTTPException(422,'请填写驳回原因。')
        with db.connection() as con:
            con.execute('UPDATE invoices SET status=?,revision=revision+1,updated_at=? WHERE id=?',(body.verdict,db.now(),invoice_id))
            db.audit({'approved':'approve','rejected':'reject','needs_review':'reopen'}[body.verdict],body.note or {'approved':'人工核对通过','needs_review':'退回重新复核'}[body.verdict],invoice_id,{'before':r['status'],'after':body.verdict},con)
            service.reconcile_duplicates(con)
    return service.get_record(invoice_id)


@app.delete('/api/invoices/{invoice_id}')
def remove(invoice_id:str):
    with service.mutation_lock:
        with db.connection() as con:
            row=con.execute('SELECT * FROM invoices WHERE id=?',(invoice_id,)).fetchone()
            if not row:raise HTTPException(404,'发票不存在。')
            con.execute('DELETE FROM invoices WHERE id=?',(invoice_id,))
            db.audit('delete',f"删除票据 {json.loads(row['doc']).get('invoice_number') or row['filename']}",invoice_id,con=con)
            referenced=con.execute('SELECT COUNT(*) FROM invoices WHERE original_path=?',(row['original_path'],)).fetchone()[0]
        Path(row['preview_path']).unlink(missing_ok=True)
        if not referenced:Path(row['original_path']).unlink(missing_ok=True)
    return {'ok':True}


@app.post('/api/imports',status_code=202)
async def upload(files:list[UploadFile]=File(...),pipeline:Literal['classic','ppocr']=Form('classic'),force_ocr:bool=Form(False)):
    if len(files)>config.MAX_FILES:raise HTTPException(413,'最多上传 100 个文件。')
    received=[];total=0
    for file in files:
        filename=file.filename or '未命名'
        content=await file.read(config.MAX_BATCH+1 if filename.lower().endswith('.zip') else config.MAX_FILE+1)
        total+=len(content)
        await file.close()
        if total>config.MAX_BATCH:raise HTTPException(413,'单批上传不能超过 100 MB。')
        received.append((filename,content))
    accepted,errors=service.expand_files(received)
    if not accepted:raise HTTPException(422,{'message':'没有可处理的文件。','errors':errors})
    return service.submit(accepted,errors,pipeline=pipeline,force_ocr=force_ocr)


@app.post('/api/datasets/{source}/import',status_code=202)
def import_dataset(source:Literal['provided','demo'],pipeline:Literal['classic','ppocr']='classic',force_ocr:bool=False):
    directory=config.ROOT/'data'/source
    if not directory.exists():raise HTTPException(404,'该数据集未随项目分发。')
    files=[(p.name,p.read_bytes()) for p in sorted(directory.iterdir()) if p.suffix.lower() in config.SUPPORTED]
    if not files:raise HTTPException(404,'数据集为空。')
    return service.submit(files,source=source,pipeline=pipeline,force_ocr=force_ocr)


@app.get('/api/datasets/demo/sample')
def demo_sample():
    path=config.ROOT/'data'/'demo'/'demo-12.png'
    if not path.is_file():raise HTTPException(404,'图片样例不存在。')
    return FileResponse(path,media_type='image/png',filename='demo-invoice.png')


@app.get('/api/jobs')
def jobs():
    with db.connection() as con:
        return {'items':[json.loads(r['data']) for r in con.execute('SELECT * FROM jobs ORDER BY updated_at DESC LIMIT 30')]}


@app.get('/api/jobs/{job_id}')
def job(job_id:str):
    with db.connection() as con:
        row=con.execute('SELECT * FROM jobs WHERE id=?',(job_id,)).fetchone()
    if not row:raise HTTPException(404,'任务不存在。')
    return json.loads(row['data'])


@app.get('/api/export')
def export_data(format:Literal['xlsx','csv','json']='xlsx',ids:str='',q:str='',status:str='',category:str='',source:str='',start:str='',end:str=''):
    rows=service.filtered(q,status,category,start,end,source=source)
    if ids:
        selected=set(ids.split(','));rows=[r for r in rows if r['id'] in selected]
    if not rows:raise HTTPException(422,'当前筛选范围内没有可导出的发票。')
    data,mime,ext=export(rows,format)
    db.audit('export',f'导出 {len(rows)} 张票据为 {ext.upper()}',changes={'count':len(rows),'format':ext,'ids':[r['id'] for r in rows]})
    return Response(data,media_type=mime,headers={'Content-Disposition':f"attachment; filename=piao-invoices.{ext}; filename*=UTF-8''{quote('票序发票台账.'+ext)}"})


@app.get('/api/audit')
def audits(action:str='',page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100)):
    with db.connection() as con:
        where=' WHERE action=?' if action else ''
        args=[action] if action else []
        total=con.execute('SELECT COUNT(*) FROM audit'+where,args).fetchone()[0]
        rows=con.execute('SELECT * FROM audit'+where+' ORDER BY id DESC LIMIT ? OFFSET ?',args+[page_size,(page-1)*page_size]).fetchall()
    return {'items':[{**dict(r),'changes':json.loads(r['changes'])} for r in rows],'total':total}


class Settings(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    workspace_name:str=Field(min_length=1,max_length=40)
    confidence_threshold:float=Field(ge=.5,le=1)
    amount_tolerance:Literal['0.00','0.01','0.02']='0.02'


@app.patch('/api/settings')
def settings(body:Settings):
    with service.mutation_lock:
        with db.connection() as con:
            before=db.settings()
            for k,v in body.model_dump().items():con.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',(k,json.dumps(v,ensure_ascii=False)))
            db.audit('settings','更新工作区与复核设置',changes={'before':before,'after':body.model_dump()},con=con)
            # A tighter amount policy can invalidate previously approved rows.
            for r in con.execute("SELECT id,doc FROM invoices WHERE status='approved'").fetchall():
                if any(i['severity']=='error' for i in validate(json.loads(r['doc']),body.amount_tolerance,body.confidence_threshold)):
                    con.execute("UPDATE invoices SET status='needs_review',revision=revision+1,updated_at=? WHERE id=?",(db.now(),r['id']))
    return db.settings()


@app.get('/{path:path}',include_in_schema=False)
def frontend(path:str):
    if path.startswith('api/'):raise HTTPException(404,'API 不存在。')
    dist=config.ROOT/'dist'
    target=(dist/path).resolve()
    if target.is_relative_to(dist) and target.is_file():return FileResponse(target)
    if (dist/'index.html').exists():return FileResponse(dist/'index.html')
    return JSONResponse({'message':'请先构建前端：npm --prefix frontend install && npm run build'},status_code=503)
