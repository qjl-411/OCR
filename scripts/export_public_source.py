"""Export a clean review checkout without private financial files."""
import argparse,json,os,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.venv','node_modules','runtime','__pycache__','.pytest_cache','.git','.qa','pytest-of-agent','test-results','playwright-report','evaluation','.openai'}
PRIVATE={'tests/provided_expectations.json','data/provided-manifest.json','docs/evaluation-results.json','DELIVERY_MANIFEST.json','scripts/export_public_source.py'}
def main():
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);a=p.parse_args();destination=a.destination.resolve();assert destination!=ROOT and not destination.is_relative_to(ROOT)
    destination.mkdir(parents=True,exist_ok=True);files=[]
    # Remove a previously generated copy of this private export helper. It
    # contains redaction literals and is not part of the public application.
    (destination/'scripts/export_public_source.py').unlink(missing_ok=True)
    for parent,dirs,names in os.walk(ROOT):
        dirs[:]=[d for d in dirs if d not in EXCLUDED and not d.startswith(('.sites-','pytest-of-'))]
        for name in names:
            source=Path(parent)/name;relative=source.relative_to(ROOT);r=relative.as_posix()
            if r in PRIVATE or r.startswith(('data/provided/','training/data/','training/camera-data/','training/source/','docs/reference/')):continue
            if source.suffix in ['.pyc','.tsbuildinfo','.pth','.onnx']:continue
            if r in ['models/classic/ctpn.xml','models/classic/ctpn.bin']:continue
            target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);files.append(r)
    p=destination/'.gitignore';text=p.read_text().replace('model-parts/*.part\n','');text+='\n!data/provided/\ndata/provided/*\n!data/provided/README.txt\n';p.write_text(text)
    folder=destination/'data/provided';folder.mkdir(parents=True,exist_ok=True);(folder/'README.txt').write_text('公开源码不包含原始私人发票。可在本机放入获授权的 PDF，或从界面上传。\n',encoding='utf-8')
    # Preserve the published recipe without disclosing private synthetic-label
    # literals. Exact private-training replay requires the private attachments.
    p=destination/'training/prepare_crnn_data.py';s=p.read_text().replace('江西方欣信息技术有限公司','示例企业有限公司').replace('91360103683459290Y','DEMO00000000000001');p.write_text(s)
    for name in ['independent-classic-results.json','vatid-image-holdout-results.json']:
        p=destination/'docs'/name;d=json.loads(p.read_text());rows=d.pop('image_results',[])
        d['image_summaries']=[{'id':r['id'],'engine':r['engine'],'seconds':r['seconds'],'keywords':len(r['keywords']),'covered':sum(k['covered'] for k in r['keywords']),'spotted':sum(k['spotted'] for k in r['keywords'])} for r in rows]
        d['public_export']='Keyword predictions omitted from public copy; original private delivery retains detailed results.'
        p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
    p=destination/'docs/external-classic-results.json';d=json.loads(p.read_text())
    for row in d['image_results']:row.pop('raw_text',None)
    d['public_export']='Unrelated raw invoice text omitted; all six predeclared field predictions, including failures, retained.'
    p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
    assert not list(folder.glob('*.pdf')) and not (destination/'tests/provided_expectations.json').exists()
    report={'files':len(files),'private_pdf_count':0,'private_crop_images':0,'runtime_database_included':False,'runtime_models':'hash-checked local model-parts; restore_models.py recreates ONNX','private_training_recipe':'public synthetic label literals use fictional placeholders; exact private checkpoint replay requires original private inputs'}
    (destination/'PUBLIC_EXPORT_CHECK.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(report)
if __name__=='__main__':main()
