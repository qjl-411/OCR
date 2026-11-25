"""Explicitly download immutable original model weights and verify digests."""
import hashlib,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FILES=[('ctpn.pb','https://storage.openvinotoolkit.org/repositories/open_model_zoo/public/2022.1/ctpn/ctpn.pb','09b3a0cc57eb826dd6b6fa95a03e078ad435b7b5fb0186dad2abdb98a4fdf64a'),('crnn-source.pth','https://raw.githubusercontent.com/Sierkinhane/CRNN_Chinese_Characters_Rec/a565687c4076b729d4059593b7570dd388055af4/output/checkpoints/mixed_second_finetune_acc_97P7.pth','7836afdb7f56cae4d5ef28532c33c1642f7f9a5e65cef5bd6fa9da00595a8691')]
if __name__=='__main__':
    folder=ROOT/'training/source';folder.mkdir(parents=True,exist_ok=True)
    for name,url,digest in FILES:
        path=folder/name
        if not path.exists():
            with urllib.request.urlopen(url,timeout=120) as response:data=response.read()
            if hashlib.sha256(data).hexdigest()!=digest:raise ValueError('Source checksum failed: '+name)
            path.write_bytes(data)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest;print(name,'verified')
