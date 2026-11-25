"""Export the real trained checkpoint and compare ONNX against PyTorch."""
import argparse,hashlib,json,sys
from pathlib import Path
import numpy as np
import torch,onnx,onnxruntime as ort
ort.disable_telemetry_events()
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.crnn_model import CRNN

def main():
    p=argparse.ArgumentParser();p.add_argument('--checkpoint',required=True);a=p.parse_args();torch.set_num_threads(2)
    charset=(ROOT/'models/classic/charset_cn.txt').read_text(encoding='utf-8');model=CRNN(len(charset)+1).eval();state=torch.load(a.checkpoint,map_location='cpu',weights_only=True);model.load_state_dict(state.get('state_dict',state),strict=True)
    path=ROOT/'models/classic/crnn_cn.onnx';torch.onnx.export(model,torch.zeros(1,1,32,160),str(path),input_names=['input'],output_names=['log_probs'],dynamic_axes={'input':{3:'width'},'log_probs':{0:'time'}},opset_version=17,dynamo=False)
    options=ort.SessionOptions();options.intra_op_num_threads=2;session=ort.InferenceSession(str(path),options,providers=['CPUExecutionProvider']);results=[];rng=torch.Generator().manual_seed(20261120)
    for width in [100,160,320,640]:
        data=torch.randn(1,1,32,width,generator=rng)
        with torch.inference_mode():expected=model(data).numpy()
        actual=session.run(None,{'input':data.numpy()})[0];error=float(np.max(np.abs(expected-actual)));assert error<.002;results.append({'width':width,'max_log_probability_error':error})
    graph=onnx.load(path);counts={name:sum(n.op_type==name for n in graph.graph.node) for name in ['Conv','LSTM','LogSoftmax']};assert counts=={'Conv':7,'LSTM':2,'LogSoftmax':1}
    assert all(any(x.name=='direction' and x.s==b'bidirectional' for x in n.attribute) for n in graph.graph.node if n.op_type=='LSTM')
    record={'checkpoint_sha256':hashlib.sha256(Path(a.checkpoint).read_bytes()).hexdigest(),'onnx_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'trained_steps_current_stage':state.get('step'),'vocabulary_characters':len(charset),'classes_including_blank':len(charset)+1,'architecture':'7 Conv + 2 bidirectional LSTM + explicit CTC','onnx_operators':counts,'parity':results}
    (ROOT/'docs/crnn-export-results.json').write_text(json.dumps(record,indent=2));print(json.dumps(record),flush=True)
if __name__=='__main__':main()
