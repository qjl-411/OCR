"""Frozen external image field benchmark, with manually declared ground truth.

Downloads original example files only. Never calls any cloud recognition API.
"""
import argparse
import hashlib
import json
import platform
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, default=ROOT/'evaluation/external-final')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/external-classic-results.json')
    parser.add_argument('--download-only', action='store_true')
    args = parser.parse_args()
    protocol_path = ROOT/'data/external-evaluation-split.json'
    protocol = json.loads(protocol_path.read_text())
    args.dataset.mkdir(parents=True, exist_ok=True)
    for sample in protocol['samples']:
        path = args.dataset/(sample['id']+'.jpg')
        if args.download_only and not path.exists():
            with urllib.request.urlopen(sample['url'], timeout=90) as response:
                path.write_bytes(response.read())
        if not path.exists():
            raise FileNotFoundError('Run this script with --download-only first: '+str(path))
        assert digest(path) == sample['image_sha256'], 'Source image changed: '+sample['id']
    if args.download_only:
        print('Verified original external example images; no recognition API called.')
        return
    sys.path.insert(0, str(ROOT))
    from backend.app.reader import read_pages
    from backend.app.parser import parse
    start = time.monotonic()
    rows = []
    for sample in protocol['samples']:
        path = args.dataset/(sample['id']+'.jpg')
        before = time.monotonic()
        _, image, boxes, engine = next(read_pages(path.read_bytes(), '.jpg', pipeline='classic', force_ocr=True))
        assert engine == image.info['ocr_pipeline'] == 'ctpn_crnn_ctc'
        document = parse(boxes, engine)
        observed = {key:document[key] for key in sample['expected']}
        matches = {key:observed[key] == value for key,value in sample['expected'].items()}
        row = {'id':sample['id'], 'engine':engine, 'image_sha256':digest(path),
               'expected':sample['expected'], 'observed':observed, 'matches':matches,
               'raw_text':document['raw_text'], 'seconds':round(time.monotonic()-before,3)}
        rows.append(row)
        print(sample['id'], sum(matches.values()), '/', len(matches), flush=True)
    fields = {key:{'matched':sum(row['matches'][key] for row in rows), 'total':len(rows)}
              for key in protocol['samples'][0]['expected']}
    count = sum(sum(row['matches'].values()) for row in rows)
    total = sum(len(row['matches']) for row in rows)
    record = {'created_at':datetime.now(timezone.utc).isoformat(), 'engine':'ctpn_crnn_ctc',
              'models':json.loads((ROOT/'models/classic/manifest.json').read_text())['files'],
              'protocol_sha256':digest(protocol_path), 'protocol':protocol,
              'implementation_sha256':{name:digest(ROOT/name) for name in [
                  'backend/app/classic_ocr/pipeline.py','backend/app/classic_ocr/ctc.py',
                  'backend/app/classic_ocr/ctpn_postprocess.py','backend/app/reader.py',
                  'backend/app/parser.py','scripts/evaluate_external.py']},
              'images_count':len(rows), 'physical_invoice_groups':len(rows),
              'matched_fields':count, 'total_fields':total, 'field_exact_accuracy':count/total,
              'per_field':fields, 'image_results':rows,
              'seconds':round(time.monotonic()-start,3), 'python':platform.python_version(),
              'scope':'Six predeclared printed fields per independent public documentation example; tiny convenience sample; no manual corrections or parameter changes after inference.',
              'ppocr_used':False, 'cloud_ocr_used':False, 'pdf_text_used':False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'matched_fields':count,'total_fields':total,'output':str(args.output)}),flush=True)


if __name__ == '__main__':
    main()
