"""Explicit CTC label collapse. Blank removal must follow repeat collapse."""
import numpy as np

def greedy_ctc(log_probs,charset,blank=0):
    values=np.asarray(log_probs)
    if values.ndim==3:values=values[:,0,:]
    labels=values.argmax(-1).tolist();output=[];selected=[];previous=None
    for t,label in enumerate(labels):
        if label!=blank and label!=previous:
            index=label-1 if label>blank else label
            output.append(charset[index] if 0<=index<len(charset) else '\ufffd');selected.append(float(values[t,label]))
        previous=label
    return ''.join(output),float(np.clip(np.exp(np.mean(selected)),0,1)) if selected else 0.,labels
