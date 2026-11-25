import { useCallback, useEffect, useState } from 'react'
import { ChartNoAxesCombined, Check, ChevronDown, ChevronRight, ClipboardCheck, Download, Files, FileText, HelpCircle, LayoutDashboard, LoaderCircle, LogOut, Menu, Plus, ReceiptText, ScanLine, Search, Settings2, ShieldCheck, Wallet, X, Activity, AlertTriangle, CalendarDays } from 'lucide-react'
import { api, downloadExport, yuan } from './api'
import { Badge, CheckLine, Empty, InvoiceTable, Modal, Spinner } from './components'
import { CategoryChart, TrendChart } from './charts'
import type { Dashboard, Meta, Page } from './types'
import InvoiceDetail from './InvoiceDetail'
import LedgerPage from './LedgerPage'
import UploadPage from './UploadPage'
import { AnalyticsPage, AuditPage, SettingsPage } from './ManagementPages'
import AuthPage, { authHeaders, readSession, writeSession } from './AuthPage'
import type { Session } from './AuthPage'

const PAGES:Record<Page,string>={dashboard:'工作台',upload:'识别中心',invoices:'发票台账',analytics:'分析报告',audit:'操作记录',settings:'系统设置'}
const validPage=()=>Object.hasOwn(PAGES,location.hash.slice(1))?location.hash.slice(1) as Page:'dashboard'

export default function App(){
  const [session,setSession]=useState<Session|null>(()=>readSession())
  const [checking,setChecking]=useState(!!session)
  // 启动时用后端校验令牌；无效或已停用则回登录页。
  useEffect(()=>{
    if(!session){setChecking(false);return}
    let live=true
    fetch('/api/auth/me',{headers:authHeaders()})
      .then(r=>r.ok?r.json():Promise.reject(new Error('invalid')))
      .then(d=>{if(live)setSession({...session,...d.user,token:session.token})})
      .catch(()=>{if(live){writeSession(null);setSession(null)}})
      .finally(()=>{if(live)setChecking(false)})
    return()=>{live=false}
  },[])
  if(checking)return <main className="app-loading"><span className="logo-icon"><ReceiptText/></span><h1>票序</h1><Spinner label="正在验证登录状态"/></main>
  if(!session)return <AuthPage onSignedIn={setSession}/>
  return <Workspace session={session} onSignOut={()=>{writeSession(null);setSession(null)}}/>
}

function Workspace({session,onSignOut}:{session:Session;onSignOut:()=>void}){
  const [page,setPage]=useState<Page>(validPage),[meta,setMeta]=useState<Meta|null>(null),[overview,setOverview]=useState<Dashboard|null>(null),[refresh,setRefresh]=useState(0),[error,setError]=useState('')
  const [detail,setDetail]=useState(''),[exportParams,setExportParams]=useState<Record<string,string>|null>(null),[format,setFormat]=useState('xlsx'),[exportBusy,setExportBusy]=useState(false)
  const [toastMsg,setToastMsg]=useState<{text:string;error:boolean;id:number}|null>(null),[menu,setMenu]=useState(false),[query,setQuery]=useState(''),[queryInput,setQueryInput]=useState(''),[ledgerTab,setLedgerTab]=useState('')
  const toast=useCallback((text:string,error=false)=>setToastMsg({text,error,id:Date.now()}),[])
  const changed=useCallback(()=>setRefresh(v=>v+1),[]),closeDetail=useCallback(()=>setDetail(''),[]),closeExport=useCallback(()=>setExportParams(null),[])
  useEffect(()=>{if(toastMsg){const id=setTimeout(()=>setToastMsg(null),5000);return()=>clearTimeout(id)}},[toastMsg])
  useEffect(()=>{let live=true;Promise.all([api<Meta>('/api/meta'),api<Dashboard>('/api/dashboard')]).then(([m,d])=>{if(live){setMeta(m);setOverview(d);setError('')}}).catch(e=>live&&setError(e.message));return()=>{live=false}},[refresh])
  useEffect(()=>{const fn=()=>setPage(validPage());window.addEventListener('hashchange',fn);return()=>window.removeEventListener('hashchange',fn)},[])
  const go=(p:Page,tab='')=>{setLedgerTab(tab);setPage(p);location.hash=p;setMenu(false);window.scrollTo({top:0})}
  const openExport=(params:Record<string,string>={})=>{setFormat('xlsx');setExportParams(params)}
  async function doExport(){if(!exportParams)return;setExportBusy(true);try{await downloadExport({...exportParams,format});setExportParams(null);toast('文件已生成，下载已开始');changed()}catch(e){toast((e as Error).message,true)}finally{setExportBusy(false)}}
  const search=()=>{setQuery(queryInput);go('invoices')}
  if(error&&!meta)return <main className="fatal"><span className="logo-icon"><ReceiptText/></span><h1>暂时无法连接工作区</h1><p>{error}</p><p>请确认后端服务已启动，再刷新页面。</p><button className="btn primary" onClick={changed}>重新连接</button></main>
  if(!meta||!overview)return <main className="app-loading"><span className="logo-icon"><ReceiptText/></span><h1>票序</h1><Spinner label="正在打开本地财务工作区"/></main>
  const nav=(p:Page,Icon:typeof LayoutDashboard)=> <button key={p} onClick={()=>go(p)} className={'nav-item '+(page===p?'active':'')}><Icon size={20}/><span>{PAGES[p]}</span>{p==='invoices'&&overview.pending_count>0&&<b>{overview.pending_count}</b>}{page===p&&<i/>}</button>
  const initials=(session.name||session.email||'财').trim().slice(0,1).toUpperCase()
  return <div className="app-shell">{menu&&<div className="sidebar-scrim" onClick={()=>setMenu(false)}/>}<aside className={'sidebar '+(menu?'open':'')}><a className="brand" href="#dashboard" onClick={()=>go('dashboard')}><span className="logo-icon"><ReceiptText size={24}/></span><span><strong>票序</strong><small>INVOICE WORKSPACE</small></span></a><button className="workspace-button" onClick={()=>go('settings')}><span className="workspace-avatar">{(session.company||'财').trim().slice(0,1)}</span><span><strong>{session.company||'我的财务工作区'}</strong><small>{session.name||session.email}</small></span><ChevronDown size={14}/></button><div className="nav-label">工作空间</div><nav aria-label="主导航">{nav('dashboard',LayoutDashboard)}{nav('upload',ScanLine)}{nav('invoices',Files)}</nav><div className="nav-label second">洞察与管理</div><nav aria-label="管理导航">{nav('analytics',ChartNoAxesCombined)}{nav('audit',Activity)}{nav('settings',Settings2)}</nav><div className="sidebar-bottom"><div className="local-card"><ShieldCheck size={22}/><strong>本地处理，安心整理</strong><p>发票与识别结果保存在本机<br/>无需云端识别密钥</p><span>OFFLINE READY</span></div><button className="signout-btn" onClick={onSignOut}><LogOut size={16}/>退出登录</button><div className="sidebar-version"><span>票序 v2.0</span><span>让票据井然有序</span></div></div></aside>
  <div className="main-shell"><header className="topbar"><button className="icon-btn mobile-menu" aria-label="打开导航菜单" onClick={()=>setMenu(true)}><Menu size={23}/></button><div className="breadcrumb"><span>工作空间</span><ChevronRight size={14}/><strong>{PAGES[page]}</strong></div><form className="global-search" onSubmit={e=>{e.preventDefault();search()}}><Search size={17}/><input aria-label="全局搜索发票" placeholder="搜索发票、销售方..." value={queryInput} onChange={e=>setQueryInput(e.target.value)}/><button aria-label="执行搜索" title="执行搜索" type="submit"><kbd>↵</kbd></button></form><div className="topbar-actions"><span className="local-status"><ShieldCheck size={15}/>本地工作区</span><button className="icon-btn help-button" title="使用帮助" aria-label="使用帮助" onClick={()=>go('settings')}><HelpCircle size={19}/></button><div className="user-chip"><span className="user-avatar">{initials}</span><span className="user-name">{session.name||session.email}</span></div></div></header><main className="main-content">{error&&<div className="error-banner">{error}<button className="text-btn" onClick={changed}>重试</button></div>}{page==='dashboard'?<DashboardPage data={overview} open={setDetail} go={go} onExport={openExport}/>:page==='upload'?<UploadPage meta={meta} open={setDetail} changed={changed} toast={toast}/>:page==='invoices'?<LedgerPage key={page} meta={meta} initialTab={ledgerTab} globalQuery={query} refresh={refresh} open={setDetail} navigateUpload={()=>go('upload')} onExport={openExport}/>:page==='analytics'?<AnalyticsPage refresh={refresh} onExport={openExport}/>:page==='audit'?<AuditPage refresh={refresh} open={setDetail}/>:<SettingsPage meta={meta} changed={changed} toast={toast}/>}<footer className="app-footer"><span>票序 · 智能发票工作台</span><span><ShieldCheck size={13}/>本地数据 · 人工确认 · 清晰可追溯</span></footer></main></div>
  {detail&&<InvoiceDetail key={detail} id={detail} meta={meta} close={closeDetail} changed={changed} toast={toast}/>}
  {exportParams&&<Modal title="导出发票数据" close={closeExport} footer={<><button className="btn" onClick={closeExport}>取消</button><button className="btn primary" disabled={exportBusy} onClick={doExport}>{exportBusy?<LoaderCircle className="spin" size={17}/>:<Download size={17}/>}生成并下载</button></>}><p className="export-intro">{exportParams.ids?`导出勾选的 ${exportParams.ids.split(',').length} 张票据。`:'导出当前筛选范围内的全部票据。'}状态与异常提示会一并保留。</p><div className="export-options">{[['xlsx','Excel 工作簿','发票明细与汇总说明，便于归档与统计'],['csv','CSV 表格','UTF-8 编码，适合数据交换'],['json','JSON 数据','结构化字段，适合系统对接']].map(([key,label,desc])=><label key={key} className={format===key?'selected':''}><input type="radio" name="format" value={key} checked={format===key} onChange={()=>setFormat(key)}/><span className="file-icon"><FileText size={22}/></span><span><strong>{label}</strong><small>{desc}</small></span>{format===key&&<Check size={19}/>}</label>)}</div><div className="info-note">Excel 中的票号和税号按文本保存，避免长数字丢失。</div></Modal>}
  {toastMsg&&<div role={toastMsg.error?'alert':'status'} className={'toast '+(toastMsg.error?'error':'')}><span>{toastMsg.error?<AlertTriangle size={19}/>:<Check size={19}/>}</span>{toastMsg.text}<button className="icon-btn" aria-label="关闭提示" onClick={()=>setToastMsg(null)}><X size={17}/></button></div>}
  </div>
}

function DashboardPage({data:baseData,open,go,onExport}:{data:Dashboard;open:(id:string)=>void;go:(p:Page,tab?:string)=>void;onExport:(p?:Record<string,string>)=>void}) {
  const [source,setSource]=useState(''),[scoped,setScoped]=useState<Dashboard|null>(null),[scopeError,setScopeError]=useState('')
  useEffect(()=>{let live=true;if(!source){setScoped(null);return}api<Dashboard>('/api/dashboard?'+new URLSearchParams({source})).then(r=>{if(live){setScoped(r);setScopeError('')}}).catch(e=>live&&setScopeError(e.message));return()=>{live=false}},[source,baseData])
  const data=scoped||baseData
  const cards=[{label:'累计票据',value:String(data.total_count),unit:'张',note:`已确认 ${data.approved_count} 张`,icon:Files,color:'green'},
    {label:'已确认支出',value:yuan(data.total_amount),unit:'元',note:`票面税额 ¥ ${yuan(data.tax_amount)}`,icon:Wallet,color:'blue'},
    {label:'待复核票据',value:String(data.pending_count),unit:'张',note:'完成核对后计入统计',icon:ClipboardCheck,color:'amber'},
    {label:'异常提示',value:String(data.anomaly_count),unit:'张',note:`其中重复票据 ${data.duplicate_count} 张`,icon:ShieldCheck,color:'purple'}]
  return <><div className="page-heading dashboard-heading"><div><span className="eyebrow">YOUR FINANCE, IN ORDER</span><h1>工作台</h1><p>从识别到归档，清晰掌握每一笔支出。</p></div><div className="button-row"><button className="btn" onClick={()=>onExport({source})}><Download size={17}/>导出报表</button><button className="btn primary" onClick={()=>go('upload')}><Plus size={18}/>上传发票</button></div></div>
    <div className="dashboard-scope"><span><CalendarDays size={15}/>开票日期汇总 · 全部时间</span><select aria-label="工作台数据来源" value={source} onChange={e=>setSource(e.target.value)}><option value="">全部数据来源</option><option value="provided">提供的数据集</option><option value="upload">本地上传</option><option value="demo">合成演示</option></select></div>{scopeError&&<div className="error-banner">{scopeError}</div>}<div className="metrics">{cards.map((c,i)=><button className="metric" key={c.label} onClick={()=>go('invoices',i===2?'needs_review':i===3?'anomaly':'')}><div className="metric-top"><span>{c.label}</span><span className={'metric-icon '+c.color}><c.icon size={19}/></span></div><strong>{c.value}<small>{c.unit}</small></strong><div className="metric-note">{i===0&&<Check size={14}/>}{i===2&&<span className="amber-dot"/>}{c.note}</div></button>)}</div>
    <div className="charts-grid"><section className="panel"><div className="panel-heading"><div><h2>支出趋势</h2><p>已确认票据 · 近六个开票月份</p></div><span className="chart-key"><i/>人民币 / 元</span></div><TrendChart data={data.trend}/></section><section className="panel"><div className="panel-heading"><div><h2>费用构成</h2><p>按已确认金额</p></div><button className="text-btn" onClick={()=>go('analytics')}>查看分析</button></div><CategoryChart data={data.categories} count={data.approved_count}/></section></div>
    <div className="dashboard-bottom"><section className="panel recent-panel"><div className="panel-heading"><h2>最近导入</h2><button className="text-btn" onClick={()=>go('invoices')}>查看全部</button></div>{data.recent.length?<InvoiceTable items={data.recent.slice(0,5)} open={open} compact/>:<Empty action={<button className="btn primary" onClick={()=>go('upload')}>上传发票</button>}/>}<div className="table-footnote">初始示例均为合成演示。你提供的真实发票可在识别中心一键导入。</div></section><section className="panel todo-panel"><div className="panel-heading"><h2>复核待办</h2><span className="todo-count">{data.pending_count}</span></div><div className="todo-summary"><span><ClipboardCheck size={27}/></span><h3>{data.pending_count?'还有票据等待你的确认':'所有票据都已处理'}</h3><p>{data.pending_count?'核对识别信息，确保每一笔记录准确。':'继续上传新发票，保持台账井然有序。'}</p></div><button className="todo-row" onClick={()=>go('invoices','duplicate')}><span className="todo-dot amber"/><span>重复票据提醒</span><b>{data.duplicate_count}</b><ChevronRight size={16}/></button><button className="todo-row" onClick={()=>go('invoices','anomaly')}><span className="todo-dot purple"/><span>需关注的异常</span><b>{data.anomaly_count}</b><ChevronRight size={16}/></button><button className="btn full" onClick={()=>go('invoices','needs_review')}>前往复核工作区</button></section></div>
    <div className="privacy-strip"><ShieldCheck size={20}/><div><strong>识别在本地，数据由你掌握</strong><span>无需上传到第三方 OCR 服务，支持离线识别与本地导出。</span></div><CheckLine>人工确认后归档</CheckLine></div>
    </>
}
