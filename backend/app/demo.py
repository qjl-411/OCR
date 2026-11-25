"""Create visibly fictional invoice documents for an offline demonstration."""
import io
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import fitz
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfgen import canvas

from . import config, db

SPECS = [
    ('松云数字科技（示例）有限公司','*信息技术服务*软件服务费','8480.00','6%','2026-11-19','approved'),
    ('简物办公（示例）有限公司','*办公用品*文具用品','1286.00','13%','2026-11-17','approved'),
    ('栖山酒店（示例）有限公司','*住宿服务*住宿费','642.00','6%','2026-11-16','approved'),
    ('山野餐饮（示例）有限公司','*餐饮服务*工作餐','356.00','6%','2026-11-12','approved'),
    ('知行咨询（示例）有限公司','*技术服务*技术咨询费','2100.00','6%','2026-10-15','approved'),
    ('城市出行（示例）有限公司','*运输服务*客运服务费','85.70','3%','2026-10-22','approved'),
    ('简物办公（示例）有限公司','*办公用品*打印纸','726.00','13%','2026-09-18','approved'),
    ('松云数字科技（示例）有限公司','*信息技术服务*维护费','1360.00','6%','2026-11-18','needs_review'),
    ('城市出行（示例）有限公司','*运输服务*客运服务费','128.50','3%','2026-11-15','needs_review'),
    ('城市出行（示例）有限公司','*运输服务*客运服务费','128.50','3%','2026-11-15','needs_review'),
    ('简物办公（示例）有限公司','*办公用品*打印耗材','268.00','13%','2026-11-14','needs_review'),
    ('山野餐饮（示例）有限公司','*餐饮服务*工作餐','186.00','6%','2026-11-13','needs_review'),
]


def make_pdf(index,spec):
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    seller,item,total,rate,dt,_=spec
    tax_rate=Decimal(rate.rstrip('%'))/100
    subtotal=(Decimal(total)/(1+tax_rate)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    tax=Decimal(total)-subtotal
    number=f'9900000000000000{(9 if index==10 else index):04d}'
    if index==11:tax+=Decimal('10') # Deliberate source-level anomaly.
    out=io.BytesIO();c=canvas.Canvas(out,pagesize=(842,560))
    c.setTitle(f'教学演示票据 {index:02d}')
    c.setFillColorRGB(.55,.22,.20)
    def text(x,y,value,size=12):
        c.setFont('STSong-Light',size);c.drawString(x,y,str(value))
    text(285,514,'电子发票（普通发票）',24)
    text(325,486,'教学演示票据  非真实发票',13)
    c.setFillColorRGB(.16,.20,.18)
    text(565,452,'发票号码：'+number,12)
    text(565,430,'开票日期：'+dt.replace('-','年',1).replace('-','月')+'日',12)
    c.setStrokeColorRGB(.65,.42,.38);c.setLineWidth(.6)
    c.rect(24,120,794,280)
    c.line(24,315,818,315);c.line(24,275,818,275);c.line(24,190,818,190);c.line(24,150,818,150)
    c.line(421,315,421,400)
    text(36,375,'购买方信息',11);text(438,375,'销售方信息',11)
    text(36,351,'名称：青禾创新（教学示例）有限公司',12)
    text(36,329,'纳税人识别号：DEMO00000000000001',10)
    text(438,351,'名称：'+seller,12)
    text(438,329,f'纳税人识别号：DEMO0000000000{index:04d}',10)
    for x,label in [(36,'项目名称'),(410,'数量'),(500,'单价'),(600,'金额'),(684,'税率'),(750,'税额')]:text(x,290,label,12)
    text(36,244,item,12);text(418,244,'1');text(490,244,f'{subtotal:.2f}');text(595,244,f'{subtotal:.2f}');text(686,244,rate);text(747,244,f'{tax:.2f}')
    text(45,166,'合  计');text(584,166,f'¥{subtotal:.2f}');text(735,166,f'¥{tax:.2f}')
    text(45,130,'价税合计（大写） 教学示例');text(630,130,'（小写）¥'+total,14)
    text(36,93,'备注：仅供课程项目功能演示，不构成真实交易凭证。',12)
    text(36,65,'开票人：示例操作员',12)
    text(565,65,'DEMO  '+str(index),11)
    c.save();return out.getvalue()


def ensure_demo_files():
    directory=config.ROOT/'data'/'demo';directory.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for i,spec in enumerate(SPECS,1):
        pdf=make_pdf(i,spec)
        name=f'demo-{i:02d}.pdf'
        if i==12:
            document=fitz.open(stream=pdf,filetype='pdf')
            pix=document[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
            name=f'demo-{i:02d}.png';(directory/name).write_bytes(pix.tobytes('png'))
            document.close()
        else:
            (directory/name).write_bytes(pdf)
        manifest.append({'file':name,'source':'synthetic','invoice_number':f'9900000000000000{(9 if i==10 else i):04d}',
                         'total':spec[2],'invoice_date':spec[4],'category':'synthetic','expected_status':spec[5],
                         'purpose':'重复票' if i in [9,10] else '金额异常' if i==11 else '图片 OCR' if i==12 else '正常演示'})
    (directory/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


def seed_if_empty():
    from .service import import_file
    with db.connection() as con:
        if con.execute('SELECT COUNT(*) FROM invoices').fetchone()[0]:return
        marker=con.execute("SELECT value FROM settings WHERE key='initialized'").fetchone()
        if marker:return # Deleting all records should not unexpectedly reseed.
    directory=config.ROOT/'data'/'demo'
    if not (directory/'manifest.json').exists():
        ensure_demo_files()
    manifest=json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    for item in manifest:
        # Demo seed stays fast and deterministic. The image sample is offered
        # for a real OCR import from the recognition page, never prelabelled OCR.
        if item['file'].endswith('.png'):continue
        result=import_file(item['file'],(directory/item['file']).read_bytes(),'demo')
        if item['expected_status']=='approved':
            with db.connection() as con:
                for inv_id in result['invoice_ids']:
                    con.execute("UPDATE invoices SET status='approved' WHERE id=?",(inv_id,))
                    db.audit('approve','初始化合成演示确认记录',inv_id,con=con)
    with db.connection() as con:
        con.execute('INSERT OR REPLACE INTO settings VALUES(?,?)',('initialized','true'))
