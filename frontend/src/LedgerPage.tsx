import { useEffect, useState } from 'react'
import { Download, Filter, Search, SlidersHorizontal, Upload, X } from 'lucide-react'
import { api } from './api'
import { Empty, InvoiceTable, Pagination, Spinner } from './components'
import type { Filters, Invoice, Meta } from './types'

const INITIAL:Filters={q:'',status:'',category:'',source:'',start:'',end:'',sort:'newest'}
const TABS:readonly [string,string][]=[['','全部票据'],['needs_review','待复核'],['approved','已确认'],['duplicate','重复票据'],['anomaly','异常票据'],['rejected','已驳回']]

export default function LedgerPage({meta,initialTab='',globalQuery='',refresh,open,navigateUpload,onExport}:{meta:Meta;initialTab?:string;globalQuery?:string;refresh:number;open:(id:string)=>void;navigateUpload:()=>void;onExport:(p:Record<string,string>)=>void}) {
  const [filters,setFilters]=useState<Filters>({...INITIAL,status:initialTab,q:globalQuery}),[page,setPage]=useState(1),[selected,setSelected]=useState<Set<string>>(new Set())
  const [data,setData]=useState<{items:Invoice[];total:number}>({items:[],total:0}),[busy,setBusy]=useState(true),[error,setError]=useState(''),[extra,setExtra]=useState(false)
  useEffect(()=>{setFilters(f=>({...f,q:globalQuery,status:initialTab}));setPage(1);setSelected(new Set())},[globalQuery,initialTab])
  useEffect(()=>{let live=true;setBusy(true);const timer=setTimeout(()=>{api<{items:Invoice[];total:number}>('/api/invoices?'+new URLSearchParams({...filters,page:String(page),page_size:'10'})).then(r=>{if(live){setData(r);setError('');if(page>1&&(page-1)*10>=r.total)setPage(Math.max(1,Math.ceil(r.total/10)))}}).catch(e=>live&&setError(e.message)).finally(()=>live&&setBusy(false))},filters.q?220:0);return()=>{live=false;clearTimeout(timer)}},[filters,page,refresh])
  const change=(key:keyof Filters,value:string)=>{setFilters(f=>({...f,[key]:value}));setPage(1);setSelected(new Set())}
  const hasFilter=Object.entries(filters).some(([k,v])=>v&&!(k==='status'&&!initialTab)&&!(k==='sort'&&v==='newest'))
  const activeTab=filters.status
  const heading=activeTab==='needs_review'?['待复核票据','对照原票核对关键字段，让每一笔入账都有依据。']:activeTab==='duplicate'?['重复票据','相同发票代码与号码的票据已阻断确认，请确认保留哪一张。']:activeTab==='anomaly'?['异常票据','存在字段缺失、金额不平或格式异常的票据需要处理。']:activeTab==='approved'?['已确认票据','已经人工核对并归档的票据。']:activeTab==='rejected'?['已驳回票据','已标记为无效或不属于本项目的票据。']:['发票台账','集中管理每一张发票，快速查找、复核与导出。']
  return <><div className="page-heading"><div><span className="eyebrow">INVOICE LIBRARY</span><h1>{heading[0]}<small>{data.total}</small></h1><p>{heading[1]}</p></div><div className="button-row"><button className="btn" onClick={()=>onExport({...filters,ids:[...selected].join(',')})}><Download size={17}/>{selected.size?`导出所选 (${selected.size})`:'导出数据'}</button><button className="btn primary" onClick={navigateUpload}><Upload size={17}/>上传发票</button></div></div>
    <section className="panel ledger-panel"><div className="ledger-tabs">{TABS.map(([value,label])=><button key={value} className={activeTab===value?'active':''} onClick={()=>change('status',value)}>{label}</button>)}</div>
      <div className="filterbar"><div className="search-input"><Search size={18}/><input aria-label="搜索发票" placeholder="搜索票号、销售方或文件名" value={filters.q} onChange={e=>change('q',e.target.value)}/>{filters.q&&<button className="icon-btn" aria-label="清除搜索" onClick={()=>change('q','')}><X size={14}/></button>}</div><select aria-label="费用分类筛选" value={filters.category} onChange={e=>change('category',e.target.value)}><option value="">全部分类</option>{meta.categories.map(c=><option key={c}>{c}</option>)}</select><select aria-label="排序方式" value={filters.sort} onChange={e=>change('sort',e.target.value)}><option value="newest">最近导入</option><option value="date_desc">开票日期从新到旧</option><option value="amount_desc">金额从高到低</option></select><button className={'btn filter-toggle '+(extra?'active':'')} onClick={()=>setExtra(!extra)}><SlidersHorizontal size={17}/>日期</button>{hasFilter&&<button className="text-btn muted" onClick={()=>{setFilters({...INITIAL});setPage(1);setSelected(new Set())}}>重置</button>}</div>
      <div className="source-filters"><span>数据来源</span>{[['','全部'],['provided','提供的数据集'],['upload','本地上传'],['demo','合成演示']].map(([key,label])=><button className={filters.source===key?'active':''} key={key} onClick={()=>change('source',key)}>{label}</button>)}</div>
      {extra&&<div className="date-filters"><label>开票日期从<input aria-label="开始日期" type="date" value={filters.start} max={filters.end} onChange={e=>change('start',e.target.value)}/></label><span>至</span><label>结束日期<input aria-label="结束日期" type="date" value={filters.end} min={filters.start} onChange={e=>change('end',e.target.value)}/></label></div>}
      {selected.size>0&&<div className="selection-bar"><span>已选择 {selected.size} 张票据</span><button className="text-btn" onClick={()=>setSelected(new Set())}>取消选择</button></div>}
      {error?<div className="error-banner" role="alert">{error}</div>:busy?<Spinner/>:data.items.length?<InvoiceTable items={data.items} open={open} selected={selected} select={ids=>setSelected(new Set(ids))}/>:<Empty title={hasFilter?'没有找到符合条件的发票':'暂无票据'} text={hasFilter?'试试调整搜索词或筛选条件。':'上传电子发票或票据图片，建立你的第一份台账。'} action={<button className="btn" onClick={hasFilter?()=>{setFilters({...INITIAL});setPage(1)}:navigateUpload}>{hasFilter?'清除筛选':'上传发票'}</button>}/>}
      <Pagination page={page} total={data.total} size={10} change={setPage}/></section><div className="page-caption"><span>金额以原票人民币计价；导出遵循当前筛选条件。</span><span><Filter size={14}/>仅已确认且非重复票据计入金额统计</span></div>
    </>
}
