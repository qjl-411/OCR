import hashlib
import io
import json
import logging
import re
import threading
import uuid
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from . import config, db, reader
from .parser import parse, validate

log = logging.getLogger(__name__)
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='invoice-ocr')
mutation_lock = threading.RLock()


def decode(row):
    result = dict(row)
    doc = json.loads(result.pop('doc'))
    result.update(doc)
    result.pop('sha256', None)
    result.pop('original_path', None)
    result.pop('preview_path', None)
    result['preview_url'] = f"/api/invoices/{result['id']}/preview"
    result['original_url'] = f"/api/invoices/{result['id']}/original"
    return result


def records(detail=False):
    with db.connection() as con:
        rows = con.execute('SELECT * FROM invoices ORDER BY created_at DESC,id DESC').fetchall()
    result = [decode(r) for r in rows]
    numbers = Counter((r.get('invoice_code', ''), r.get('invoice_number')) for r in result if r.get('invoice_number') and r['status'] != 'rejected')
    settings = db.settings()
    for r in result:
        r['duplicate'] = bool(r.get('invoice_number') and r['status']!='rejected' and numbers[(r.get('invoice_code',''),r['invoice_number'])]>1)
        r['issues'] = validate(r, settings['amount_tolerance'], settings['confidence_threshold'], r['duplicate'])
        if not detail:
            for key in ['raw_text','boxes','evidence','field_confidence','items']:
                r.pop(key,None)
    return result


def get_record(invoice_id):
    return next((r for r in records(True) if r['id']==invoice_id), None)


def filtered(q='',status='',category='',start='',end='',sort='newest',source=''):
    items=records()
    if q:
        q=q.casefold().strip()
        items=[r for r in items if q in ' '.join(str(r.get(k) or '') for k in ['invoice_number','invoice_code','seller_name','buyer_name','filename']).casefold()]
    if status=='anomaly':
        items=[r for r in items if r['issues'] and r['status']!='rejected']
    elif status=='duplicate':
        items=[r for r in items if r['duplicate']]
    elif status:
        items=[r for r in items if r['status']==status]
    if category:
        items=[r for r in items if r.get('category')==category]
    if source:
        items=[r for r in items if r.get('source')==source]
    if start:
        items=[r for r in items if r.get('invoice_date','')>=start]
    if end:
        items=[r for r in items if r.get('invoice_date','')<=end and r.get('invoice_date')]
    if sort=='amount_desc':
        items.sort(key=lambda r:Decimal(r.get('total') or '0'),reverse=True)
    elif sort=='date_desc':
        items.sort(key=lambda r:r.get('invoice_date',''),reverse=True)
    return items


def expand_files(files):
    output=[]; errors=[]; total=0
    for name,data in files:
        name=Path(name.replace('\\','/')).name[:240]
        suffix=Path(name).suffix.lower()
        if len(data)>config.MAX_BATCH:
            errors.append({'filename':name,'message':'单批文件超过 100 MB。'}); continue
        if suffix=='.zip':
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as z:
                    members=[i for i in z.infolist() if not i.is_dir() and not i.filename.startswith('__MACOSX/')]
                    if len(members)>config.MAX_FILES or sum(i.file_size for i in members)>config.MAX_BATCH:
                        raise ValueError('ZIP 解压后超过 100 个文件或 100 MB。')
                    for info in members:
                        path=Path(info.filename.replace('\\','/'))
                        if path.is_absolute() or '..' in path.parts or info.flag_bits & 1:
                            errors.append({'filename':info.filename,'message':'不支持不安全路径或加密压缩条目。'});continue
                        if path.suffix.lower() not in config.SUPPORTED:
                            errors.append({'filename':path.name,'message':'已跳过不支持的文件格式。'});continue
                        if info.file_size>config.MAX_FILE:
                            errors.append({'filename':path.name,'message':'单文件超过 20 MB。'});continue
                        content=z.read(info)
                        total+=len(content)
                        if total>config.MAX_BATCH or len(output)>=config.MAX_FILES:
                            raise ValueError('解压后批次过大。')
                        output.append((path.name[:240],content))
            except (zipfile.BadZipFile, RuntimeError, ValueError, OSError) as e:
                errors.append({'filename':name,'message':str(e) if isinstance(e,ValueError) else 'ZIP 损坏或无法读取。'})
        elif suffix in config.SUPPORTED:
            if len(data)>config.MAX_FILE:
                errors.append({'filename':name,'message':'单文件超过 20 MB。'});continue
            total+=len(data)
            if total>config.MAX_BATCH or len(output)>=config.MAX_FILES:
                errors.append({'filename':name,'message':'单批最多 100 个文件、合计 100 MB。'});continue
            output.append((name,data))
        else:
            errors.append({'filename':name,'message':'支持 PDF、PNG、JPG、JPEG 和 ZIP。'})
    return output,errors


def reconcile_duplicates(con):
    rows=con.execute("SELECT id,doc,status FROM invoices WHERE status!='rejected'").fetchall()
    keys=Counter((json.loads(r['doc']).get('invoice_code',''),json.loads(r['doc']).get('invoice_number')) for r in rows if json.loads(r['doc']).get('invoice_number'))
    for r in rows:
        d=json.loads(r['doc'])
        if r['status']=='approved' and keys[(d.get('invoice_code',''),d.get('invoice_number'))]>1:
            con.execute("UPDATE invoices SET status='needs_review',revision=revision+1,updated_at=? WHERE id=?",(db.now(),r['id']))
            db.audit('duplicate','出现相同票号，已退回待复核',r['id'],con=con)


def import_file(name,data,source='upload',pipeline='classic',force_ocr=False):
    content_digest=hashlib.sha256(data).hexdigest()
    digest=hashlib.sha256(data+f'|{pipeline}|{force_ocr}|{reader.model_version(pipeline)}'.encode()).hexdigest()
    # Fully materialize page results before insertion so a failed later page
    # never leaves a partially imported file hidden behind a failed task item.
    with db.connection() as con:
        existing=con.execute('SELECT id FROM invoices WHERE sha256=?',(digest,)).fetchall()
        if existing:
            return {'filename':name,'status':'skipped','message':'相同内容已存在，已跳过','invoice_ids':[r['id'] for r in existing]}
    ext=Path(name).suffix.lower()
    pages=list(reader.read_pages(data,ext,pipeline=pipeline,force_ocr=force_ocr))
    parsed_pages=[]
    for page,image,boxes,engine in pages:
        doc=parse(boxes,engine)
        doc['preprocessing']={'deskew_degrees':image.info.get('deskew_degrees',0)}
        doc['processing_profile']={'pipeline':pipeline,'force_ocr':force_ocr,'content_sha256':content_digest,'model_version':image.info.get('model_version'),'timing':image.info.get('inference_seconds')}
        if len(doc['raw_text'])<8:
            raise ValueError('未识别到有效文字，请提供清晰票据。')
        parsed_pages.append((page,image,doc))
    ids=[]
    path=config.DATA/'originals'/f'{content_digest}{ext}'
    with mutation_lock:
        with db.connection() as con:
            existing=con.execute('SELECT id FROM invoices WHERE sha256=?',(digest,)).fetchall()
            if existing:
                return {'filename':name,'status':'skipped','message':'相同内容已存在，已跳过','invoice_ids':[r['id'] for r in existing]}
            path.write_bytes(data)
            for page,image,doc in parsed_pages:
                inv_id=uuid.uuid4().hex
                preview=config.DATA/'previews'/f'{inv_id}.jpg'
                image.save(preview,'JPEG',quality=90)
                timestamp=db.now()
                con.execute('INSERT INTO invoices(id,sha256,page,filename,original_path,preview_path,status,source,doc,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                            (inv_id,digest,page,name,str(path),str(preview),'needs_review',source,json.dumps(doc,ensure_ascii=False),timestamp,timestamp))
                ids.append(inv_id)
                db.audit('import',f"识别 {name} 第 {page} 页",inv_id,{'engine':doc['engine'],'source':source},con)
            reconcile_duplicates(con)
    return {'filename':name,'status':'completed','message':f'识别完成 · {len(ids)} 张票据','invoice_ids':ids}


def run_job(job,files):
    job['status']='running';db.save_job(job)
    for name,data in files:
        job['current_file']=name;db.save_job(job)
        try:
            result=import_file(name,data,job.get('source','upload'),job.get('pipeline','classic'),job.get('force_ocr',False))
            job['skipped' if result['status']=='skipped' else 'succeeded']+=1
        except Exception as e:
            log.exception('Invoice import failed: %s',name)
            result={'filename':name,'status':'failed','message':str(e) if isinstance(e,(ValueError,RuntimeError)) else '识别失败，请检查文件或查看服务日志。','invoice_ids':[]}
            job['failed']+=1
        job['results'].append(result);job['processed']+=1;db.save_job(job)
    job['status']='completed';job['current_file']='';job['finished_at']=db.now();db.save_job(job)


def submit(files,errors=None,source='upload',pipeline='classic',force_ocr=False):
    job={'id':uuid.uuid4().hex,'status':'queued','total':len(files),'processed':0,'succeeded':0,'failed':0,'skipped':0,
         'results':[],'errors':errors or [],'source':source,'pipeline':pipeline,'force_ocr':force_ocr,'created_at':db.now(),'current_file':''}
    db.save_job(job)
    executor.submit(run_job,job,files)
    return job


def dashboard(start='',end='',source=''):
    items=filtered(start=start,end=end,source=source)
    approved=[r for r in items if r['status']=='approved' and not r['duplicate']]
    def summed(rows,key='total'):
        return format(sum((Decimal(r.get(key) or '0') for r in rows),Decimal('0')),'.2f')
    months=defaultdict(list);cats=defaultdict(list);sellers=defaultdict(list)
    for r in approved:
        months[r.get('invoice_date','')[:7]].append(r)
        cats[r.get('category','其他费用')].append(r)
        sellers[r.get('seller_name','未识别')].append(r)
    return {'total_count':len(items),'approved_count':len(approved),'pending_count':sum(r['status']=='needs_review' for r in items),
            'rejected_count':sum(r['status']=='rejected' for r in items),'anomaly_count':sum(bool(r['issues']) and r['status']!='rejected' for r in items),
            'duplicate_count':sum(r['duplicate'] for r in items),'total_amount':summed(approved),'tax_amount':summed(approved,'tax_amount'),
            'pdf_count':sum(r['engine']=='pdf_text' for r in items),'ocr_count':sum(r['engine']!='pdf_text' for r in items),
            'trend':[{'month':m,'amount':float(summed(v)),'count':len(v)} for m,v in sorted(months.items())],
            'categories':[{'name':k,'amount':float(summed(v)),'count':len(v)} for k,v in sorted(cats.items(),key=lambda kv:Decimal(summed(kv[1])),reverse=True)],
            'suppliers':[{'name':k,'amount':float(summed(v)),'count':len(v)} for k,v in sorted(sellers.items(),key=lambda kv:Decimal(summed(kv[1])),reverse=True)[:8]],
            'recent':items[:6]}
