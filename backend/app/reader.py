import importlib.util
import io
import json
import math
import statistics
import threading
from pathlib import Path

import fitz
from PIL import Image, ImageOps

from . import config

_engine = None
_lock = threading.Lock()


def ppocr_available():
    return importlib.util.find_spec('rapidocr_onnxruntime') is not None


def ppocr(image):
    global _engine
    if not ppocr_available():
        raise RuntimeError('尚未安装 OCR 依赖，请运行启动脚本安装 requirements.txt 后重试。')
    import numpy as np
    import onnxruntime as ort
    ort.disable_telemetry_events()
    from rapidocr_onnxruntime import RapidOCR
    with _lock:
        if _engine is None:
            models = config.ROOT / 'models'
            kwargs = {'intra_op_num_threads': 2, 'inter_op_num_threads': 1,
                      'det_limit_side_len': 1600, 'det_limit_type': 'max'}
            if (models / 'ch_PP-OCRv4_det_infer.onnx').exists():
                kwargs.update(det_model_path=str(models / 'ch_PP-OCRv4_det_infer.onnx'),
                              rec_model_path=str(models / 'ch_PP-OCRv4_rec_infer.onnx'),
                              cls_model_path=str(models / 'ch_ppocr_mobile_v2.0_cls_infer.onnx'))
            _engine = RapidOCR(**kwargs)
        # RapidOCR expects OpenCV BGR input for ndarray.
        result, _ = _engine(np.asarray(image)[:, :, ::-1].copy())
    w,h = image.size
    return [{'id':f'b{i}', 'text':r[1], 'score':round(float(r[2]),4),
             'angle':round(math.degrees(math.atan2(r[0][1][1]-r[0][0][1],r[0][1][0]-r[0][0][0])),3),
             'rect':[round(min(p[0] for p in r[0])/w,6), round(min(p[1] for p in r[0])/h,6),
                     round(max(p[0] for p in r[0])/w,6), round(max(p[1] for p in r[0])/h,6)]}
            for i,r in enumerate(result or [])]


def recognize_image(image,pipeline='classic'):
    if pipeline=='classic':
        from .classic_ocr.pipeline import run
        return image,run(image)
    if pipeline!='ppocr':raise ValueError('未知识别流水线')
    image.info['ocr_pipeline']='ppocr'
    boxes=ppocr(image)
    angles=[b['angle'] for b in boxes if len(b['text'])>=5
            and b['rect'][2]-b['rect'][0]>3*(b['rect'][3]-b['rect'][1]) and abs(b['angle'])<10]
    if len(angles)>=5:
        angle=statistics.median(angles)
        if .8<=abs(angle)<=8:
            image=image.rotate(angle,expand=True,fillcolor='white')
            boxes=ppocr(image)
            image.info['deskew_degrees']=round(angle,2)
    return image,boxes


def read_pages(data: bytes, extension: str, pipeline='classic', force_ocr=False):
    if extension == '.pdf':
        try:
            document = fitz.open(stream=data, filetype='pdf')
        except Exception as e:
            raise ValueError('无法打开 PDF，文件可能损坏。') from e
        with document:
            if document.is_encrypted:
                raise ValueError('不支持加密 PDF，请先解除密码。')
            if not 1 <= len(document) <= config.MAX_PAGES:
                raise ValueError(f'单个 PDF 支持 1–{config.MAX_PAGES} 页，请拆分后导入。')
            for index,page in enumerate(document):
                w,h = page.rect.width,page.rect.height
                if w<=0 or h<=0 or max(w,h)>15000:
                    raise ValueError('PDF 页面尺寸异常。')
                scale = min(2.3, 2200/max(w,h))
                pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
                image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
                boxes=[]
                for block in page.get_text('dict')['blocks']:
                    for line in block.get('lines',[]):
                        text=''.join(span['text'] for span in line['spans']).strip()
                        x0,y0,x1,y1=line['bbox']
                        if text and 0<=x0<w and 0<=y0<h:
                            boxes.append({'id':f'b{len(boxes)}','text':text,'score':1.0,
                                          'rect':[round(x0/w,6),round(y0/h,6),round(min(x1,w)/w,6),round(min(y1,h)/h,6)]})
                useful=''.join(b['text'] for b in boxes)
                engine='pdf_text'
                if force_ocr or len(useful)<40 or useful.count('\ufffd')>len(useful)*.1:
                    image,boxes=recognize_image(image,pipeline); engine='ctpn_crnn_ctc' if pipeline=='classic' else 'ppocr'
                yield index+1,image,boxes,engine
    else:
        try:
            with Image.open(io.BytesIO(data)) as original:
                if original.width*original.height>40_000_000:
                    raise ValueError('图片超过 4000 万像素，请缩小后导入。')
                image=ImageOps.exif_transpose(original).convert('RGB')
        except Exception as e:
            raise ValueError('无法打开图片，文件损坏或像素过大。') from e
        image.thumbnail((2600,2600))
        image,boxes=recognize_image(image,pipeline)
        yield 1,image,boxes,'ctpn_crnn_ctc' if pipeline=='classic' else 'ppocr'


def available():
    from .classic_ocr.pipeline import available as classic_available
    return bool(classic_available())

def model_version(pipeline):
    path=config.ROOT/('models/classic/manifest.json' if pipeline=='classic' else 'models/manifest.json')
    return json.loads(path.read_text(encoding='utf-8')).get('version','ppocr-v4') if path.exists() else 'missing'
