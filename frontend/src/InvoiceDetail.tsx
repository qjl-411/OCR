import { useEffect, useState } from 'react'
import { AlertTriangle, Check, CircleCheck, Eye, EyeOff, FileText, LoaderCircle, Minus, Plus, RotateCcw, Save, Trash2, X } from 'lucide-react'
import { api, jsonBody, yuan } from './api'
import { Badge, Modal, Source, Spinner } from './components'
import type { Invoice, Meta } from './types'

const EDIT_FIELDS=['invoice_number','invoice_code','invoice_date','invoice_type','buyer_name','buyer_tax_id','seller_name','seller_tax_id','subtotal','tax_amount','total','tax_rates','category','remark'] as const
type Form = Record<typeof EDIT_FIELDS[number],string>
const toForm=(r:Invoice)=>Object.fromEntries(EDIT_FIELDS.map(k=>[k,String(r[k]??'')])) as Form

export default function InvoiceDetail({id,meta,close,changed,toast}:{id:string;meta:Meta;close:()=>void;changed:()=>void;toast:(s:string,error?:boolean)=>void}) {
  const [record,setRecord]=useState<Invoice|null>(null),[form,setForm]=useState<Form|null>(null)
  const [error,setError]=useState(''),[busy,setBusy]=useState(''),[showBoxes,setShowBoxes]=useState(false),[focus,setFocus]=useState(''),[zoom,setZoom]=useState(100)
  const [reject,setReject]=useState(false),[note,setNote]=useState(''),[confirmDelete,setConfirmDelete]=useState(false),[tab,setTab]=useState('fields')
  useEffect(()=>{let live=true;api<Invoice>(`/api/invoices/${id}`).then(r=>{if(live){setRecord(r);setForm(toForm(r))}}).catch(e=>live&&setError(e.message));return()=>{live=false}},[id])
  const dirty=record&&form&&JSON.stringify(form)!==JSON.stringify(toForm(record))
  async function save() {
    if(!record||!form)return record
    const r=await api<Invoice>(`/api/invoices/${id}`,{method:'PATCH',...jsonBody({...form,revision:record.revision})})
    setRecord(r);setForm(toForm(r));changed();return r
  }
  async function act(action:string) {
    if(!record)return
    setBusy(action);setError('')
    try {
      if(action==='delete'){await api(`/api/invoices/${id}`,{method:'DELETE'});changed();toast('票据已删除');close();return}
      let r=record
      if(dirty)r=(await save())!
      if(action==='save'){toast('修改已保存，等待人工确认');return}
      r=await api<Invoice>(`/api/invoices/${id}/review`,{method:'POST',...jsonBody({revision:r.revision,verdict:action,note:action==='rejected'?note:''})})
      setRecord(r);setForm(toForm(r));setReject(false);changed();toast(action==='approved'?'票据已确认，已计入支出统计':action==='rejected'?'票据已驳回':'已退回待复核')
    } catch(e){setError((e as Error).message)} finally {setBusy('')}
  }
  const input=(key:typeof EDIT_FIELDS[number],label:string,opts:{wide?:boolean;type?:string;required?:boolean}={})=><label className={'field '+(opts.wide?'span-2':'')} key={key}><span>{label}{opts.required&&<em>*</em>}{record?.issues.some(x=>x.field===key)&&<AlertTriangle size={13} className="field-warning"/>}</span><input value={form?.[key]??''} type={opts.type||'text'} inputMode={['subtotal','tax_amount','total'].includes(key)?'decimal':undefined} onFocus={()=>{setFocus(key);setShowBoxes(true)}} onChange={e=>setForm({...form!,[key]:e.target.value})} className={record?.issues.some(x=>x.field===key)?'invalid':''}/></label>
  return <Modal title="发票复核工作区" close={close} wide footer={record&&<><span className="detail-footer-note">{record.source==='demo'?'教学演示票据 · 非真实发票':`第 ${record.page} 页 · ${record.engine==='pdf_text'?'文字层直接提取':'本地 OCR 识别'}`}</span><div className="button-row"><button className="icon-btn danger" title="删除票据" aria-label="删除票据" disabled={!!busy} onClick={()=>setConfirmDelete(true)}><Trash2 size={18}/></button>{record.status==='needs_review'?<button className="btn" disabled={!!busy} onClick={()=>{setReject(!reject);setConfirmDelete(false)}}>驳回</button>:<button className="btn" disabled={!!busy} onClick={()=>act('needs_review')}><RotateCcw size={16}/>退回复核</button>}<button className="btn" disabled={!!busy||!dirty} onClick={()=>act('save')}>{busy==='save'?<LoaderCircle className="spin" size={16}/>:<Save size={16}/>}保存修改</button>{record.status!=='approved'&&<button className="btn primary" disabled={!!busy} onClick={()=>act('approved')}>{busy==='approved'?<LoaderCircle className="spin" size={16}/>:<Check size={17}/>}确认通过</button>}</div></>}>
    {!record||!form?error?<div className="error-banner">{error}</div>:<Spinner/>:<>
      <div className="detail-summary"><span className="file-icon large"><FileText size={24}/></span><div><h3>{record.seller_name||record.filename}</h3><p className="mono">{record.invoice_number||'票号待识别'} <Source record={record}/></p></div><Badge record={record}/><strong className="summary-total">¥ {yuan(record.total)}</strong></div>
      {error&&<div role="alert" className="error-banner">{error}</div>}
      {confirmDelete&&<div className="inline-confirm"><div><strong>删除这张票据及其预览？</strong><p>此操作无法撤销，操作记录会保留。</p></div><button className="btn" onClick={()=>setConfirmDelete(false)}>取消</button><button className="btn danger-fill" disabled={!!busy} onClick={()=>act('delete')}>确认删除</button></div>}
      {reject&&<div className="reject-panel"><label>驳回原因<input autoFocus placeholder="例如：重复报销、票据不属于本项目" value={note} onChange={e=>setNote(e.target.value)}/></label><button className="btn" disabled={!note.trim()||!!busy} onClick={()=>act('rejected')}>确认驳回</button></div>}
      <div className="detail-body"><section className="preview-panel"><div className="preview-toolbar"><span>原始票据</span><div><button className={'icon-btn '+(showBoxes?'active':'')} title={showBoxes?'隐藏识别框':'显示识别框'} aria-label="切换识别框" onClick={()=>setShowBoxes(!showBoxes)}>{showBoxes?<Eye size={17}/>:<EyeOff size={17}/>}</button><span className="divider"/><button className="icon-btn" aria-label="缩小" disabled={zoom<=60} onClick={()=>setZoom(zoom-20)}><Minus size={16}/></button><small>{zoom}%</small><button className="icon-btn" aria-label="放大" disabled={zoom>=200} onClick={()=>setZoom(zoom+20)}><Plus size={16}/></button></div></div><div className="preview-scroll"><div className="invoice-image" style={{width:`${zoom}%`}}><img src={record.preview_url} alt="原始发票预览"/>{showBoxes&&record.boxes?.map(b=><button key={b.id} className={'ocr-box '+(record.evidence?.[focus]===b.id?'highlight':'')} style={{left:`${b.rect[0]*100}%`,top:`${b.rect[1]*100}%`,width:`${(b.rect[2]-b.rect[0])*100}%`,height:`${(b.rect[3]-b.rect[1])*100}%`}} title={`${b.text} · 分数 ${Math.round(b.score*100)}%`} aria-label={`识别文本 ${b.text}`} onClick={()=>toast(b.text)}/>)}</div></div><div className="preview-caption"><span>{record.engine==='pdf_text'?'PDF 文字层 · 坐标可追溯':`${record.engine==='ctpn_crnn_ctc'?'CTPN → CRNN → CTC':'PP-OCR 旧版对比'} · 平均分 ${Math.round(record.confidence*100)}%（非准确率）`}</span><a href={record.original_url} target="_blank" rel="noreferrer">打开原件</a></div></section>
      <section className="fields-panel"><div className="detail-tabs"><button className={tab==='fields'?'active':''} onClick={()=>setTab('fields')}>结构化信息</button><button className={tab==='text'?'active':''} onClick={()=>setTab('text')}>识别原文</button><button className={tab==='items'?'active':''} onClick={()=>setTab('items')}>项目明细</button></div><div className="fields-scroll">{tab==='fields'?<>
        {record.issues.length>0?<div className="issue-box"><strong><AlertTriangle size={16}/>请核对 {record.issues.length} 项提示</strong>{record.issues.map((i,n)=><button key={n} onClick={()=>{setFocus(i.field);setShowBoxes(true)}}>{i.message}</button>)}</div>:<div className="success-note"><CircleCheck size={16}/>必填字段和金额关系检查通过</div>}
        <h4>发票信息</h4><div className="form-grid">{input('invoice_number','发票号码',{required:true})}{input('invoice_date','开票日期',{required:true,type:'date'})}{input('invoice_code','发票代码（数电票可空）')}{input('invoice_type','发票类型')}</div>
        <h4>交易双方</h4><div className="form-grid">{input('buyer_name','购买方名称',{wide:true,required:true})}{input('buyer_tax_id','购买方税号',{wide:true})}{input('seller_name','销售方名称',{wide:true,required:true})}{input('seller_tax_id','销售方税号',{wide:true})}</div>
        <h4>金额与分类</h4><div className="form-grid">{input('subtotal','不含税金额',{required:true})}{input('tax_amount','税额',{required:true})}{input('total','价税合计',{required:true})}{input('tax_rates','税率 / 征收率')}<label className="field span-2"><span>费用分类</span><select value={form.category} onChange={e=>setForm({...form,category:e.target.value})}>{meta.categories.map(c=><option key={c}>{c}</option>)}</select></label><label className="field span-2"><span>复核备注</span><textarea rows={2} placeholder="记录费用用途或人工核对说明" value={form.remark} onChange={e=>setForm({...form,remark:e.target.value})}/></label></div><p className="hint">修改后将重新进入待复核。规则校验仅检查数据一致性，不能替代税务真伪查验。</p>
      </>:tab==='text'?<><p className="hint">保留初次提取文本，用于人工核对与问题追踪。保存字段不会覆盖这份原文。</p><pre className="raw-text">{record.raw_text||'未提取到文本'}</pre></>:<><p className="hint">以下为规则识别出的项目行，复杂多行表格请以原件为准。</p>{record.items?.length?<div className="item-list">{record.items.map((item,n)=><div key={n}><strong>{item.name}</strong><p>金额 {item.amount?`¥${yuan(item.amount)}`:'待核对'} · 税率 {item.tax_rate||'待核对'} · 税额 {item.tax_amount?`¥${yuan(item.tax_amount)}`:'待核对'}</p></div>)}</div>:<p>没有提取到可确认的项目明细，请查看原票。</p>}</>}</div></section></div>
    </>}
  </Modal>
}
