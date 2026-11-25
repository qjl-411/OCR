import io
import time
import zipfile

import fitz
from openpyxl import load_workbook

from backend.app import config, db
from backend.app.parser import money

FIELDS=['invoice_number','invoice_code','invoice_date','invoice_type','buyer_name','buyer_tax_id','seller_name','seller_tax_id','subtotal','tax_amount','total','tax_rates','category','remark']


def wait_job(client,job_id):
    end=time.monotonic()+30
    while time.monotonic()<end:
        result=client.get('/api/jobs/'+job_id).json()
        if result['status'] in ['completed','failed']:return result
        time.sleep(.02)
    raise AssertionError('Import timed out')


def upload(client,data,name='sample.pdf'):
    response=client.post('/api/imports',files=[('files',(name,data))])
    assert response.status_code==202,response.text
    return wait_job(client,response.json()['id'])


def get_one(client):
    item=client.get('/api/invoices').json()['items'][0]
    return client.get('/api/invoices/'+item['id']).json()


def patch(client,r,**changes):
    body={k:r.get(k) for k in FIELDS};body.update(changes);body['revision']=r['revision']
    return client.patch('/api/invoices/'+r['id'],json=body)


def review(client,r,verdict='approved',note=''):
    return client.post(f"/api/invoices/{r['id']}/review",json={'revision':r['revision'],'verdict':verdict,'note':note})


def test_complete_import_review_edit_export_delete_flow(client,sample):
    assert client.get('/api/health').json()['status']=='ok'
    j=upload(client,sample);assert j['succeeded']==1 and j['failed']==0
    r=get_one(client);assert r['status']=='needs_review'
    assert client.get('/api/dashboard').json()['total_amount']=='0.00'
    assert client.get(r['preview_url']).headers['content-type']=='image/jpeg'
    assert client.get(r['original_url']).status_code==200
    assert review(client,r).status_code==200
    r=get_one(client);assert r['status']=='approved'
    assert client.get('/api/dashboard').json()['total_amount']=='8480.00'
    patched=patch(client,r,remark='核对完成');assert patched.status_code==200
    r=patched.json();assert r['status']=='needs_review'
    assert review(client,r).status_code==200
    xlsx=client.get('/api/export?format=xlsx');assert xlsx.status_code==200
    workbook=load_workbook(io.BytesIO(xlsx.content))
    assert workbook.sheetnames==['发票明细','汇总说明']
    assert workbook.worksheets[0]['A2'].value=='99000000000000000001'
    assert workbook.worksheets[0]['A2'].data_type=='s'
    assert workbook.worksheets[0]['K2'].value==8480
    assert client.get('/api/export?format=csv').content.startswith(b'\xef\xbb\xbf')
    assert client.get('/api/export?format=json').json()['invoices'][0]['total']=='8480.00'
    assert client.delete('/api/invoices/'+r['id']).status_code==200
    assert client.get('/api/invoices/'+r['id']).status_code==404
    actions=[r['action'] for r in client.get('/api/audit').json()['items']]
    assert all(a in actions for a in ['import','edit','approve','export','delete'])


def test_identical_files_are_skipped(client,sample):
    assert upload(client,sample)['succeeded']==1
    assert upload(client,sample,'renamed.pdf')['skipped']==1
    assert client.get('/api/invoices').json()['total']==1


def test_business_duplicate_blocks_both_and_rejecting_one_releases_other(client):
    for name in ['demo-09.pdf','demo-10.pdf']:
        assert upload(client,(config.ROOT/'data/demo'/name).read_bytes(),name)['succeeded']==1
    records=client.get('/api/invoices').json()['items']
    assert all(r['duplicate'] for r in records)
    assert review(client,records[0]).status_code==422
    assert review(client,records[0],'rejected','相同票号，保留另一张').status_code==200
    other=client.get('/api/invoices/'+records[1]['id']).json()
    assert not other['duplicate']
    assert review(client,other).status_code==200
    assert client.get('/api/dashboard').json()['total_amount']=='128.50'


def test_edit_invalidates_approval_and_revision_guard(client,sample):
    upload(client,sample);r=get_one(client)
    assert review(client,r).status_code==200
    assert patch(client,r,remark='stale').status_code==409
    r=get_one(client)
    result=patch(client,r,total='999.00')
    assert result.status_code==200 and result.json()['status']=='needs_review'
    assert review(client,result.json()).status_code==422


def test_malformed_documents_and_unsupported_files(client):
    assert upload(client,b'%PDF- broken')['failed']==1
    assert client.post('/api/imports',files=[('files',('unsafe.exe',b'no'))]).status_code==422
    assert upload(client,b'no','fake.png')['failed']==1


def test_safe_zip_batch_with_traversal_and_wrong_format(client,sample):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('nested/valid.pdf',sample)
        z.writestr('../escape.pdf',sample)
        z.writestr('note.txt','skip')
    j=upload(client,out.getvalue(),'batch.zip')
    assert j['succeeded']==1 and len(j['errors'])==2
    assert not (config.DATA.parent/'escape.pdf').exists()


def test_multipage_pdf_creates_page_records(client,sample):
    original=fitz.open(stream=sample,filetype='pdf');combined=fitz.open()
    combined.insert_pdf(original);combined.insert_pdf(original)
    j=upload(client,combined.tobytes())
    assert j['succeeded']==1
    records=client.get('/api/invoices').json()['items']
    assert sorted(r['page'] for r in records)==[1,2]
    assert all(r['duplicate'] for r in records)
    combined.close();original.close()


def test_filters_pagination_and_empty_export(client):
    for name in ['demo-01.pdf','demo-02.pdf','demo-03.pdf']:
        upload(client,(config.ROOT/'data/demo'/name).read_bytes(),name)
    q=client.get('/api/invoices?q=简物').json();assert q['total']==1
    assert client.get('/api/invoices?category=差旅交通').json()['total']==1
    assert len(client.get('/api/invoices?page=2&page_size=2').json()['items'])==1
    assert client.get('/api/invoices?start=2026-11-18').json()['total']==1
    assert client.get('/api/export?format=csv&q=notfound').status_code==422
    assert client.get('/api/invoices?page=0').status_code==422


def test_formula_injection_is_inert_and_identifiers_are_text(client,sample):
    upload(client,sample);r=get_one(client)
    result=patch(client,r,seller_name='=HYPERLINK("https://example.test")',remark='@SUM(1,2)')
    assert result.status_code==200
    response=client.get('/api/export?format=xlsx');wb=load_workbook(io.BytesIO(response.content))
    assert wb.worksheets[0]['G2'].data_type=='s'
    assert wb.worksheets[0]['G2'].value.startswith('=HYPERLINK')
    assert "'=HYPERLINK" in client.get('/api/export?format=csv').text


def test_setting_validation_and_cross_origin_mutation_block(client,sample):
    assert client.patch('/api/settings',json={'workspace_name':'测试工作区','confidence_threshold':.85,'amount_tolerance':'0.01'}).status_code==200
    assert client.get('/api/meta').json()['settings']['workspace_name']=='测试工作区'
    assert client.patch('/api/settings',json={'workspace_name':'','confidence_threshold':1.1,'amount_tolerance':'9'}).status_code==422
    assert client.post('/api/imports',files=[('files',('test.pdf',sample))],headers={'Origin':'https://untrusted.example'}).status_code==403
    assert client.get('/api/health').headers['x-content-type-options']=='nosniff'


def test_reject_requires_note_and_broken_api_is_not_frontend(client,sample):
    upload(client,sample);r=get_one(client)
    assert review(client,r,'rejected','').status_code==422
    assert client.get('/api/does-not-exist').status_code==404


def test_interrupted_jobs_are_recovered(client):
    db.save_job({'id':'interrupted','status':'running'})
    db.interrupted_jobs()
    job=client.get('/api/jobs/interrupted').json()
    assert job['status']=='failed' and '重新导入' in job['error']


def test_rejected_duplicate_cannot_be_reapproved(client):
    for name in ['demo-09.pdf','demo-10.pdf']:
        upload(client,(config.ROOT/'data/demo'/name).read_bytes(),name)
    items=client.get('/api/invoices').json()['items']
    rejected=review(client,items[0],'rejected','重复记录').json()
    assert review(client,rejected).status_code==422
    other=client.get('/api/invoices/'+items[1]['id']).json()
    assert review(client,other).status_code==200


def test_source_filter_is_consistent_for_dashboard_ledger_and_export(client,sample):
    upload(client,sample)
    assert client.get('/api/invoices?source=upload').json()['total']==1
    assert client.get('/api/invoices?source=demo').json()['total']==0
    assert client.get('/api/dashboard?source=upload').json()['total_count']==1
    assert client.get('/api/dashboard?source=demo').json()['total_count']==0
    assert client.get('/api/export?source=demo').status_code==422


def test_offline_api_reference_has_no_cdn_dependency(client):
    result=client.get('/docs')
    assert result.status_code==200
    assert 'cdn.jsdelivr.net' not in result.text
    assert '/api/invoices' in result.text
    assert client.get('/openapi.json').json()['info']['version']=='2.0.0'


def test_a_blank_later_page_does_not_partially_save_a_file(client,sample,monkeypatch):
    from backend.app import reader
    from PIL import Image
    page=next(reader.read_pages(sample,'.pdf'))
    def mixed_pages(*args,**kwargs):
        yield page
        yield 2,Image.new('RGB',(100,100),'white'),[],'ocr'
    monkeypatch.setattr(reader,'read_pages',mixed_pages)
    assert upload(client,sample)['failed']==1
    assert client.get('/api/invoices').json()['total']==0
    assert not list((config.DATA/'originals').iterdir())
    assert not list((config.DATA/'previews').iterdir())
