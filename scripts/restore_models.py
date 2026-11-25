"""Offline, hash-checked restoration of versioned weight pieces. No downloads."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def restore():
    manifest=ROOT/'model-parts/manifest.json'
    if not manifest.exists():return
    for item in json.loads(manifest.read_text())['files']:
        target=(ROOT/item['file']).resolve()
        if not target.is_relative_to(ROOT/'models'):raise ValueError('Invalid model destination')
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()==item['sha256']:continue
        target.parent.mkdir(parents=True,exist_ok=True);temporary=target.with_suffix('.partial');digest=hashlib.sha256();size=0
        try:
            with temporary.open('wb') as out:
                for piece in item['parts']:
                    source=(ROOT/'model-parts'/piece['file']).resolve()
                    if not source.is_relative_to(ROOT/'model-parts'):raise ValueError('Invalid piece path')
                    data=source.read_bytes()
                    if len(data)!=piece['bytes'] or hashlib.sha256(data).hexdigest()!=piece['sha256']:raise ValueError('Model piece checksum failed: '+piece['file'])
                    out.write(data);digest.update(data);size+=len(data)
            if size!=item['bytes'] or digest.hexdigest()!=item['sha256']:raise ValueError('Model checksum failed')
            temporary.replace(target)
        finally:temporary.unlink(missing_ok=True)
if __name__=='__main__':restore();print('Model files restored and verified.')
