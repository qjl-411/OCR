"""Real CPU/CUDA CRNN fine-tuning with JSONL loss and checkpoint provenance."""
import argparse,hashlib,json,random,sys,time
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import torch
from PIL import Image,ImageEnhance,ImageFilter
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.crnn_model import CRNN
from backend.app.classic_ocr.ctc import greedy_ctc

def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);p.add_argument('--steps',type=int,default=400);p.add_argument('--batch-size',type=int,default=8);p.add_argument('--device',default='cpu');p.add_argument('--threads',type=int,default=4);p.add_argument('--data',type=Path,default=ROOT/'training/data');p.add_argument('--run-name',default='required-crnn');a=p.parse_args()
    torch.set_num_threads(a.threads);torch.manual_seed(20261120);np.random.seed(20261120);random.seed(20261120)
    folder=a.data;output=ROOT/'training/runs'/a.run_name;output.mkdir(parents=True,exist_ok=True)
    charset=(ROOT/'models/classic/charset_cn.txt').read_text(encoding='utf-8');ids={c:i+1 for i,c in enumerate(charset)};model=CRNN(len(charset)+1)
    state=torch.load(a.checkpoint,map_location='cpu',weights_only=True);model.load_state_dict(state.get('state_dict',state),strict=True);model.to(a.device)
    for parameter in model.cnn.parameters():parameter.requires_grad=False
    optimizer=torch.optim.Adam(model.rnn.parameters(),lr=.00015);criterion=torch.nn.CTCLoss(blank=0,zero_infinity=True)
    train=json.loads((folder/'train.json').read_text());validation=json.loads((folder/'validation.json').read_text());cache={r['file']:Image.open(folder/r['file']).convert('L').copy() for r in train+validation}
    def tensor_for(row,augment=False):
        image=cache[row['file']].copy()
        if augment:
            image=ImageEnhance.Contrast(image).enhance(random.uniform(.8,1.3))
            if random.random()<.2:image=image.filter(ImageFilter.GaussianBlur(random.uniform(0,.4)))
        factor=random.uniform(.52,.7) if augment else 160/280;width=max(12,min(720,round(image.width/image.height*32*factor)))
        minimum=len(row['text'])+sum(x==y for x,y in zip(row['text'],row['text'][1:]));width=max(width,(minimum+1)*4)
        image=image.resize((width,32),Image.Resampling.BICUBIC);return torch.from_numpy(((np.asarray(image).astype('float32')/255-.588)/.193)[None]),width
    def batch(rows):
        tensors=[tensor_for(r,True) for r in rows];images=torch.full((len(rows),1,32,max(w for _,w in tensors)),(1-.588)/.193)
        for i,(tensor,w) in enumerate(tensors):images[i,:,:,:w]=tensor
        return images.to(a.device),torch.tensor([ids[c] for r in rows for c in r['text']],dtype=torch.long,device=a.device),torch.tensor([w//4+1 for _,w in tensors]),torch.tensor([len(r['text']) for r in rows])
    def check():
        subset=validation[:40 if folder.name=='data' else 100]+[r for r in validation if r['source_kind']=='synthetic'][:20];matches=edits=characters=0;model.eval()
        with torch.inference_mode():
            for row in subset:
                image,_=tensor_for(row);text,_,_=greedy_ctc(model(image[None].to(a.device)).cpu().numpy(),charset);target=row['text'];matches+=text==target;characters+=len(target);prev=list(range(len(text)+1))
                for j,c in enumerate(target,1):
                    curr=[j]
                    for k,d in enumerate(text,1):curr.append(min(curr[-1]+1,prev[k]+1,prev[k-1]+(c!=d)))
                    prev=curr
                edits+=prev[-1]
        return {'samples':len(subset),'exact_matches':matches,'cer':edits/max(characters,1),'scope':'DEVELOPMENT crops, not independent whole-invoice accuracy'}
    meta={'started_at':datetime.now(timezone.utc).isoformat(),'checkpoint_sha256':hashlib.sha256(Path(a.checkpoint).read_bytes()).hexdigest(),'run_name':a.run_name,'training_data_manifest_sha256':hashlib.sha256((folder/'manifest.json').read_bytes()).hexdigest(),'device':a.device,'torch':torch.__version__,'threads':a.threads,'steps':a.steps,'batch_size':a.batch_size,'architecture':'7 Conv + 2 bidirectional LSTM + CTC','train_samples':len(train),'validation_samples':len(validation),'cnn_frozen':True,'loss':'torch.nn.CTCLoss','independent_test_data_used':False,'initial_validation':check(),'parent_completed_steps':state.get('step',0)}
    (output/'run.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print('INITIAL',meta['initial_validation'],flush=True);start=time.monotonic()
    with (output/'metrics.jsonl').open('w') as log:
        for step in range(1,a.steps+1):
            model.train();model.cnn.eval();images,targets,lengths,target_lengths=batch(random.sample(train,a.batch_size));optimizer.zero_grad(set_to_none=True);loss=criterion(model(images),targets,lengths,target_lengths);loss.backward();torch.nn.utils.clip_grad_norm_(model.rnn.parameters(),5);optimizer.step()
            row={'step':step,'loss':float(loss.detach().cpu()),'elapsed_seconds':round(time.monotonic()-start,3)};log.write(json.dumps(row)+'\n');log.flush()
            if step%100==0:print(row,flush=True);torch.save({'state_dict':model.state_dict(),'step':step},output/'latest.pth')
    meta.update(final_validation=check(),elapsed_seconds=time.monotonic()-start,finished_at=datetime.now(timezone.utc).isoformat(),completed_steps=a.steps,cumulative_project_finetuning_steps=meta['parent_completed_steps']+a.steps)
    torch.save({'state_dict':model.state_dict(),'step':a.steps,'source_checkpoint_sha256':meta['checkpoint_sha256']},output/'finetuned.pth');meta['output_sha256']=hashlib.sha256((output/'finetuned.pth').read_bytes()).hexdigest();(output/'run.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print('FINISHED',meta['final_validation'],'seconds',meta['elapsed_seconds'],flush=True)
if __name__=='__main__':main()
