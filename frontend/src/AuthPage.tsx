import { useCallback, useEffect, useMemo, useState } from 'react'
import { ArrowRight, BarChart3, Check, Eye, EyeOff, Lock, Mail, ShieldCheck, Sparkles, User, Building2, ReceiptText, LoaderCircle, RefreshCw, Info } from 'lucide-react'

type Mode = 'login' | 'register'
export type Session = { id: number; email: string; name: string; company: string; token: string }

const KEY = 'piao-studio.session'
export const TOKEN_KEY = 'piao-studio.token'

export function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    const value = JSON.parse(raw) as Session
    return value && value.email && value.token ? value : null
  } catch { return null }
}
export function writeSession(session: Session | null) {
  try {
    if (session) {
      localStorage.setItem(KEY, JSON.stringify(session))
      localStorage.setItem(TOKEN_KEY, session.token)
    } else {
      localStorage.removeItem(KEY)
      localStorage.removeItem(TOKEN_KEY)
    }
  } catch { /* storage unavailable */ }
}

export function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function strengthOf(password: string) {
  let score = 0
  if (password.length >= 8) score++
  if (/[A-Z]/.test(password) && /[a-z]/.test(password)) score++
  if (/\d/.test(password)) score++
  if (/[^A-Za-z0-9]/.test(password)) score++
  return Math.min(score, 4)
}
const STRENGTH = [
  { label: '强度不足', color: '#c9564e' },
  { label: '强度偏弱', color: '#c98a3f' },
  { label: '强度一般', color: '#b8973f' },
  { label: '强度良好', color: '#5d9c78' },
  { label: '强度很高', color: '#3f8a5e' },
]

async function post<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    const detail = (data as { detail?: string }).detail
    throw new Error(typeof detail === 'string' ? detail : `请求失败 (${response.status})`)
  }
  return data as T
}

export default function AuthPage({ onSignedIn }: { onSignedIn: (session: Session) => void }) {
  const [mode, setMode] = useState<Mode>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [company, setCompany] = useState('')
  const [code, setCode] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [remember, setRemember] = useState(true)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState('')
  const [notice, setNotice] = useState('')
  const [codeSent, setCodeSent] = useState(false)
  const [resendIn, setResendIn] = useState(0)
  const [serverReady, setServerReady] = useState<boolean | null>(null)
  const [emailTaken, setEmailTaken] = useState(false)

  const strength = useMemo(() => strengthOf(password), [password])

  useEffect(() => { setErrors({}); setNotice(''); setCode(''); setCodeSent(false) }, [mode])

  // 账号服务可用性：不可用时给出明确提示，而不是让用户填完表单才失败。
  useEffect(() => {
    let live = true
    fetch('/api/auth/status').then(r => r.json()).then(d => { if (live) setServerReady(!!d.enabled) }).catch(() => { if (live) setServerReady(false) })
    return () => { live = false }
  }, [])

  useEffect(() => {
    if (resendIn <= 0) return
    const timer = setTimeout(() => setResendIn(v => v - 1), 1000)
    return () => clearTimeout(timer)
  }, [resendIn])

  // 邮箱输入停顿后检查是否已注册，避免用户填完表单才被告知。
  useEffect(() => {
    const value = email.trim()
    setEmailTaken(false)
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value)) return
    let live = true
    const timer = setTimeout(() => {
      fetch('/api/auth/check-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: value }),
      }).then(r => r.json()).then(d => { if (live) setEmailTaken(!!d.registered) }).catch(() => {})
    }, 500)
    return () => { live = false; clearTimeout(timer) }
  }, [email])

  const validate = () => {
    const next: Record<string, string> = {}
    if (!email.trim()) next.email = '请填写邮箱'
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())) next.email = '邮箱格式不正确'
    if (!password) next.password = '请填写密码'
    else if (mode === 'register' && password.length < 8) next.password = '密码至少 8 位'
    if (mode === 'register') {
      if (!name.trim()) next.name = '请填写姓名'
      if (!company.trim()) next.company = '请填写公司名称'
      if (!code.trim()) next.code = '请输入邮箱验证码'
    }
    setErrors(next)
    return Object.keys(next).length === 0
  }

  const sendCode = useCallback(async () => {
    setNotice('')
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())) {
      setErrors(e => ({ ...e, email: '请先填写正确的邮箱地址' }))
      return
    }
    setBusy('code')
    try {
      await post('/api/auth/send-code', { email: email.trim(), purpose: 'register', name: name.trim() })
      setCodeSent(true)
      setResendIn(60)
      setNotice('验证码已发送，请查收邮件（有效期 10 分钟）。')
    } catch (e) {
      setNotice((e as Error).message)
    } finally { setBusy('') }
  }, [email, name])

  async function submit(event: React.FormEvent) {
    event.preventDefault()
    setNotice('')
    if (!validate()) return
    setBusy('submit')
    try {
      const result = mode === 'register'
        ? await post<{ token: string; user: { id: number; email: string; name: string; company: string } }>('/api/auth/register', {
            email: email.trim(), name: name.trim(), company: company.trim(), password, code: code.trim(),
          })
        : await post<{ token: string; user: { id: number; email: string; name: string; company: string } }>('/api/auth/login', {
            email: email.trim(), password,
          })
      const session: Session = { ...result.user, token: result.token }
      writeSession(session)
      onSignedIn(session)
    } catch (e) {
      setNotice((e as Error).message)
    } finally { setBusy('') }
  }

  const isRegister = mode === 'register'
  const strengthLabel = STRENGTH[Math.max(0, strength - 1)]
  return <div className="auth-shell">
    <aside className="auth-brand">
      <div className="auth-brand-inner">
        <div className="auth-logo"><span className="auth-logo-mark"><ReceiptText size={22}/></span><span><strong>票序</strong><small>INVOICE WORKSPACE</small></span></div>
        <h1>把每一张发票<br/>整理成可信赖的账</h1>
        <p>本地识别、人工复核、闭环归档。发票数据始终留在你的设备上。</p>
        <ul className="auth-points">
          <li><span><ShieldCheck size={17}/></span><div><strong>数据不出本机</strong><small>无需上传到第三方识别服务</small></div></li>
          <li><span><Sparkles size={17}/></span><div><strong>批量自动整理</strong><small>电子票据与照片一次识别</small></div></li>
          <li><span><BarChart3 size={17}/></span><div><strong>支出结构清晰</strong><small>分类、供应商、趋势一目了然</small></div></li>
        </ul>
      </div>
      <div className="auth-brand-foot"><span>© 2026 票序</span><span>安全 · 稳定 · 可追溯</span></div>
    </aside>

    <main className="auth-main">
      <div className="auth-card">
        <header className="auth-head">
          <span className="auth-eyebrow">{isRegister ? 'CREATE ACCOUNT' : 'WELCOME BACK'}</span>
          <h2>{isRegister ? '创建你的工作区账号' : '登录工作区'}</h2>
          <p>{isRegister ? '开始整理你的发票，只需一分钟。' : '继续你的发票整理工作。'}</p>
        </header>

        <div className="auth-switch" role="tablist">
          <button role="tab" aria-selected={!isRegister} className={!isRegister ? 'active' : ''} onClick={() => setMode('login')}>登录</button>
          <button role="tab" aria-selected={isRegister} className={isRegister ? 'active' : ''} onClick={() => setMode('register')}>注册</button>
          <i className={isRegister ? 'to-right' : ''}/>
        </div>

        {serverReady === false && <div className="auth-notice error"><Info size={16}/>账号服务暂不可用，请确认数据库与邮件配置后重试。</div>}

        <form className="auth-form" onSubmit={submit} noValidate>
          {isRegister && <>
            <label className="auth-field">
              <span>姓名</span>
              <div className={'auth-input' + (errors.name ? ' invalid' : '')}><User size={17}/><input aria-label="姓名" value={name} onChange={e => setName(e.target.value)} placeholder="你的姓名" autoComplete="name"/></div>
              {errors.name && <small className="auth-error">{errors.name}</small>}
            </label>
            <label className="auth-field">
              <span>公司名称</span>
              <div className={'auth-input' + (errors.company ? ' invalid' : '')}><Building2 size={17}/><input aria-label="公司名称" value={company} onChange={e => setCompany(e.target.value)} placeholder="公司或组织名称" autoComplete="organization"/></div>
              {errors.company && <small className="auth-error">{errors.company}</small>}
            </label>
          </>}
          <label className="auth-field">
            <span>邮箱</span>
            <div className={'auth-input' + (errors.email ? ' invalid' : '')}><Mail size={17}/><input aria-label="邮箱" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="name@company.com" autoComplete="email"/></div>
            {errors.email && <small className="auth-error">{errors.email}</small>}
            {isRegister && emailTaken && !errors.email && <small className="auth-hint">该邮箱已注册。<button type="button" className="auth-link" onClick={() => { setMode('login'); setNotice('该邮箱已注册，请直接登录。') }}>前往登录</button></small>}
          </label>
          <label className="auth-field">
            <span>密码</span>
            <div className={'auth-input' + (errors.password ? ' invalid' : '')}><Lock size={17}/><input aria-label="密码" type={showPassword ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)} placeholder={isRegister ? '至少 8 位' : '输入密码'} autoComplete={isRegister ? 'new-password' : 'current-password'}/><button type="button" className="auth-eye" aria-label={showPassword ? '隐藏口令' : '显示口令'} onClick={() => setShowPassword(!showPassword)}>{showPassword ? <EyeOff size={17}/> : <Eye size={17}/>}</button></div>
            {errors.password ? <small className="auth-error">{errors.password}</small> : isRegister && password && <div className="auth-strength"><div>{[0, 1, 2, 3].map(i => <i key={i} className={strength > i ? 'on' : ''} style={strength > i ? { background: strengthLabel.color } : undefined}/>)}</div><small style={{ color: strengthLabel.color }}>{strengthLabel.label}</small></div>}
          </label>

          {isRegister && <label className="auth-field">
            <span>邮箱验证码</span>
            <div className={'auth-input code-input' + (errors.code ? ' invalid' : '')}><ShieldCheck size={17}/><input aria-label="验证码" inputMode="numeric" maxLength={6} value={code} onChange={e => setCode(e.target.value.replace(/\D/g,''))} placeholder="6 位数字"/>
              <button type="button" className="auth-code-btn" disabled={busy === 'code' || resendIn > 0 || emailTaken} onClick={sendCode}>
                {busy === 'code' ? <LoaderCircle size={14} className="spin"/> : resendIn > 0 ? <>{resendIn}s</> : <><RefreshCw size={14}/>{codeSent ? '重新发送' : '获取验证码'}</>}
              </button>
            </div>
            {errors.code && <small className="auth-error">{errors.code}</small>}
          </label>}

          {!isRegister && <div className="auth-row"><label className="auth-check"><input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)}/><i><Check size={13}/></i>记住我</label><button type="button" className="auth-link" onClick={() => setNotice('请联系你的系统管理员重置密码。')}>忘记密码？</button></div>}

          {notice && <div className={'auth-notice' + (/失败|错误|不可用|不正确|过期|频繁/.test(notice) ? ' error' : '')}>{notice}</div>}

          <button type="submit" className="auth-submit" disabled={busy === 'submit' || serverReady === false}>
            {busy === 'submit' ? <span className="auth-spinner"/> : <>{isRegister ? '创建账号' : '登录'}<ArrowRight size={18}/></>}
          </button>
        </form>

        <footer className="auth-foot">
          {isRegister ? '已有账号？' : '还没有账号？'}
          <button onClick={() => setMode(isRegister ? 'login' : 'register')}>{isRegister ? '返回登录' : '免费注册'}</button>
        </footer>
      </div>
      <p className="auth-legal">登录即表示同意《服务条款》与《隐私政策》。发票数据存储在本机，不会上传。</p>
    </main>
  </div>
}
