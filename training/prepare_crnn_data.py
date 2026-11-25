"""PDF text-object supervision and explicitly synthetic strings, not OCR labels."""
import json,random
from pathlib import Path
import fitz
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
def main():
    folder=ROOT/'training/data';folder.mkdir(parents=True,exist_ok=True);allowed=set((ROOT/'models/classic/charset_cn.txt').read_text(encoding='utf-8'))
    files=sorted((ROOT/'data/provided').glob('*.pdf'));splits={'train':[],'validation':[]};skipped=[]
    for i,path in enumerate(files):
        split='train' if i<18 else 'validation';pdf=fitz.open(path);page=pdf[0];pix=page.get_pixmap(matrix=fitz.Matrix(3,3),alpha=False);image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                text=''.join(s['text'] for s in line['spans']).strip().replace(' ','').replace('¥','￥')
                if not 1<=len(text)<=65:continue
                if any(c not in allowed for c in text):skipped.append({'source':path.name,'text':text});continue
                x0,y0,x1,y1=[int(v*3) for v in line['bbox']]
                if min(x0,y0)<0 or x1>image.width or y1>image.height:continue
                crop=image.crop((max(0,x0-2),max(0,y0-1),min(image.width,x1+2),min(image.height,y1+1)))
                if min(crop.size)<4:continue
                name=f'{split}-{i:02d}-{len(splits[split]):04d}.png';crop.save(folder/name);splits[split].append({'file':name,'text':text,'source':path.name,'source_kind':'PDF text layer'})
        pdf.close()
    fonts=[ImageFont.truetype(p,36) for p in ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/opentype/noto/NotoSerifCJK-Regular.ttc'] if Path(p).exists()]
    if not fonts:raise RuntimeError('Need Noto CJK fonts for reproducible synthetic supervision')
    random.seed(20261120)
    for i in range(700):
        number=''.join(random.choice('0123456789') for _ in range(20)) if i%4 else '9900000000000000'+f'{i:04d}'
        texts=[number,'发票号码：'+number,f'{random.randint(0,9999)}.{random.randint(0,99):02d}',f'￥{random.randint(0,9999)}.{random.randint(0,99):02d}',f'开票日期：2026年{random.randint(1,12):02d}月{random.randint(1,28):02d}日','名称：江西方欣信息技术有限公司','价税合计（小写）','合计','纳税人识别号：91360103683459290Y'];text=texts[i%len(texts)]
        if any(c not in allowed for c in text):continue
        font=fonts[i%len(fonts)];box=font.getbbox(text);image=Image.new('L',(box[2]-box[0]+8,box[3]-box[1]+8),255);ImageDraw.Draw(image).text((4-box[0],4-box[1]),text,font=font,fill=0)
        split='validation' if i%10==9 else 'train';name=f'synthetic-{i:04d}.png';image.save(folder/name);splits[split].append({'file':name,'text':text,'source':'synthetic Noto CJK','source_kind':'synthetic'})
    for key,rows in splits.items():(folder/f'{key}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    (folder/'manifest.json').write_text(json.dumps({'provided_train_pdfs':[p.name for p in files[:18]],'provided_validation_pdfs':[p.name for p in files[18:]],'counts':{k:len(v) for k,v in splits.items()},'skipped_unrepresentable':skipped,'independent_test_data_used':False},ensure_ascii=False,indent=2))
    print({k:len(v) for k,v in splits.items()},flush=True)
if __name__=='__main__':main()
