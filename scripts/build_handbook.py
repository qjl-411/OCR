"""Build a self-contained Chinese development handbook from the project docs."""
import html
import json
import re
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        raise SystemExit('文档重建需要安装 requirements-docs.txt；日常运行不需要。')
    from backend.app.main import app
    from backend.app.openapi_ui import render
    schema=app.openapi()
    (ROOT/'docs/openapi.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'docs/08-openapi.html').write_text(render(schema),encoding='utf-8')
    md=MarkdownIt('commonmark',{'html':False}).enable('table')
    sections=[];nav=[]
    paths=[ROOT/'README.md']+sorted((ROOT/'docs').glob('[0-9][0-9]-*.md'))
    for index,path in enumerate(paths):
        source=path.read_text(encoding='utf-8')
        title=source.splitlines()[0].lstrip('# ')
        # A readable ordered flow replaces Mermaid in the exported offline
        # handbook; the exact Mermaid source remains in the Markdown file.
        source=re.sub(r'```mermaid\n[\s\S]*?```','**处理流程：** 批量上传 → 格式检查 → 本地队列 → PDF 直接读取或图片 OCR → 字段提取与校验 → 人工修订、确认或驳回 → 统计与导出。',source)
        rendered=md.render(source)
        # Relative source links in a standalone export point to included
        # sections where applicable; no external assets are needed.
        for other_index,other in enumerate(paths):
            for link in [other.name,'docs/'+other.name]:
                rendered=rendered.replace('href="'+link+'"','href="#section-'+str(other_index)+'"')
        sections.append(f'<section id="section-{index}">{rendered}</section>')
        nav.append(f'<a href="#section-{index}">{html.escape(title.replace("票序智能财务发票系统 ",""))}</a>')
    style='''
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f7f5;color:#27372e;font:16px/1.9 system-ui,"PingFang SC","Microsoft YaHei",sans-serif}a{color:#347554;text-decoration:none}a:hover{text-decoration:underline}header{background:#164c3d;color:white;padding:60px max(28px,calc((100vw - 1160px)/2)) 50px}header .label{color:#b6d3bf;letter-spacing:3px;font-size:12px}header h1{font-size:36px;line-height:1.4;letter-spacing:1px;margin:15px 0 18px}header p{color:#c4d8ca;max-width:700px;font-size:15px;line-height:1.9}header .badges{display:flex;gap:12px;margin-top:25px;flex-wrap:wrap}header .badges span{font-size:12px;color:#cbe3ce;padding:5px 12px;background:#ffffff0a;border:1px solid #ffffff24;border-radius:5px}.layout{max-width:1200px;margin:35px auto;display:grid;grid-template-columns:220px minmax(0,1fr);gap:32px;padding:0 25px}nav{position:sticky;top:25px;align-self:start;padding:18px 14px;border:1px solid #e1e9e0;border-radius:10px;background:white}nav strong{display:block;font-size:12px;color:#80927b;letter-spacing:1px;margin:3px 12px 10px}nav a{display:block;font-size:13px;line-height:1.65;color:#63775a;padding:9px 12px;border-radius:6px}nav a:hover{background:#f0f6ea;text-decoration:none}article{min-width:0}section{background:white;border:1px solid #e1e8dc;border-radius:12px;padding:34px 38px;margin-bottom:25px;scroll-margin-top:25px}section>h1{font-size:25px;color:#253b29;line-height:1.5;margin:0 0 25px}h2{font-size:20px;color:#385232;margin:32px 0 16px}h3{font-size:17px;color:#56744b;margin:26px 0 13px}h4{font-size:16px}p{margin:15px 0;font-size:15px}ul,ol{padding-left:25px;font-size:15px}li{padding-left:4px;margin:9px 0}table{width:100%;border-collapse:collapse;font-size:13px;line-height:1.8;margin:23px 0;overflow-wrap:anywhere}th{background:#eaf2e4;color:#426039;font-weight:600;text-align:left}th,td{border:1px solid #dce6d4;padding:11px 13px;vertical-align:top}tr:nth-child(even)td{background:#fafcf8}code{background:#eef4e9;border-radius:4px;padding:2px 5px;color:#5e7a4f;font-family:Consolas,monospace;font-size:.88em}pre{border:1px solid #e0e9d8;background:#f4f8ef;padding:17px 19px;border-radius:8px;overflow:auto;font-size:13px;line-height:1.85}pre code{background:none;padding:0;font-size:13px;color:#5b754b}blockquote{border-left:3px solid #b6cda2;padding:2px 20px;margin:20px 0;background:#f5f9f0;color:#7c956d}.foot{font-size:12px;color:#90a080;padding:0 10px 35px}.top-link{display:inline-block;margin-top:20px;font-size:12px}strong{font-weight:650}@media(max-width:900px){.layout{grid-template-columns:1fr;padding:0 17px;gap:20px}nav{position:static;display:flex;flex-wrap:wrap;gap:0;padding:14px}nav strong{width:100%}nav a{font-size:12px;padding:8px 10px}section{padding:27px}header{padding:38px 25px}header h1{font-size:28px}table{font-size:12px}th,td{padding:9px}}@media print{body{background:white;color:#222;font-size:11pt}.layout{display:block;max-width:none;margin:0;padding:0}nav,header .badges,.top-link{display:none}header{background:none;color:black;padding:0 0 20px}header h1{font-size:25pt;color:black}header p,header .label{color:#555}section{border:0;padding:0;margin:0;break-before:page}section h1{color:black;font-size:19pt}h2,h3{color:black;break-after:avoid}table,pre{break-inside:avoid}th{background:#eee;color:black}p,ul,ol{font-size:10pt;line-height:1.8}table{font-size:8.5pt}a{color:inherit}pre{white-space:pre-wrap;word-break:break-word}@page{size:A4;margin:20mm}}
    '''
    output='<!doctype html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>票序 项目开发与验收手册</title><style>'+style+'</style></head><body id="top"><header><span class="label">PIAO STUDIO / PROJECT HANDBOOK</span><h1>票序 智能财务发票系统<br>开发与交付手册</h1><p>从需求梳理、界面设计到识别、人工复核、归档和统计，说明项目如何运行、如何验证，以及如何演示与继续开发。</p><div class="badges"><span>React + FastAPI</span><span>本地 OCR</span><span>完整源码与模型</span><span>v2.0.0</span></div></header><div class="layout"><nav><strong>手册目录</strong>'+''.join(nav)+'</nav><article>'+''.join(sections)+'<div class="foot">票序 v2.0.0 · 本手册可离线阅读或通过浏览器打印为 PDF。<br>浏览器视觉验收、跨操作系统和 Docker 实机验证的限制已在验收报告中明确说明。<br><a class="top-link" href="#top">返回文档开头</a></div></article></div></body></html>'
    path=ROOT/'docs/piao-project-handbook.html';path.write_text(output,encoding='utf-8');print(path)


if __name__=='__main__':main()
