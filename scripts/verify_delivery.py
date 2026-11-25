"""Real service/queue/designated OCR/XLSX smoke check on native OS or Docker."""
import argparse,hashlib,json,os,platform,re,socket,subprocess,sys,tempfile,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[1]

def verify(base):
    with httpx.Client(base_url=base,timeout=120,trust_env=False) as client:
        for _ in range(150):
            try:
                response=client.get('/api/health');response.raise_for_status();break
            except httpx.HTTPError:time.sleep(.2)
        else:raise AssertionError('HTTP service startup timed out')
        health=response.json();assert health['version']=='2.0.0' and health['ocr_available']
        page=client.get('/');page.raise_for_status();assert '票序' in page.text;assets=re.findall(r'(?:src|href)="(/assets/[^\"]+)"',page.text);assert len(assets)>=2
        for asset in assets:assert client.get(asset).status_code==200
        d=client.get('/api/dashboard').json();assert (d['total_count'],d['approved_count'],d['total_amount'])==(11,7,'13675.70')
        assert client.get('/api/meta').json()['pipelines']['default']=='classic'
        assert client.get('/openapi.json').json()['info']['version']=='2.0.0'
        docs=client.get('/docs');assert docs.status_code==200 and 'cdn.jsdelivr' not in docs.text
        response=client.post('/api/imports',data={'pipeline':'classic','force_ocr':'true'},files=[('files',('demo-12.png',(ROOT/'data/demo/demo-12.png').read_bytes(),'image/png'))]);assert response.status_code==202,response.text
        job_id=response.json()['id'];end=time.monotonic()+120
        while time.monotonic()<end:
            job=client.get('/api/jobs/'+job_id).json()
            if job['status'] in ['completed','failed']:break
            time.sleep(.1)
        assert job['status']=='completed' and job['succeeded']==1 and job['failed']==0,job
        r=client.get('/api/invoices/'+job['results'][0]['invoice_ids'][0]).json();assert r['engine']=='ctpn_crnn_ctc'
        expected={'invoice_number':'99000000000000000012','invoice_date':'2026-11-13','subtotal':'175.47','tax_amount':'10.53','total':'186.00'}
        assert {k:r[k] for k in expected}==expected
        assert r['status']=='needs_review' and r['processing_profile']['model_version']
        assert client.get(r['preview_url']).status_code==200 and client.get(r['original_url']).status_code==200
        xlsx=client.get('/api/export?format=xlsx');assert xlsx.status_code==200 and xlsx.content[:2]==b'PK'
        assert client.get('/api/dashboard').json()['total_amount']=='13675.70'
        return {'service_startup':'passed','static_assets':len(assets),'offline_docs':'passed','actual_image_ocr':'passed','engine':r['engine'],'model_version':r['processing_profile']['model_version'],'observed':expected,'queue_and_preview':'passed','xlsx_download':'passed','unreviewed_amount_excluded':'passed'}

def main():
    p=argparse.ArgumentParser();p.add_argument('--base-url',default='');p.add_argument('--output',type=Path,default=ROOT/'docs/delivery-smoke-results.json');a=p.parse_args()
    sys.path.insert(0,str(ROOT/'scripts'));from restore_models import restore;restore()
    manifest=json.loads((ROOT/'models/classic/manifest.json').read_text())
    for item in manifest['files']:assert hashlib.sha256((ROOT/'models/classic'/item['file']).read_bytes()).hexdigest()==item['sha256']
    if a.base_url:result=verify(a.base_url)
    else:
        parent=ROOT/'.qa';parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent,prefix='native-') as directory:
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            env=os.environ.copy();env.update(INVOICE_DATA_DIR=directory,INVOICE_SEED_DEMO='1')
            with (Path(directory)/'server.log').open('w') as log:
                process=subprocess.Popen([sys.executable,'-m','uvicorn','backend.app.main:app','--host','127.0.0.1','--port',str(port)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
                try:result=verify(f'http://127.0.0.1:{port}')
                except Exception:print((Path(directory)/'server.log').read_text(),file=sys.stderr);raise
                finally:
                    process.terminate()
                    try:process.wait(timeout=10)
                    except subprocess.TimeoutExpired:process.kill();process.wait()
    assert result['model_version']==manifest['version']
    result.update(python=platform.python_version(),platform=platform.platform(),machine=platform.machine(),model_hashes='passed',browser_visual_qa='separate real-browser evidence required')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
