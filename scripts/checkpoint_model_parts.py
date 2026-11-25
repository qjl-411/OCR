"""Split large weight files into bounded pieces for source version recovery."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    folder=ROOT/'model-parts';folder.mkdir(exist_ok=True);entries=[]
    for path in sorted((ROOT/'models').rglob('*.onnx')):
        data=path.read_bytes();parts=[]
        for i,offset in enumerate(range(0,len(data),8*1024*1024)):
            name=path.relative_to(ROOT).as_posix().replace('/','_')+f'.{i:03d}.part';chunk=data[offset:offset+8*1024*1024];(folder/name).write_bytes(chunk)
            parts.append({'file':name,'bytes':len(chunk),'sha256':hashlib.sha256(chunk).hexdigest()})
        entries.append({'file':path.relative_to(ROOT).as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'parts':parts})
    (folder/'manifest.json').write_text(json.dumps({'files':entries},indent=2));print({'models':len(entries),'parts':sum(len(e['parts']) for e in entries)},flush=True)
if __name__=='__main__':main()
