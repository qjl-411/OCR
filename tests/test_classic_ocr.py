"""Meaningful algorithm contracts and prevention of silent model substitution."""
import numpy as np
import pytest
from PIL import Image
from backend.app import config,reader
from backend.app.classic_ocr.ctc import greedy_ctc

def test_ctc_order_repeats_blank_and_literal_hyphen():
    labels=[1,1,0,1,2,2,0,3];logits=np.full((len(labels),1,4),-30.,dtype=np.float32)
    for i,label in enumerate(labels):logits[i,0,label]=0
    text,score,path=greedy_ctc(logits,'甲-乙');assert text=='甲甲-乙' and score==1 and path==labels
    assert greedy_ctc(np.array([[[0,-30,-30,-30]]]),'甲-乙')[0]==''

def test_classic_failure_cannot_fall_back_to_ppocr(monkeypatch):
    from backend.app.classic_ocr import pipeline
    def missing(_):raise RuntimeError('missing required network')
    def forbidden(_):raise AssertionError('Unexpected PP-OCR fallback')
    monkeypatch.setattr(pipeline,'run',missing);monkeypatch.setattr(reader,'ppocr',forbidden)
    with pytest.raises(RuntimeError,match='missing required network'):reader.recognize_image(Image.new('RGB',(100,100)),pipeline='classic')

def test_force_pdf_path_excludes_pdf_text(monkeypatch):
    calls=[]
    def fake(image,pipeline='classic'):
        calls.append(pipeline);return image,[{'id':'network','text':'NETWORK ONLY','score':.8,'rect':[.1,.1,.8,.2]}]
    monkeypatch.setattr(reader,'recognize_image',fake)
    _,_,boxes,engine=next(reader.read_pages((config.ROOT/'data/demo/demo-01.pdf').read_bytes(),'.pdf',pipeline='classic',force_ocr=True))
    assert calls==['classic'] and engine=='ctpn_crnn_ctc' and [b['text'] for b in boxes]==['NETWORK ONLY']

def test_currency_fallback_requires_read_values_and_sum_consistency():
    from backend.app.parser import parse
    def b(i,text,x,y):return {'id':str(i),'text':text,'score':.9,'rect':[x,y,x+.15,y+.03]}
    boxes=[b(0,'￥175.47',.6,.6),b(1,'￥10.53',.8,.6),b(2,'（小写）￥186.00',.5,.7)]
    assert parse(boxes)['tax_amount']=='10.53'
    boxes[1]['text']='￥1053';assert parse(boxes)['tax_amount'] is None
    boxes[1]['text']='￥11.53';assert parse(boxes)['tax_amount'] is None
    assert parse([b(4,'175.476%10.53',.5,.5)])['tax_rates']=='6%'
