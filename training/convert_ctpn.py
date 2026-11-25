"""Convert original CTPN frozen-graph weights; verify raw outputs at 3 sizes."""
import argparse,hashlib,json,sys,os
from pathlib import Path
os.environ['OPT_OUT_TRACKING']='1'
import numpy as np
import openvino as ov
import onnxruntime as ort
import torch
ort.disable_telemetry_events()
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from training.ctpn_model import CTPN

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();torch.set_num_threads(2)
    core=ov.Core();source=core.read_model(a.source);source.reshape([1,-1,-1,3])
    reference=core.compile_model(source,'CPU',{'INFERENCE_NUM_THREADS':2,'INFERENCE_PRECISION_HINT':'f32'})
    nodes=source.get_ordered_ops();constants={n.get_friendly_name():np.array(n.get_data()) for n in nodes if n.get_type_name()=='Constant'}
    model=CTPN().eval();convs=[n for n in nodes if n.get_type_name()=='Convolution'];assert len(convs)==14
    with torch.no_grad():
        for layer,node in zip(model.convs,convs):
            layer.weight.copy_(torch.from_numpy(np.array(node.input_value(1).get_node().get_data())))
            add=next(x.get_node() for x in node.output(0).get_target_inputs() if x.get_node().get_type_name()=='Add')
            bias=next(add.input_value(i).get_node() for i in range(2) if add.input_value(i).get_node().get_type_name()=='Constant')
            layer.bias.copy_(torch.from_numpy(np.array(bias.get_data()).reshape(-1)))
        order=np.concatenate([np.arange(0,128),np.arange(256,384),np.arange(128,256),np.arange(384,512)])
        for direction,suffix in [('fw',''),('bw','_reverse')]:
            prefix=f'lstm_o/bidirectional_rnn/{direction}/lstm_cell/';kernel=constants[prefix+'kernel'];bias=constants[prefix+'bias'][order].copy();bias[128:256]+=1
            getattr(model.brnn,'weight_ih_l0'+suffix).copy_(torch.from_numpy(kernel[:512,:].T[order].copy()))
            getattr(model.brnn,'weight_hh_l0'+suffix).copy_(torch.from_numpy(kernel[512:,:].T[order].copy()))
            getattr(model.brnn,'bias_ih_l0'+suffix).copy_(torch.from_numpy(bias));getattr(model.brnn,'bias_hh_l0'+suffix).zero_()
        for layer,prefix in [(model.context,'lstm_o'),(model.classifier,'rpn_cls_score'),(model.regression,'rpn_bbox_pred')]:
            layer.weight.copy_(torch.from_numpy(constants[prefix+'/weights'].T.copy()));layer.bias.copy_(torch.from_numpy(constants[prefix+'/biases'].copy()))
    path=ROOT/'models/classic/ctpn.onnx'
    torch.onnx.export(model,torch.zeros(1,3,160,256),str(path),input_names=['image'],output_names=['class_probabilities','bbox_deltas'],dynamic_axes={'image':{2:'height',3:'width'},'class_probabilities':{1:'feature_height',2:'feature_width'},'bbox_deltas':{1:'feature_height',2:'feature_width'}},opset_version=17,dynamo=False)
    opt=ort.SessionOptions();opt.intra_op_num_threads=2;session=ort.InferenceSession(str(path),opt,providers=['CPUExecutionProvider']);rows=[];rng=np.random.default_rng(20261120)
    for h,w in [(160,256),(320,512),(400,640)]:
        x=rng.normal(0,30,(1,h,w,3)).astype('float32');expected={k.get_any_name():v for k,v in reference([x]).items()};actual=session.run(None,{'image':x.transpose(0,3,1,2)})
        errors=[float(np.max(np.abs(expected['Reshape_2:0']-actual[0]))),float(np.max(np.abs(expected['rpn_bbox_pred/Reshape_1:0']-actual[1])))];assert max(errors)<.002,errors
        rows.append({'input':[h,w],'max_probability_error':errors[0],'max_regression_error':errors[1]});print(rows[-1],flush=True)
    record={'source_sha256':hashlib.sha256(Path(a.source).read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'architecture':'VGG16 13 Conv + RPN Conv + BiLSTM(128) + FC(512) + 10 anchor heads','trained':False,'reference':'original frozen graph read and executed by OpenVINO CPU, not a separate TensorFlow runtime','parity':rows}
    (ROOT/'docs/ctpn-conversion-results.json').write_text(json.dumps(record,indent=2))
if __name__=='__main__':main()
