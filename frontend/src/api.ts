function authToken(): string {
  try { return localStorage.getItem('piao-studio.token') || '' } catch { return '' }
}

export async function api<T>(url: string, options?: RequestInit): Promise<T> {
  const headers = new Headers(options?.headers)
  const token = authToken()
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch(url, { ...options, headers })
  if (response.status === 401) {
    // Token 失效：清除本地会话，交由上层跳回登录页。
    try {
      localStorage.removeItem('piao-studio.session')
      localStorage.removeItem('piao-studio.token')
    } catch { /* storage unavailable */ }
  }
  if (!response.ok) {
    const result = await response.json().catch(() => ({}))
    let message = result.detail
    if (Array.isArray(message)) message = message.map((e: {msg: string}) => e.msg).join('；')
    if (typeof message === 'object') message = [message.message, ...(message.errors || []).map((e: {message: string}) => e.message)].join('；')
    throw new Error(message || `请求失败 (${response.status})`)
  }
  return response.json()
}
export const jsonBody = (body: unknown) => ({ headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
export const yuan = (v: string | number | null | undefined) => Number(v || 0).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
export const dateTime = (v: string) => new Date(v).toLocaleString('zh-CN', { hour12: false })
export async function downloadExport(params: Record<string,string>) {
  const headers = new Headers()
  const token = authToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const response = await fetch('/api/export?' + new URLSearchParams(params), { headers })
  if (!response.ok) { const err = await response.json(); throw new Error(err.detail || '导出失败') }
  const blob = await response.blob(); const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = `票序发票台账-${new Date().toISOString().slice(0,10)}.${params.format || 'xlsx'}`
  a.click(); setTimeout(() => URL.revokeObjectURL(url), 2000)
}
