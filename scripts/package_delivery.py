"""Produce the private, runnable candidate with complete weight-file hashes."""
import hashlib,json,os,shutil,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.venv','node_modules','runtime','__pycache__','.pytest_cache','.git','.qa','pytest-of-agent','test-results','playwright-report','evaluation','.openai'}
def files():
    paths=[]
    for parent,dirs,names in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in EXCLUDED and not d.startswith(('.sites-','pytest-of-'))]
        for name in names:
            p=Path(parent)/name;r=p.relative_to(ROOT).as_posix()
            if name=='DELIVERY_MANIFEST.json' or p.suffix in ['.pyc','.tsbuildinfo','.part']:continue
            if r.startswith(('training/data/','training/camera-data/','training/source/')):continue
            if r in ['models/classic/ctpn.xml','models/classic/ctpn.bin']:continue
            if p.suffix=='.pth' and r!='training/runs/camera-adaptation/finetuned.pth':continue
            paths.append(p)
    return sorted(paths)
def main():
    output=ROOT.parent/'deliverables';output.mkdir(exist_ok=True)
    required=['start.py','dist/index.html','models/classic/ctpn.onnx','models/classic/crnn_cn.onnx','models/classic/manifest.json','docs/independent-classic-results.json','docs/external-classic-results.json','data/vatid-identity-audit.json','data/evaluation-split.json','docs/backend-test-results.xml','docs/delivery-smoke-results.json','docs/piao-project-handbook.html','.github/workflows/acceptance.yml']
    for name in required:assert (ROOT/name).is_file(),name
    assert len(list((ROOT/'data/provided').glob('*.pdf')))==23
    paths=files();manifest={'project':'票序 智能财务发票系统','version':'2.0.0 acceptance candidate','entry':'python start.py','status':'Specified networks and real training executed; small invoice-identity-disjoint evaluation completed with documented extraction failures. Windows/macOS/Docker/browser acceptance pending real execution.','files':[{'path':p.relative_to(ROOT).as_posix(),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in paths]}
    mp=ROOT/'DELIVERY_MANIFEST.json';mp.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8');archive=output/'piao-studio-v2.0-acceptance-candidate.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths+[mp]:z.write(p,'invoice-studio/'+p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for item in manifest['files']:assert hashlib.sha256(z.read('invoice-studio/'+item['path'])).hexdigest()==item['sha256'],item['path']
        assert sum(n.startswith('invoice-studio/data/provided/') and n.endswith('.pdf') for n in z.namelist())==23
    handbook=output/'piao-v2-development-handbook.html';shutil.copy2(ROOT/'docs/piao-project-handbook.html',handbook)
    (output/'SHA256SUMS-v2.txt').write_text('\n'.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name for p in [archive,handbook])+'\n')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'files':len(paths)+1,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'handbook':str(handbook)},ensure_ascii=False))
if __name__=='__main__':main()
