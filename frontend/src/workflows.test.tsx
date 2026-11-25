// DOM interaction tests. These do not replace real-browser layout verification.
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Modal, InvoiceTable } from './components'
import InvoiceDetail from './InvoiceDetail'
import LedgerPage from './LedgerPage'
import UploadPage from './UploadPage'
import type { Invoice, Meta } from './types'

const meta:Meta={settings:{workspace_name:'测试工作区',confidence_threshold:.9,amount_tolerance:'0.02'},categories:['技术服务','办公采购'],ocr_available:true,provided_count:23,demo_count:12}
const invoice:Invoice={id:'test-id',filename:'demo.pdf',page:1,revision:1,created_at:'2026-11-19T12:00:00Z',updated_at:'2026-11-19T12:00:00Z',invoice_number:'99000000000000000001',invoice_code:'',invoice_date:'2026-11-19',invoice_type:'电子普通发票',buyer_name:'示例购买方',buyer_tax_id:'DEMO00000000000001',seller_name:'示例销售方',seller_tax_id:'DEMO00000000000002',subtotal:'100.00',tax_amount:'6.00',total:'106.00',tax_rates:'6%',category:'技术服务',remark:'',status:'needs_review',source:'demo',engine:'pdf_text',confidence:1,duplicate:false,issues:[],completeness:100,preview_url:'/preview.jpg',original_url:'/original.pdf',boxes:[],raw_text:'原始识别文本'}
const response=(value:unknown)=>Promise.resolve(new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}}))
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()})

describe('票据工作流交互',()=>{
  it('表格显示演示来源，选择和打开详情各自生效',async()=>{
    const open=vi.fn(),select=vi.fn();render(<InvoiceTable items={[invoice]} selected={new Set()} select={select} open={open}/>)
    expect(screen.getByText('演示')).toBeTruthy()
    await userEvent.click(screen.getByLabelText('选择本页全部发票'));expect(select).toHaveBeenCalledWith(['test-id'])
    await userEvent.click(screen.getByText('复核'));expect(open).toHaveBeenCalledWith('test-id')
    expect(screen.getByText('¥ 106.00')).toBeTruthy()
  })
  it('弹窗约束焦点并可通过 Escape 关闭',async()=>{
    const close=vi.fn();render(<Modal title="可访问弹窗" close={close}><button>测试操作</button></Modal>)
    expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true')
    expect(document.activeElement).toBe(screen.getByLabelText('关闭弹窗'))
    fireEvent.keyDown(document,{key:'Escape'});expect(close).toHaveBeenCalledTimes(1)
  })
  it('保存修订后使用新版本号确认，不会确认旧版本',async()=>{
    const calls:{url:string;method:string;body:any}[]=[]
    vi.stubGlobal('fetch',vi.fn((url:string,opts:RequestInit={})=>{
      calls.push({url,method:opts.method||'GET',body:opts.body?JSON.parse(String(opts.body)):null})
      if(opts.method==='PATCH')return response({...invoice,revision:2,remark:'人工核对'})
      if(url.endsWith('/review'))return response({...invoice,revision:3,status:'approved',remark:'人工核对'})
      return response(invoice)
    }))
    render(<InvoiceDetail id="test-id" meta={meta} close={vi.fn()} changed={vi.fn()} toast={vi.fn()}/>)
    await screen.findByText('示例销售方')
    const remark=screen.getByPlaceholderText('记录费用用途或人工核对说明');await userEvent.type(remark,'人工核对')
    await userEvent.click(screen.getByText('确认通过'))
    await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/review'))).toBe(true))
    const mutation=calls.filter(c=>c.method!=='GET')
    expect(mutation.map(c=>c.method)).toEqual(['PATCH','POST'])
    expect(mutation[0].body.revision).toBe(1);expect(mutation[1].body.revision).toBe(2)
  })
  it('台账导出包含当前来源条件和勾选记录',async()=>{
    vi.stubGlobal('fetch',vi.fn(()=>response({items:[invoice],total:1})))
    const onExport=vi.fn();render(<LedgerPage meta={meta} refresh={0} open={vi.fn()} navigateUpload={vi.fn()} onExport={onExport}/>)
    await screen.findByText('示例销售方')
    await userEvent.click(screen.getByText('合成演示'))
    await screen.findByText('示例销售方')
    await userEvent.click(screen.getByLabelText('选择本页全部发票'))
    await userEvent.click(screen.getByText('导出所选 (1)'))
    expect(onExport).toHaveBeenCalledWith(expect.objectContaining({source:'demo',ids:'test-id'}))
  })
  it('无效上传格式被拦截，不会进入队列',async()=>{
    vi.stubGlobal('fetch',vi.fn(()=>response({items:[]})))
    render(<UploadPage meta={meta} open={vi.fn()} changed={vi.fn()} toast={vi.fn()}/>)
    const input=screen.getByLabelText('选择发票文件')
    fireEvent.change(input,{target:{files:[new File(['bad'],'bad.exe')]}})
    expect(await screen.findByRole('alert')).toHaveProperty('textContent','bad.exe：不支持此格式')
    expect(screen.queryByText(/开始识别 1 个文件/)).toBeNull()
  })
})
