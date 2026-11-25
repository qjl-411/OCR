"""Download the fixed invoice-identity-disjoint split; never select by scores."""
import argparse,hashlib,json
from pathlib import Path
from vatid_data import fetch_selection
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'evaluation/vatid-final');a=p.parse_args()
    selection=json.loads((ROOT/'data/evaluation-split.json').read_text())
    audit_path=ROOT/selection['identity_audit'];audit=json.loads(audit_path.read_text())
    assert hashlib.sha256(audit_path.read_bytes()).hexdigest()==selection['identity_audit_sha256']
    phases=audit['phases'];pool=phases['unused_candidate_pool']
    excluded={group for phase,rows in phases.items() if phase!='unused_candidate_pool' for group in rows.values()}
    assert selection['samples']==[name for name,group in pool.items() if group not in excluded]
    assert not set(selection['selected_groups'].values()) & excluded
    fetch_selection(a.output,selection);print(a.output)
