"""Actual designated-network keyword evaluation. Never invokes PDF or PP-OCR."""
import argparse,hashlib,json,platform,re,sys,time,unicodedata
from datetime import datetime,timezone
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from backend.app.classic_ocr.pipeline import ClassicOCR
from vatid_data import annotations

def normalize(text):return re.sub(r'[\W_]+','',unicodedata.normalize('NFKC',text))
def edit_distance(a,b):
    previous=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        current=[i]
        for j,y in enumerate(b,1):current.append(min(current[-1]+1,previous[j]+1,previous[j-1]+(x!=y)))
        previous=current
    return previous[-1]
def coverage(gt,box):
    x,y,xx,yy=gt;a,b,c,d=box
    return max(0,min(xx,c)-max(x,a))*max(0,min(yy,d)-max(y,b))/max((xx-x)*(yy-y),1)

def main():
    p=argparse.ArgumentParser();p.add_argument('--dataset',type=Path,required=True);p.add_argument('--output',type=Path,default=ROOT/'docs/independent-classic-results.json');a=p.parse_args()
    selection=json.loads((a.dataset/'selection.json').read_text());model=ClassicOCR();start=time.monotonic();images=[];inputs=[]
    totals={kind:{'keywords':0,'covered':0,'spotting_matches':0,'crop_exact':0,'crop_edits':0,'characters':0} for kind in ['all','horizontal','vertical']}
    for identifier in selection['samples']:
        image_path=a.dataset/f'{identifier}.jpg';truth_path=a.dataset/f'{identifier}_textGT.txt';image=Image.open(image_path).convert('RGB');w,h=image.size;t=time.monotonic();boxes=model(image)
        assert image.info['ocr_pipeline']=='ctpn_crnn_ctc';detections=[([b['rect'][0]*w,b['rect'][1]*h,b['rect'][2]*w,b['rect'][3]*h],normalize(b['text'])) for b in boxes];rows=[]
        for expected,rect in annotations(truth_path):
            target=normalize(expected);pred,_,_=model.recognize_crop(image,rect);pred=normalize(pred);covered=[txt for box,txt in detections if coverage(rect,box)>=.8];spotted=any(target in txt for txt in covered)
            kind='vertical' if rect[3]-rect[1]>1.5*(rect[2]-rect[0]) else 'horizontal';error=edit_distance(target,pred)
            for key in ['all',kind]:
                z=totals[key];z['keywords']+=1;z['covered']+=bool(covered);z['spotting_matches']+=spotted;z['crop_exact']+=pred==target;z['crop_edits']+=error;z['characters']+=len(target)
            rows.append({'ground_truth':target,'crop_prediction':pred,'orientation':kind,'covered':bool(covered),'spotted':spotted,'crop_edits':error})
        inputs.append({'id':identifier,'image_sha256':hashlib.sha256(image_path.read_bytes()).hexdigest(),'annotation_sha256':hashlib.sha256(truth_path.read_bytes()).hexdigest()})
        images.append({'id':identifier,'engine':image.info['ocr_pipeline'],'seconds':round(time.monotonic()-t,3),'detected_lines':len(boxes),'keywords':rows});print(identifier,'keywords',len(rows),'covered',sum(r['covered'] for r in rows),'spotted',sum(r['spotted'] for r in rows),flush=True)
    for z in totals.values():
        n=max(z['keywords'],1);z.update(keyword_coverage_recall=z['covered']/n,keyword_spotting_recall=z['spotting_matches']/n,crop_exact_accuracy=z['crop_exact']/n,crop_cer=z['crop_edits']/max(z['characters'],1))
    record={'created_at':datetime.now(timezone.utc).isoformat(),'engine':'ctpn_crnn_ctc','model_version':model.manifest['version'],'models':model.manifest['files'],'manifest_sha256':hashlib.sha256((model.folder/'manifest.json').read_bytes()).hexdigest(),'implementation_sha256':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['backend/app/classic_ocr/pipeline.py','backend/app/classic_ocr/ctc.py','backend/app/classic_ocr/ctpn_postprocess.py','scripts/evaluate_classic.py','scripts/vatid_data.py']},'dataset':selection,'images_count':len(images),'inputs':inputs,'metrics':totals,'image_results':images,'seconds':round(time.monotonic()-start,3),'python':platform.python_version(),'platform':platform.platform(),'scope':'Partial KEYWORD annotations, not full invoice transcription or financial field accuracy','protocol':{'normalization':'NFKC and removal of punctuation and whitespace on both sides, because the keyword annotations omit printed punctuation','coverage_threshold':.8,'spotting':'keyword occurs in a predicted line covering >=80% of the GT rectangle','crop_recognition':'GT crop CRNN+CTC component metric, separate from end-to-end spotting','ppocr_used':False,'pdf_text_used':False,'test_data_used_for_project_training_or_tuning':False},'limitations':['Small invoice-group-disjoint subset; repeated photographs of one invoice are correlated and cannot establish broad generalization.','Upstream pretraining data is incompletely documented; upstream overlap cannot be ruled out.','Vertical text reported separately; the classic recognizer is horizontal.','No global precision/F1 because other invoice text is not annotated.']}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({'metrics':totals,'seconds':record['seconds'],'output':str(a.output)},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
