"""Geometry-assisted, conservative invoice extraction. Missing values stay missing."""
import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

CATEGORIES = ['差旅交通', '餐饮招待', '办公采购', '技术服务', '其他费用']
FIELD_NAMES = {
    'invoice_number': '发票号码', 'invoice_date': '开票日期', 'buyer_name': '购买方名称',
    'seller_name': '销售方名称', 'total': '价税合计', 'subtotal': '不含税金额', 'tax_amount': '税额',
}


def clean(s):
    return unicodedata.normalize('NFKC', s).replace('￥', '¥').replace('\u3000', ' ').strip()


def money(value):
    if value is None or str(value).strip() == '':
        return None
    try:
        v = Decimal(re.sub(r'[,¥￥\s]', '', str(value)))
        if not v.is_finite() or abs(v) > Decimal('999999999999.99'):
            return None
        return format(v.quantize(Decimal('.01'), rounding=ROUND_HALF_UP), '.2f')
    except (InvalidOperation, ValueError):
        return None


def amounts(s):
    return [money(v) for v in re.findall(r'(?<![\d.])-?\d[\d,]*\.\d{2}(?!\d)', clean(s))]


def row_groups(boxes):
    rows = []
    for b in sorted(boxes, key=lambda b: ((b['rect'][1] + b['rect'][3]) / 2, b['rect'][0])):
        cy = (b['rect'][1] + b['rect'][3]) / 2
        h = max(b['rect'][3] - b['rect'][1], .008)
        if rows and abs(rows[-1]['cy'] - cy) < h * .48:
            rows[-1]['boxes'].append(b)
        else:
            rows.append({'cy': cy, 'boxes': [b]})
    return [' '.join(b['text'] for b in sorted(row['boxes'], key=lambda b: b['rect'][0])) for row in rows]


def parse(boxes, engine='pdf_text'):
    boxes = [{**b, 'text': clean(b['text'])} for b in boxes]
    rows = row_groups(boxes)
    text = '\n'.join(rows)
    compact = re.sub(r'\s+', '', text)
    doc = {k: '' for k in ['invoice_number', 'invoice_code', 'invoice_date', 'buyer_name', 'buyer_tax_id',
                          'seller_name', 'seller_tax_id', 'remark']}
    doc.update(total=None, subtotal=None, tax_amount=None, tax_rates='', currency='CNY',
               category='其他费用', invoice_type='增值税发票', engine=engine, boxes=boxes,
               raw_text=text, items=[], evidence={}, field_confidence={})
    if '专用发票' in compact:
        doc['invoice_type'] = '增值税专用发票'
    elif '电子发票' in compact or '电子普通发票' in compact:
        doc['invoice_type'] = '电子普通发票'
    number = re.search(r'(?:发票号码|票据号码|发票号|号码|No\.?)[：: ]*([0-9]{20}|[0-9]{8})(?![0-9])', text, re.I)
    if not number:
        number = re.search(r'(?<!\d)(\d{20})(?!\d)', compact)
    if number:
        doc['invoice_number'] = number.group(1)
    code = re.search(r'发票代码[：:]*(\d{10,12})(?!\d)', compact)
    if code:
        doc['invoice_code'] = code.group(1)
    dt = re.search(r'(20\d{2})[年/.-](\d{1,2})[月/.-](\d{1,2})日?', compact)
    if dt:
        try:
            doc['invoice_date'] = date(*map(int, dt.groups())).isoformat()
        except ValueError:
            pass
    # Modern electronic invoices place both parties side by side. Legacy paper
    # invoices put the seller below the items; splitting by x/y supports both.
    name_boxes = [b for b in boxes if re.search(r'名\s*称\s*[：:]', b['text'])]
    if name_boxes:
        name_boxes.sort(key=lambda b: (round(b['rect'][1] / .035), b['rect'][0]))
        for index, b in enumerate(name_boxes[:2]):
            role = 'buyer' if index == 0 else 'seller'
            region = [v for v in boxes if abs(v['rect'][1]-b['rect'][1]) < .018
                      and v['rect'][0] >= b['rect'][0] - .01
                      and (v['rect'][0] < .49 if b['rect'][0] < .49 else True)]
            line = ' '.join(v['text'] for v in sorted(region, key=lambda v: v['rect'][0]))
            found = re.search(r'名\s*称\s*[：:]\s*(.+?)(?:统一|纳税|$)', line)
            if found:
                name = re.sub(r'\s+', '', found.group(1)).rstrip('购销售')
                doc[f'{role}_name'] = name
                doc['evidence'][f'{role}_name'] = b['id']
    # Some OCR output places the label and value in separate boxes, or merges
    # both parties into one line. Fall back to text rows without inventing names.
    if not doc['seller_name']:
        names = re.findall(r'名称\s*[:：]\s*(.+?)(?=\s+(?:销|购|名称|统一)|\n|$)', text)
        if len(names) >= 2:
            doc['buyer_name'], doc['seller_name'] = [re.sub(r'\s+', '', v) for v in names[:2]]
    id_boxes = []
    for b in boxes:
        ids = re.findall(r'(?<![A-Z0-9])([0-9A-Z]{18}|[0-9A-Z]{15}|[0-9A-Z]{20})(?![A-Z0-9])', b['text'])
        for value in ids:
            if value == doc['invoice_number'] or value.isdigit() and len(value) == 20:
                continue
            if any(c.isalpha() for c in value) or re.search('识别号|信用代码', b['text']):
                id_boxes.append((b, value))
    id_boxes.sort(key=lambda x: (round(x[0]['rect'][1] / .04), x[0]['rect'][0]))
    seen = []
    for b, value in id_boxes:
        if value not in [v for _, v in seen]:
            seen.append((b, value))
    for role, pair in zip(['buyer', 'seller'], seen[:2]):
        doc[f'{role}_tax_id'] = pair[1]
        doc['evidence'][f'{role}_tax_id'] = pair[0]['id']
    # Summation is extracted only from the actual total row, never inferred
    # from the largest number in the document.
    for i, row in enumerate(rows):
        stripped = re.sub(r'\s+', '', row)
        if re.search(r'合计', stripped) and '价税' not in stripped:
            vals = amounts(row)
            if len(vals) >= 2:
                doc['subtotal'], doc['tax_amount'] = vals[-2:]
            elif len(vals) == 1:
                doc['subtotal'] = vals[0]
                if '免税' in row or '不征税' in row:
                    doc['tax_amount'] = '0.00'
            elif i + 1 < len(rows) and '价税' not in rows[i+1]:
                vals = amounts(row + ' ' + rows[i+1])
                if len(vals) >= 2:
                    doc['subtotal'], doc['tax_amount'] = vals[-2:]
        if '小写' in stripped:
            tail = re.split('小写', row)[-1]
            vals = amounts(tail)
            if vals:
                doc['total'] = vals[-1]
    # Fallback to nearby amount boxes at the total label's height.
    for key, label in [('total', '小写'), ('subtotal', '合计')]:
        if doc[key] is not None:
            continue
        for b in boxes:
            bt = re.sub(r'\s+', '', b['text'])
            if label not in bt or key == 'subtotal' and '价税' in bt:
                continue
            nearby = sorted([v for v in boxes if abs(v['rect'][1]-b['rect'][1]) < .012 and v['rect'][0] >= b['rect'][0]], key=lambda v:v['rect'][0])
            vals = amounts(' '.join(v['text'] for v in nearby))
            if vals:
                doc[key] = vals[-1] if key == 'total' else vals[0]
                if key == 'subtotal' and len(vals) >= 2:
                    doc['tax_amount'] = vals[-1]
                break
    # Missing totals are not inferred. Only two explicit currency amounts on
    # the same row may be used when they agree with the separately printed total.
    if doc['subtotal'] is None and doc['tax_amount'] is None and doc['total'] is not None:
        for row in rows:
            vals=amounts(row)
            if row.count('¥')==2 and len(vals)==2 and abs(Decimal(vals[0])+Decimal(vals[1])-Decimal(doc['total']))<=Decimal('.02'):
                doc['subtotal'],doc['tax_amount']=vals
                break
    tokens=re.findall(r'(?<![\d.])\d{1,2}(?:\.\d+)?%',text)+re.findall(r'\.\d{2}(\d{1,2}(?:\.\d+)?%)',text)
    rates=sorted(set(tokens),key=lambda x:float(x[:-1]))
    if not rates and '免税' in compact:
        rates = ['免税']
    doc['tax_rates'] = ' / '.join(rates)
    for row in rows:
        if '*' not in row:
            continue
        name = re.search(r'\*[^*]+\*[^\s]+', row)
        if not name:
            continue
        vals = amounts(row)
        rate = re.search(r'\d+(?:\.\d+)?%|免税|不征税', row)
        doc['items'].append({'name':name.group(0), 'amount':vals[-2] if len(vals)>=2 else None,
                             'tax_amount':vals[-1] if len(vals)>=2 else None,
                             'tax_rate':rate.group(0) if rate else ''})
    if re.search(r'运输|客运|汽油|机票|出租|打车|交通|旅客|住宿|酒店', compact):
        doc['category'] = '差旅交通'
    elif re.search(r'餐饮|饮食|餐费|食品|小吃', compact):
        doc['category'] = '餐饮招待'
    elif re.search(r'文具|办公|日用品|纸制品|塑料|零售|超市', compact):
        doc['category'] = '办公采购'
    elif re.search(r'技术服务|信息技术服务|软件|咨询|研发', compact):
        doc['category'] = '技术服务'
    doc['confidence'] = round(sum(b.get('score', 1) for b in boxes)/len(boxes), 4) if boxes else 0
    for key in FIELD_NAMES:
        value = doc.get(key)
        if value:
            target = str(value).replace('-', '') if key == 'invoice_date' else str(value)
            match = next((b for b in boxes if target in re.sub(r'[,\s年月日.-]', '', b['text'])
                          if key in ['invoice_number','invoice_date']), None) if key in ['invoice_number','invoice_date'] else next((b for b in boxes if str(value) in b['text'].replace(',', '')), None)
            if match:
                doc['evidence'][key] = match['id']
                doc['field_confidence'][key] = match.get('score', 1)
    doc['completeness'] = round(sum(bool(doc.get(k) is not None and doc.get(k) != '') for k in FIELD_NAMES)/len(FIELD_NAMES)*100)
    return doc


def validate(doc, tolerance='0.02', threshold=.9, duplicate=False):
    issues = []
    for key, name in FIELD_NAMES.items():
        if doc.get(key) is None or doc.get(key) == '':
            issues.append({'field':key,'message':f'缺少{name}','severity':'error'})
    num = doc.get('invoice_number','')
    if num and not re.fullmatch(r'(?:\d{8}|\d{20})', num):
        issues.append({'field':'invoice_number','message':'发票号码应为 8 位或 20 位数字','severity':'error'})
    if len(num) == 8 and not re.fullmatch(r'(?:\d{10}|\d{12})', doc.get('invoice_code', '')):
        issues.append({'field':'invoice_code','message':'传统 8 位发票号码需同时填写 10 位或 12 位发票代码','severity':'error'})
    try:
        if doc.get('invoice_date'):
            date.fromisoformat(doc['invoice_date'])
    except ValueError:
        issues.append({'field':'invoice_date','message':'开票日期格式不正确','severity':'error'})
    vals = [money(doc.get(k)) for k in ['subtotal','tax_amount','total']]
    if all(v is not None for v in vals):
        diff = abs(Decimal(vals[0])+Decimal(vals[1])-Decimal(vals[2]))
        if diff > Decimal(tolerance):
            issues.append({'field':'total','message':f'金额不平：不含税金额 + 税额与价税合计相差 ¥{diff:.2f}','severity':'error'})
    if doc.get('confidence', 1) < threshold:
        issues.append({'field':'confidence','message':'OCR 文本平均分数低于复核阈值，请逐项核对','severity':'warning'})
    if duplicate:
        issues.append({'field':'invoice_number','message':'存在相同发票代码与号码，请核查重复票据','severity':'error'})
    for role in ['buyer','seller']:
        tid = doc.get(f'{role}_tax_id','')
        if tid and not re.fullmatch(r'[0-9A-Z]{15,20}', tid):
            issues.append({'field':f'{role}_tax_id','message':f'{"购买方" if role=="buyer" else "销售方"}税号格式需核对','severity':'warning'})
    return issues
