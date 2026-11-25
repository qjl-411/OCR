import { useEffect, useRef, useState } from 'react'
import { Archive, Check, CircleCheck, CloudUpload, FileText, LoaderCircle, ScanLine, ShieldCheck, X } from 'lucide-react'
import type { Job, Meta } from './types'
import { api, dateTime } from './api'
import { Empty } from './components'

export default function UploadPage({meta,open,changed,toast}:{meta:Meta;open:(id:string)=>void;changed:()=>void;toast:(s:string,error?:boolean)=>void}) {
  const [files,setFiles]=useState<File[]>([]),[drag,setDrag]=useState(false),[busy,setBusy]=useState(''),[jobs,setJobs]=useState<Job[]>([]),[error,setError]=useState(''),[forceOcr,setForceOcr]=useState(false)
  const input=useRef<HTMLInputElement>(null),seen=useRef(new Map<string,string>()),loaded=useRef(false)
  useEffect(()=>{let live=true
    const poll=()=>api<{items:Job[]}>('/api/jobs').then(r=>{if(!live)return;setJobs(r.items);for(const j of r.items){if(loaded.current&&seen.current.has(j.id)&&seen.current.get(j.id)!==j.status&&['completed','failed'].includes(j.status)){changed();toast(j.status==='completed'?`批次完成：成功 ${j.succeeded}，跳过 ${j.skipped}，失败 ${j.failed}`:'任务中断，请重新导入',j.status==='failed')}seen.current.set(j.id,j.status)}loaded.current=true}).catch(e=>live&&setError(e.message))
    poll();const timer=setInterval(poll,1600);return()=>{live=false;clearInterval(timer)}
  },[changed,toast])
  function add(incoming:FileList|File[]) {
    const valid=Array.from(incoming); const messages:string[]=[]
    const added=valid.filter(f=>{if(!/\.(pdf|png|jpe?g|zip)$/i.test(f.name)){messages.push(`${f.name}：不支持此格式`);return false}if(f.size>(/\.zip$/i.test(f.name)?100:20)*1024*1024){messages.push(`${f.name}：文件过大`);return false}return true})
    setFiles(old=>{const combined=[...old,...added.filter(f=>!old.some(v=>v.name===f.name&&v.size===f.size&&v.lastModified===f.lastModified))];if(combined.length>100){messages.push('单批最多 100 个文件');return combined.slice(0,100)}return combined})
    setError(messages.join('；'))
  }
  async function submit(source?:string) {
    if(!source&&!files.length)return
    setBusy(source||'upload');setError('')
    try {
      let job:Job
      // 不传 pipeline：服务端默认使用指定的 CTPN/CRNN/CTC 引擎，
      // 界面不提供引擎选择入口，避免用户误选。验收时仍可通过 API 显式指定。
      if(source)job=await api<Job>(`/api/datasets/${source}/import?force_ocr=${forceOcr}`,{method:'POST'})
      else {const data=new FormData();data.append('force_ocr',String(forceOcr));files.forEach(f=>data.append('files',f));job=await api<Job>('/api/imports',{method:'POST',body:data});setFiles([])}
      seen.current.set(job.id,job.status);setJobs(old=>[job,...old]);toast('任务已加入本地识别队列')
    }catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  const active=jobs.some(j=>['running','queued'].includes(j.status))
  return <><div className="page-heading"><div><span className="eyebrow">RECOGNITION CENTER</span><h1>识别中心</h1><p>上传电子发票或票据照片，系统自动整理成结构化台账。</p></div><span className="pill"><ShieldCheck size={16}/>文件在本机处理</span></div>
    <div className="upload-layout"><section className="panel upload-panel"><div className="panel-heading"><h2>上传发票</h2><span className="muted">PDF / PNG / JPG / ZIP</span></div><input type="file" ref={input} multiple accept=".pdf,.png,.jpg,.jpeg,.zip" className="sr-only" aria-label="选择发票文件" onChange={e=>{if(e.target.files)add(e.target.files);e.target.value=''}}/>
      <div className="upload-options"><label className="force-ocr"><input type="checkbox" checked={forceOcr} onChange={e=>setForceOcr(e.target.checked)}/>扫描件 PDF 按图片识别</label><span className="upload-option-note">电子发票自动读取内嵌文字，扫描件可勾选按图片识别</span></div>
      <div role="button" tabIndex={0} aria-label="点击或拖拽上传发票" className={'dropzone '+(drag?'dragging':'')} onClick={()=>input.current?.click()} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();input.current?.click()}}} onDragOver={e=>{e.preventDefault();setDrag(true)}} onDragLeave={()=>setDrag(false)} onDrop={e=>{e.preventDefault();setDrag(false);add(e.dataTransfer.files)}}><span className="upload-symbol"><CloudUpload size={30}/></span><h3>点击选择，或将发票拖到这里</h3><p>支持电子 PDF、纸质票照片，以及整包 ZIP 文件</p><span className="btn primary"><PlusIcon/>选择文件</span><div className="dropzone-spec"><span><b>PDF</b>电子发票、扫描件</span><span><b>PNG / JPG</b>票据照片</span><span><b>ZIP</b>整包批量</span></div><small>单个文件 ≤ 20 MB · ZIP / 每批 ≤ 100 MB · 最多 100 个文件</small></div>
      {error&&<div className="error-banner" role="alert">{error}</div>}
      {files.length>0&&<div className="upload-queue"><div className="queue-heading"><strong>待上传文件 <span>{files.length}</span></strong><button className="text-btn muted" onClick={()=>setFiles([])}>清空</button></div>{files.map((f,i)=><div className="queued-file" key={i}><span className="file-icon">{/\.zip$/i.test(f.name)?<Archive size={20}/>:<FileText size={20}/>}</span><div><strong>{f.name}</strong><small>{(f.size/1024/1024).toFixed(2)} MB</small></div><button className="icon-btn" aria-label={`移除 ${f.name}`} onClick={()=>setFiles(files.filter((_,n)=>n!==i))}><X size={17}/></button></div>)}<button className="btn primary full" disabled={!!busy} onClick={()=>submit()}>{busy==='upload'?<LoaderCircle className="spin" size={18}/>:<ScanLine size={18}/>}开始识别 {files.length} 个文件</button></div>}
      <div className="upload-features"><span><Check size={15}/>电子发票直接读取</span><span><Check size={15}/>图片离线识别</span><span><Check size={15}/>重复内容自动跳过</span></div></section>
    <section className="panel jobs-panel"><div className="panel-heading"><h2>识别任务</h2><span className={active?'live-label':'muted'}>{active?<><LoaderCircle size={14} className="spin"/>正在处理</>:'最近 30 个批次'}</span></div><div className="jobs-scroll">{jobs.length?jobs.map(j=><div className="job" key={j.id}><div className="job-title"><span className={'job-state '+j.status}>{['running','queued'].includes(j.status)?<LoaderCircle className="spin" size={21}/>:<CircleCheck size={21}/>}</span><div><strong>{j.source==='provided'?'发票数据集':j.source==='demo'?'示例数据集':'本地上传批次'}</strong><small>{dateTime(j.created_at)}</small></div><span className="job-status">{{queued:'等待处理',running:'识别中',completed:'已完成',failed:'已中断'}[j.status]||j.status}</span></div><div className="progress-track"><i style={{width:`${j.total?j.processed/j.total*100:0}%`}}/></div><div className="job-meta"><span>{j.processed} / {j.total} 文件</span><span>成功 {j.succeeded} · 跳过 {j.skipped} · 失败 {j.failed}</span></div>{j.current_file&&<p className="current-file">正在处理：{j.current_file}</p>}{j.error&&<p className="error-text">{j.error}</p>}<details><summary>查看批次明细{j.errors?.length?`（${j.errors.length} 条导入提示）`:''}</summary><div className="job-results">{j.results.map((r,i)=><div key={i} className={r.status==='failed'?'failed':''}><span><strong>{r.filename}</strong><small>{r.message}</small></span>{r.invoice_ids.length>0&&<button className="text-btn" onClick={()=>open(r.invoice_ids[0])}>查看</button>}</div>)}{j.errors?.map((e,i)=><p key={i} className="error-text">{e.filename}：{e.message}</p>)}</div></details></div>):<Empty title="还没有识别任务" text="上传文件后，可以在这里查看每个文件的处理结果。"/>}</div></section></div>
    </>
}
function PlusIcon(){return <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true"><path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/></svg>}
