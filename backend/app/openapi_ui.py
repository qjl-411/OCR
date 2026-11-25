"""Dependency-free, offline-readable API reference generated from OpenAPI."""
import html
import json


def render(schema):
    escape=html.escape
    sections=[]
    for path,methods in schema.get('paths',{}).items():
        for method,operation in methods.items():
            if method not in ['get','post','patch','delete']:continue
            params=operation.get('parameters',[])
            rows=''.join(f"<tr><td><code>{escape(p['name'])}</code></td><td>{escape(p['in'])}</td><td>{'必填' if p.get('required') else '可选'}</td><td><code>{escape(json.dumps(p.get('schema',{}),ensure_ascii=False))}</code></td></tr>" for p in params)
            parameters=f'<h3>参数</h3><table><tr><th>名称</th><th>位置</th><th>约束</th><th>类型与默认值</th></tr>{rows}</table>' if rows else '<p>无查询或路径参数。</p>'
            body=operation.get('requestBody')
            request='<h3>请求体</h3><pre>'+escape(json.dumps(body,ensure_ascii=False,indent=2))+'</pre>' if body else ''
            sections.append(f"<details><summary><b class='{method}'>{method.upper()}</b><code>{escape(path)}</code><span>{escape(operation.get('summary',''))}</span></summary><div class='detail'>{parameters}{request}<h3>响应</h3><pre>{escape(json.dumps(operation.get('responses',{}),ensure_ascii=False,indent=2))}</pre></div></details>")
    components=escape(json.dumps(schema.get('components',{}),ensure_ascii=False,indent=2))
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>票序 接口参考</title><style>
    *{box-sizing:border-box}body{font-family:system-ui,"Microsoft YaHei",sans-serif;background:#f3f7f4;color:#263f2d;margin:0;padding:38px 20px;font-size:16px}main{max-width:1100px;margin:auto}header{padding:30px;background:#164c3d;color:#fff;border-radius:14px;margin-bottom:24px}header p{color:#c1d7c7;line-height:1.8}header a{color:#e3efd9}h1{font-size:28px;margin:0 0 16px}h2{font-size:20px;margin:28px 0 15px}h3{font-size:15px;color:#67815c;margin:22px 0 12px}p{font-size:14px;line-height:1.8}details{border:1px solid #dce6d6;border-radius:8px;background:white;margin:10px 0;overflow:hidden}summary{cursor:pointer;display:flex;gap:16px;align-items:center;flex-wrap:wrap;padding:17px;font-size:14px}summary b{font-size:12px;min-width:60px;text-align:center;padding:5px;border-radius:4px;background:#eaf3eb;color:#477451}.post{background:#edf2fc;color:#557da4}.delete{background:#faece8;color:#b7745d}.patch{background:#fbf3df;color:#ae9866}summary span{margin-left:auto;color:#8c9e81}code,pre{font-family:Consolas,monospace}.detail{padding:0 20px 22px}pre{font-size:13px;line-height:1.75;white-space:pre-wrap;word-break:break-all;background:#f6f9f3;border:1px solid #e6eedf;padding:18px;border-radius:7px;color:#5f7b51;max-height:500px;overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:11px;border:1px solid #e4ebdd;text-align:left}th{background:#f0f6e9}.note{padding:18px 22px;background:#fff;border:1px solid #e1eadb;border-radius:10px;color:#738a64}footer{font-size:12px;color:#93a28b;margin-top:30px}@media(max-width:600px){summary{gap:10px;font-size:12px}summary span{width:100%;margin-left:0}body{padding:20px 12px}header{padding:23px}h1{font-size:24px}.detail{padding:0 12px 15px}table{font-size:12px}th,td{padding:6px}}
    </style><main><header><h1>票序 智能发票系统 接口参考</h1><p>本地 API · OpenAPI 3 · v1.0.0<br>此页不依赖外部脚本或在线 CDN，离线也可阅读。</p><a href="openapi.json">查看 OpenAPI JSON</a></header><div class="note"><p>上传返回 202，代表任务被接收。请轮询任务状态获取逐文件结果。金额以字符串表示，未知值为 null。修改和复核需携带 revision，版本冲突返回 409。金额统计只计入已确认、非重复票据。</p></div><h2>接口列表</h2>'''+''.join(sections)+f'<h2>数据结构</h2><details><summary>展开完整模型定义</summary><div class="detail"><pre>{components}</pre></div></details><footer>默认地址 http://127.0.0.1:8000 · 单机教学项目</footer></main></html>'
