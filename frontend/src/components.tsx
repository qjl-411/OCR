import { useEffect, useRef, type ReactNode } from 'react'
import { Check, ChevronLeft, ChevronRight, FileText, Inbox, LoaderCircle, X } from 'lucide-react'
import type { Invoice } from './types'
import { yuan } from './api'

export function Spinner({ label = '正在读取数据' }: {label?: string}) { return <div className="loading"><LoaderCircle className="spin" size={24}/><span>{label}</span></div> }
export function Empty({ title='还没有票据', text='上传第一张发票，开始整理你的财务数据。', action }: {title?: string; text?: string; action?: ReactNode}) { return <div className="empty"><span className="empty-icon"><Inbox size={30}/></span><h3>{title}</h3><p>{text}</p>{action}</div> }
export function Badge({ record }: {record: Invoice}) {
  const status = record.duplicate ? 'duplicate' : record.status
  return <span className={`badge ${status}`}><i/>{({approved:'已确认',needs_review:'待复核',rejected:'已驳回',duplicate:'重复票据'})[status]}</span>
}
export function Source({ record }: {record: Invoice}) { return <span className={'source ' + (record.source==='demo'?'demo':'')}>{record.source==='demo'?'合成演示':record.engine==='pdf_text'?'电子 PDF':'图片 OCR'}</span> }
export function Modal({ title, children, close, wide=false, footer }: {title: string; children: ReactNode; close: () => void; wide?: boolean; footer?: ReactNode}) {
  const ref=useRef<HTMLDivElement>(null)
  useEffect(() => {
    const previous=document.activeElement as HTMLElement
    const old=document.body.style.overflow; document.body.style.overflow='hidden'
    const focusable=()=>Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input:not(:disabled),select,textarea,[tabindex="0"]')||[])
    focusable()[0]?.focus()
    const handle=(e: KeyboardEvent)=>{if(e.key==='Escape')close(); if(e.key==='Tab'){const list=focusable();const first=list[0],last=list[list.length-1];if(e.shiftKey && document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey && document.activeElement===last){e.preventDefault();first?.focus()}}}
    document.addEventListener('keydown',handle)
    return ()=>{document.body.style.overflow=old;document.removeEventListener('keydown',handle);previous?.focus()}
  },[close])
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)close()}}><div ref={ref} role="dialog" aria-modal="true" aria-label={title} className={'modal '+(wide?'wide':'')}><header className="modal-head"><h2>{title}</h2><button className="icon-btn" onClick={close} aria-label="关闭弹窗"><X size={22}/></button></header><div className="modal-content">{children}</div>{footer&&<footer className="modal-foot">{footer}</footer>}</div></div>
}
export function Pagination({ page, total, size, change }: {page: number; total: number; size: number; change: (n:number)=>void}) {
  const pages=Math.max(1,Math.ceil(total/size))
  return <div className="pagination"><span>共 {total} 张票据{total>0 && `，当前 ${(page-1)*size+1}–${Math.min(page*size,total)} 条`}</span><div><button className="icon-btn" disabled={page<=1} aria-label="上一页" onClick={()=>change(page-1)}><ChevronLeft size={18}/></button><span>{page} / {pages}</span><button className="icon-btn" disabled={page>=pages} aria-label="下一页" onClick={()=>change(page+1)}><ChevronRight size={18}/></button></div></div>
}
export function InvoiceTable({ items, open, selected, select, compact=false }: {items: Invoice[]; open:(id:string)=>void; selected?:Set<string>; select?:(ids:string[])=>void; compact?:boolean}) {
  return <div className="table-scroll"><table className="invoice-table"><thead><tr>{select&&<th className="check-col"><input type="checkbox" aria-label="选择本页全部发票" checked={items.length>0&&items.every(r=>selected?.has(r.id))} onChange={e=>select(e.target.checked?[...new Set([...(selected||[]),...items.map(r=>r.id)])]:[...(selected||[])].filter(id=>!items.some(r=>r.id===id)))}/></th>}<th>发票 / 销售方</th>{!compact&&<th>开票日期</th>}<th>费用分类</th><th className="align-right">价税合计</th><th>状态</th><th className="align-right">操作</th></tr></thead><tbody>{items.map(r=><tr key={r.id}>{select&&<td><input type="checkbox" aria-label={`选择 ${r.invoice_number||r.filename}`} checked={selected?.has(r.id)||false} onChange={e=>select(e.target.checked?[...(selected||[]),r.id]:[...(selected||[])].filter(id=>id!==r.id))}/></td>}<td><button className="invoice-cell" onClick={()=>open(r.id)}><span className={'file-icon '+(r.engine==='ocr'?'blue':'')}><FileText size={20}/></span><span><strong title={r.seller_name||r.filename}>{r.seller_name||'销售方待识别'}</strong><small className="mono">{r.invoice_number||'票号待识别'}{r.source==='demo'&&<em className="row-demo">演示</em>}</small></span></button></td>{!compact&&<td className="nowrap">{r.invoice_date||'—'}</td>}<td><span className="category-label">{r.category}</span></td><td className="amount align-right">{r.total===null?'—':`¥ ${yuan(r.total)}`}</td><td><Badge record={r}/></td><td className="align-right"><button className="text-btn" onClick={()=>open(r.id)}>{r.status==='needs_review'?'复核':'查看'}</button></td></tr>)}</tbody></table></div>
}
export function CheckLine({ children }: {children:ReactNode}) {return <span className="check-line"><Check size={16}/>{children}</span>}
