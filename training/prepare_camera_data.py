"""Real paper crop supervision from official TRAIN IDs 0001-0025 only."""
import argparse,json,sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from vatid_data import fetch_subset,annotations
from backend.app.classic_ocr.pipeline import prepare_crop

def main():
    p=argparse.ArgumentParser();p.add_argument('--downloads',type=Path,default=ROOT/'evaluation/vatid-training');a=p.parse_args();fetch_subset(a.downloads,1,25,'train','TRAINING 0001-0020 and development 0021-0025 only')
    folder=ROOT/'training/camera-data';folder.mkdir(parents=True,exist_ok=True);charset=set((ROOT/'models/classic/charset_cn.txt').read_text(encoding='utf-8'));splits={'train':[],'validation':[]}
    for i in range(1,26):
        name=f'vat_{i:04d}';im=Image.open(a.downloads/f'{name}.jpg').convert('L')
        for index,(text,rect) in enumerate(annotations(a.downloads/f'{name}_textGT.txt')):
            x,y,xx,yy=map(int,rect)
            if yy-y>1.5*(xx-x) or any(c not in charset for c in text):continue
            filename=f'{name}-{index:02d}.png';Image.fromarray(prepare_crop(np.array(im.crop((x,y,xx+1,yy+1))))).save(folder/filename)
            splits['train' if i<=20 else 'validation'].append({'file':filename,'text':text,'source':name,'source_kind':'VATID official TRAIN split human keyword annotation'})
    for key in splits:
        splits[key]+=[{**row,'file':'../data/'+row['file']} for row in json.loads((ROOT/f'training/data/{key}.json').read_text())]
        (folder/f'{key}.json').write_text(json.dumps(splits[key],ensure_ascii=False,indent=2),encoding='utf-8')
    record={'sources':json.loads((a.downloads/'download-manifest.json').read_text()),'counts':{k:len(v) for k,v in splits.items()},'camera_training_ids':list(range(1,21)),'camera_development_ids':list(range(21,26)),'independent_0081_0100_used':False};(folder/'manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(record['counts'],flush=True)
if __name__=='__main__':main()
