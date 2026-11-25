"""Actual original CTPN -> 7-Conv/2-BiLSTM CRNN -> explicit CTC.

No import, invocation or fallback to PP-OCR exists in this module.
"""
import hashlib,json,math,re,threading,time
from pathlib import Path
import cv2
import numpy as np
from .. import config
from .ctc import greedy_ctc
from .ctpn_postprocess import CTPNPostprocessor
_instance=None
_lock=threading.Lock()

def normalize_exposure(array):
    low,high=np.percentile(array,[2,96])
    if high>=235 or high-low<12:return array
    return np.clip((array.astype(np.float32)-low)*255/(high-low),0,255).astype(np.uint8)

def prepare_crop(gray):
    gray=normalize_exposure(gray)
    _,mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    if gray.shape[1]>4*gray.shape[0]:
        rows=(mask>0).mean(axis=1)>.75;gray=gray.copy();gray[rows]=255
        _,mask=cv2.threshold(gray,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    active=(mask>0).sum(axis=1)>max(1,gray.shape[1]*.003);groups=[];start=None
    for i,on in enumerate([*active,False]):
        if on and start is None:start=i
        if not on and start is not None:groups.append((start,i));start=None
    if len(groups)>1:
        main=max(groups,key=lambda g:g[1]-g[0]);others=[b-a for a,b in groups if (a,b)!=main]
        if main[1]-main[0]>=10 and max(others,default=0)<(main[1]-main[0])*.4:
            gray=gray[main[0]:main[1]];mask=mask[main[0]:main[1]]
    ys,xs=np.where(mask>0)
    if len(xs):
        gray=gray[ys.min():ys.max()+1,xs.min():xs.max()+1];mask=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
        empty=~(mask>0).any(axis=0);keep=np.ones(gray.shape[1],dtype=bool);start=0
        while start<len(empty):
            if not empty[start]:start+=1;continue
            end=start+1
            while end<len(empty) and empty[end]:end+=1
            if end-start>max(8,gray.shape[0]*.6):
                keep[start+max(2,round(gray.shape[0]*.18)):end]=False
            start=end
        gray=gray[:,keep]
    return cv2.copyMakeBorder(gray,2,2,2,2,cv2.BORDER_CONSTANT,value=255)

def available():
    import importlib.util
    folder=config.ROOT/'models/classic'
    return all((folder/n).is_file() for n in ['ctpn.onnx','crnn_cn.onnx','charset_cn.txt','manifest.json']) and importlib.util.find_spec('onnxruntime') is not None

class ClassicOCR:
    def __init__(self):
        import onnxruntime as ort
        ort.disable_telemetry_events();self.folder=config.ROOT/'models/classic'
        self.manifest=json.loads((self.folder/'manifest.json').read_text(encoding='utf-8'))
        for item in self.manifest['files']:
            if hashlib.sha256((self.folder/item['file']).read_bytes()).hexdigest()!=item['sha256']:
                raise RuntimeError('指定网络权重校验失败：'+item['file'])
        options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
        self.detector=ort.InferenceSession(str(self.folder/'ctpn.onnx'),options,providers=['CPUExecutionProvider'])
        self.recognizer=ort.InferenceSession(str(self.folder/'crnn_cn.onnx'),options,providers=['CPUExecutionProvider'])
        self.charset=(self.folder/'charset_cn.txt').read_text(encoding='utf-8');self.input=self.recognizer.get_inputs()[0].name;self.post=CTPNPostprocessor()
    def detect(self,image):
        rgb=np.asarray(image.convert('RGB'));height,width=rgb.shape[:2]
        scale=min(1000/min(height,width),2000/max(height,width));h,w=max(16,round(height*scale)),max(16,round(width*scale))
        bgr=cv2.resize(normalize_exposure(rgb)[:,:,::-1],(w,h)).astype(np.float32)
        ph,pw=math.ceil(h/16)*16,math.ceil(w/16)*16;data=np.full((ph,pw,3),255,np.float32);data[:h,:w]=bgr
        data-=np.array([102.9801,115.9465,122.7717],np.float32)
        prob,delta=self.detector.run(None,{'image':data[None].transpose(0,3,1,2).copy()})
        proposals,scores=self.post.get_proposals(prob[0],delta[0],[h,w,1])
        lines=self.post.get_detections(proposals,scores[:,None],[h,w]);result=[]
        for line in lines:
            pts=line[:8].reshape(4,2)/np.array([w/width,h/height]);x0,y0=pts.min(0);x1,y1=pts.max(0)
            result.append({'rect':[float(x0),float(y0),float(x1),float(y1)],'score':float(line[8])})
        return result
    def recognize_crop(self,image,rect):
        rgb=np.asarray(image.convert('RGB'));height,width=rgb.shape[:2];x0,y0,x1,y1=rect
        crop=rgb[max(0,int(y0)):min(height,math.ceil(y1)+1),max(0,int(x0)):min(width,math.ceil(x1)+1)]
        if min(crop.shape[:2],default=0)<2:return '',0.,[]
        gray=prepare_crop(cv2.cvtColor(crop,cv2.COLOR_RGB2GRAY))
        def predict(factor):
            width=max(8,min(1600,round(gray.shape[1]/gray.shape[0]*32*factor)));resized=cv2.resize(gray,(width,32),interpolation=cv2.INTER_CUBIC)
            blob=((resized.astype(np.float32)/255-.588)/.193)[None,None]
            return greedy_ctc(self.recognizer.run(None,{self.input:blob})[0],self.charset)
        result=predict(160/280)
        # Select only text actually predicted by this CRNN+CTC, never insert
        # missing digits/decimal dots. Retry invalid labelled invoice numbers.
        pattern=r'(?:发票号码|票据号码)[：: ]*(?:\d{20}|\d{8})(?!\d)'
        if re.search(r'发票号码|票据号码',result[0]) and not re.search(pattern,result[0]):
            valid=[r for r in [predict(f) for f in [.65,.7,.85]] if re.search(pattern,r[0])]
            if valid:result=max(valid,key=lambda r:r[1])
        if re.fullmatch(r'[￥¥]-?\d{3,}',result[0]):
            valid=[r for r in [predict(f) for f in [.7,.85]] if re.fullmatch(r'[￥¥]-?\d+\.\d{2}',r[0]) and r[1]>=.65]
            if valid:result=max(valid,key=lambda r:r[1])
        return result
    def __call__(self,image):
        start=time.monotonic();w,h=image.size;detections=self.detect(image);det_time=time.monotonic()-start;boxes=[]
        for d in detections:
            rect=d['rect'];text,score,path=self.recognize_crop(image,rect)
            if text:boxes.append({'id':f'b{len(boxes)}','text':text,'score':round(score,4),'detection_score':round(d['score'],4),'rect':[round(rect[0]/w,6),round(rect[1]/h,6),round(rect[2]/w,6),round(rect[3]/h,6)],'angle':0.,'ctc_steps':len(path)})
        image.info.update(ocr_pipeline='ctpn_crnn_ctc',model_version=self.manifest['version'],inference_seconds={'detection':round(det_time,3),'recognition':round(time.monotonic()-start-det_time,3)})
        return boxes

def run(image):
    global _instance
    if not available():raise RuntimeError('CTPN/CRNN 权重或依赖不齐全；不会自动使用 PP-OCR。')
    with _lock:
        if _instance is None:_instance=ClassicOCR()
        return _instance(image)
