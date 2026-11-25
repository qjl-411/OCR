"""Fixed VATID splits, immutable upstream revision; no implicit network use."""
import hashlib,json,urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
COMMIT='e0c2ab03a253552133f1a771b9a77eb20db20865';BASE=f'https://raw.githubusercontent.com/FuxiJia/InvoiceDatasets/{COMMIT}/'
def fetch_subset(folder,start,end,split,use):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    selection={'repo':'FuxiJia/InvoiceDatasets','commit':COMMIT,'samples':[f'vat_{i:04d}' for i in range(start,end+1)],'selection_rule':f'fixed contiguous IDs {start:04d} through {end:04d} from official VAT {split} split','use':use,'exclusions':'0001-0020 train; 0021-0025 crop development; 0051-0060 preprocessing development; 0061-0080 historical candidate; 0081-0100 final heldout'}
    p=folder/'selection.json'
    if p.exists() and json.loads(p.read_text())!=selection:raise ValueError('Refusing to overwrite an existing split protocol')
    p.write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
    jobs=[]
    for name in selection['samples']:jobs.extend([(f'dataset/images/vat_{split}/{name}.jpg',f'{name}.jpg'),(f'dataset/labels/textGT/{name}_textGT.txt',f'{name}_textGT.txt')])
    def download(job):
        source,name=job;destination=folder/name
        if not destination.exists():
            with urllib.request.urlopen(BASE+source,timeout=90) as r:destination.write_bytes(r.read())
        return {'file':name,'bytes':destination.stat().st_size,'sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'url':BASE+source}
    with ThreadPoolExecutor(4) as pool:manifest=list(pool.map(download,jobs))
    (folder/'download-manifest.json').write_text(json.dumps(manifest,indent=2));return selection

def annotations(path):
    rows=Path(path).read_bytes().decode('gbk').splitlines();result=[]
    for i in range(0,len(rows)-1,2):
        x0,x1,y0,y1=map(float,rows[i+1].split());result.append((rows[i].strip(),[x0,y0,x1,y1]))
    return result

def fetch_selection(folder,selection):
    """Materialize a predeclared, possibly noncontiguous evaluation protocol."""
    assert selection['repo']=='FuxiJia/InvoiceDatasets' and selection['commit']==COMMIT
    assert selection['source_partition'] in ['train','test']
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);protocol=folder/'selection.json'
    if protocol.exists() and json.loads(protocol.read_text())!=selection:
        raise ValueError('Refusing to overwrite an existing evaluation protocol')
    protocol.write_text(json.dumps(selection,ensure_ascii=False,indent=2),encoding='utf-8')
    records=[]
    for name in selection['samples']:
        assert len(name)==8 and name.startswith('vat_') and name[4:].isdigit()
        for source,filename in [(f"dataset/images/vat_{selection['source_partition']}/{name}.jpg",f'{name}.jpg'),(f'dataset/labels/textGT/{name}_textGT.txt',f'{name}_textGT.txt')]:
            target=folder/filename
            if not target.exists():
                with urllib.request.urlopen(BASE+source,timeout=90) as response:target.write_bytes(response.read())
            records.append({'file':filename,'url':BASE+source,'bytes':target.stat().st_size,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
    (folder/'download-manifest.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
    return selection
