"""Reproducible application evaluation; not a general OCR accuracy benchmark."""
import io
import json
import sys
import time
from pathlib import Path

import fitz
from PIL import Image, ImageEnhance

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.parser import parse,validate
from backend.app.reader import read_pages


def evaluate():
    expect=json.loads((ROOT/'tests/provided_expectations.json').read_text(encoding='utf-8'))
    report={'scope':'固定附件回归与同源栅格衍生样本，不代表独立测试集准确率','native':[],'ocr':[]}
    for name,truth in expect.items():
        path=ROOT/'data/provided'/name
        if not path.exists():continue
        start=time.monotonic();_,_,boxes,engine=next(read_pages(path.read_bytes(),'.pdf'));doc=parse(boxes,engine)
        report['native'].append({'file':name,'engine':engine,'seconds':round(time.monotonic()-start,3),
                                 'matches':{key:doc[key]==v for key,v in truth.items()},
                                 'tax_is_explicit':doc['tax_amount'] is not None,'issues':validate(doc)})
    names=list(expect)
    cases=[(names[0],'clean_png'),(names[1],'jpeg_quality_65'),(names[3],'rotate_2_degrees'),(names[-1],'grayscale')]
    for name,variant in cases:
        path=ROOT/'data/provided'/name
        if not path.exists():continue
        pdf=fitz.open(path);page=pdf[0];pix=page.get_pixmap(matrix=fitz.Matrix(2.4,2.4),alpha=False);pdf.close()
        img=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        if variant=='rotate_2_degrees':img=img.rotate(2,expand=True,fillcolor='white')
        if variant=='grayscale':img=img.convert('L').convert('RGB')
        ext='.jpg' if variant=='jpeg_quality_65' else '.png';buffer=io.BytesIO();img.save(buffer,'JPEG' if ext=='.jpg' else 'PNG',quality=65)
        start=time.monotonic();_,_,boxes,engine=next(read_pages(buffer.getvalue(),ext));doc=parse(boxes,engine)
        report['ocr'].append({'source_file':name,'variant':variant,'engine':engine,'seconds':round(time.monotonic()-start,3),
                              'matches':{key:doc[key]==v for key,v in expect[name].items()},
                              'observed':{key:doc[key] for key in expect[name]},
                              'text_mean_score':doc['confidence'],'issues':validate(doc)})
    target=ROOT/'docs'/'evaluation-results.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    total=sum(len(x['matches']) for group in ['native','ocr'] for x in report[group])
    passed=sum(sum(x['matches'].values()) for group in ['native','ocr'] for x in report[group])
    print(json.dumps({'native_files':len(report['native']),'derived_ocr_files':len(report['ocr']),'matched_anchors':passed,'total_anchors':total,'output':str(target)},ensure_ascii=False))
    return report


if __name__=='__main__':evaluate()
