import csv
import io
import json
from decimal import Decimal

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

LABELS=[('invoice_number','发票号码'),('invoice_code','发票代码'),('invoice_date','开票日期'),('invoice_type','发票类型'),
        ('buyer_name','购买方名称'),('buyer_tax_id','购买方税号'),('seller_name','销售方名称'),('seller_tax_id','销售方税号'),
        ('subtotal','不含税金额'),('tax_amount','税额'),('total','价税合计'),('tax_rates','税率'),('category','费用分类'),
        ('status','复核状态'),('source','数据来源'),('engine','提取通道'),('filename','原始文件'),('page','页码'),('issues','异常提示'),('remark','备注')]
STATUSES={'approved':'已确认','needs_review':'待复核','rejected':'已驳回'}


def cell_value(r,key):
    value=r.get(key)
    if key=='status':return STATUSES.get(value,value)
    if key=='issues':return '；'.join(i['message'] for i in value or [])
    if key=='source':return {'demo':'合成演示','provided':'用户提供','upload':'本地上传'}.get(value,value)
    if key=='engine':return 'PDF 文字层' if value=='pdf_text' else '图片 OCR'
    return '' if value is None else value


def safe_csv(value):
    s=str(value)
    return "'"+s if s.startswith(('=','+','-','@','\t','\r')) else s


def export(rows,fmt):
    if fmt=='json':
        return json.dumps({'schema_version':1,'statistics_scope':'金额统计仅包含已确认且不重复票据','invoices':rows},ensure_ascii=False,indent=2).encode(),'application/json','json'
    if fmt=='csv':
        out=io.StringIO(newline='');writer=csv.writer(out)
        writer.writerow([label for _,label in LABELS])
        for r in rows:
            writer.writerow([safe_csv(cell_value(r,key)) for key,_ in LABELS])
        return ('\ufeff'+out.getvalue()).encode(),'text/csv; charset=utf-8','csv'
    wb=Workbook();ws=wb.active;ws.title='发票明细'
    ws.append([label for _,label in LABELS])
    for r in rows:
        ws.append([cell_value(r,key) for key,_ in LABELS])
        for col,(key,_) in enumerate(LABELS,1):
            cell=ws.cell(ws.max_row,col)
            if key in ['subtotal','tax_amount','total'] and r.get(key) is not None:
                cell.value=float(Decimal(r[key]));cell.number_format='#,##0.00;[Red]-#,##0.00'
            elif isinstance(cell.value,str):
                cell.data_type='s' # Prevent spreadsheet formula injection, preserve IDs.
    ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    for col,(key,_) in enumerate(LABELS,1):
        ws.column_dimensions[ws.cell(1,col).column_letter].width=36 if key in ['seller_name','buyer_name','issues','filename','remark'] else 25 if key in ['invoice_number','buyer_tax_id','seller_tax_id'] else 16
    summary=wb.create_sheet('汇总说明')
    approved=[r for r in rows if r['status']=='approved' and not r['duplicate']]
    summary.append(['项目','数值'])
    for label,value in [('导出票据数量',len(rows)),('已确认数量',len(approved)),('待复核数量',sum(r['status']=='needs_review' for r in rows)),
                        ('已确认价税合计',float(sum((Decimal(r.get('total') or '0') for r in approved),Decimal('0')))),
                        ('统计口径','仅已确认且非重复票据计入金额；并非税务真伪查验结果'),('演示数据','标记为合成演示的票据不能用于报销或税务用途')]:
        summary.append([label,value])
    summary.column_dimensions['A'].width=26;summary.column_dimensions['B'].width=80
    for sheet in wb:
        sheet.row_dimensions[1].height=28
        for cell in sheet[1]:
            cell.fill=PatternFill('solid',fgColor='164C3D');cell.font=Font(color='FFFFFF',bold=True)
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.alignment=Alignment(vertical='top',wrap_text=True)
                if cell.row%2==0:cell.fill=PatternFill('solid',fgColor='F2F7F4')
    out=io.BytesIO();wb.save(out)
    return out.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','xlsx'
