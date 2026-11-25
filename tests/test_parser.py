from pathlib import Path
import json

import pytest

from backend.app import config
from backend.app.parser import money,parse,validate
from backend.app.reader import read_pages


@pytest.mark.parametrize('value,expected',[('1,234.50','1234.50'),('0.105','0.11'),('-1.005','-1.01'),('¥ 8.20','8.20'),('NaN',None),('Infinity',None),('',None),(None,None),('abc',None),('99999999999999',None)])
def test_decimal_money(value,expected):
    assert money(value)==expected


def test_demo_native_fields():
    path=config.ROOT/'data/demo/demo-01.pdf'
    page,image,boxes,engine=next(read_pages(path.read_bytes(),'.pdf'))
    doc=parse(boxes,engine)
    assert doc['invoice_number']=='99000000000000000001'
    assert doc['invoice_date']=='2026-11-19'
    assert doc['total']=='8480.00'
    assert doc['subtotal']=='8000.00'
    assert doc['tax_amount']=='480.00'
    assert doc['tax_rates']=='6%'
    assert doc['buyer_name']=='青禾创新(教学示例)有限公司'
    assert doc['seller_name']=='松云数字科技(示例)有限公司'
    assert validate(doc)==[]
    assert all(0<=coordinate<=1 for b in boxes for coordinate in b['rect'])


def test_document_anomaly_is_not_silently_repaired():
    path=config.ROOT/'data/demo/demo-11.pdf'
    _,_,boxes,engine=next(read_pages(path.read_bytes(),'.pdf'))
    doc=parse(boxes,engine)
    assert doc['total']=='268.00' and doc['tax_amount']=='40.83'
    assert any('10.00' in issue['message'] for issue in validate(doc))


def test_provided_regression():
    reference=config.ROOT/'tests/provided_expectations.json'
    if not reference.exists():pytest.skip('Private reference data excluded from public source')
    expected=json.loads(reference.read_text(encoding='utf-8'))
    assert len(expected)==23
    for name,fields in expected.items():
        path=config.ROOT/'data/provided'/name
        if not path.exists():pytest.skip('提供的私人样本未包含在当前分发包')
        pages=list(read_pages(path.read_bytes(),'.pdf'))
        assert len(pages)==1
        _,_,boxes,engine=pages[0]
        assert engine=='pdf_text'
        doc=parse(boxes,engine)
        for field,value in fields.items():
            assert doc[field]==value,(name,field,doc[field],value)


def test_masked_tax_remains_unknown():
    # Lock the exact masked-tax sample: case-insensitive filesystems (Windows/macOS)
    # make glob('DZFP_*.pdf') also match lowercase dzfp_ samples with visible tax.
    path=config.ROOT/'data/provided'/'DZFP_26367000000002725372.pdf'
    if not path.exists():pytest.skip('Private samples not provided')
    _,_,boxes,engine=next(read_pages(path.read_bytes(),'.pdf'))
    doc=parse(boxes,engine)
    assert doc['tax_amount'] is None
    assert any(i['field']=='tax_amount' for i in validate(doc))


def test_missing_fields_and_legacy_code():
    d=parse([])
    assert d['invoice_number']=='' and d['total'] is None
    assert len([i for i in validate(d) if i['severity']=='error'])>=7
    d.update(invoice_number='00000001')
    assert any(i['field']=='invoice_code' for i in validate(d))


def test_money_tolerance_is_decimal():
    d={'invoice_number':'12345678901234567890','invoice_date':'2026-01-01','buyer_name':'甲','seller_name':'乙',
       'subtotal':'0.10','tax_amount':'0.20','total':'0.30'}
    assert validate(d,tolerance='0.00')==[]
    d['total']='0.32'
    assert validate(d,tolerance='0.02')==[]
    assert any(i['field']=='total' for i in validate(d,tolerance='0.01'))


@pytest.mark.ocr
def test_real_onnx_image_recognition():
    path=config.ROOT/'data/demo/demo-12.png'
    _,_,boxes,engine=next(read_pages(path.read_bytes(),'.png'))
    doc=parse(boxes,engine)
    assert engine=='ctpn_crnn_ctc' and len(boxes)>15
    assert doc['invoice_number']=='99000000000000000012'
    assert doc['invoice_date']=='2026-11-13'
    assert doc['total']=='186.00' and doc['tax_amount']=='10.53'
    assert doc['tax_rates']=='6%'
    assert doc['confidence']>.8
