// Authentication flow tests: the workspace must stay locked until a real
// sign-in, and the client must talk to the backend rather than decide locally.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import AuthPage, { readSession, writeSession } from './AuthPage'

const jsonResponse = (value: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(value), { status, headers: { 'Content-Type': 'application/json' } }))

beforeEach(() => { localStorage.clear() })
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear() })

describe('登录与注册', () => {
  it('未登录时呈现登录表单，登录成功后写入会话', async () => {
    const onSignedIn = vi.fn()
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === '/api/auth/status') return jsonResponse({ enabled: true, mail_ready: true })
      if (url === '/api/auth/login') return jsonResponse({ token: 'tok-123', user: { id: 7, email: 'finance@company.com', name: '财务', company: '某公司' } })
      return jsonResponse({}, 404)
    }))
    render(<AuthPage onSignedIn={onSignedIn} />)
    await screen.findByRole('heading', { name: '登录工作区' })
    await userEvent.type(screen.getByLabelText('邮箱'), 'finance@company.com')
    await userEvent.type(screen.getByLabelText('密码'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: /^登录$/ }))
    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1))
    expect(onSignedIn.mock.calls[0][0]).toMatchObject({ email: 'finance@company.com', token: 'tok-123' })
    expect(readSession()?.token).toBe('tok-123')
  })

  it('登录失败时展示后端返回的错误信息', async () => {
    const onSignedIn = vi.fn()
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === '/api/auth/status') return jsonResponse({ enabled: true })
      if (url === '/api/auth/login') return jsonResponse({ detail: '邮箱或密码不正确。' }, 401)
      return jsonResponse({}, 404)
    }))
    render(<AuthPage onSignedIn={onSignedIn} />)
    await screen.findByRole('heading', { name: '登录工作区' })
    await userEvent.type(screen.getByLabelText('邮箱'), 'finance@company.com')
    await userEvent.type(screen.getByLabelText('密码'), 'wrongpass')
    await userEvent.click(screen.getByRole('button', { name: /^登录$/ }))
    await waitFor(() => expect(screen.getByText('邮箱或密码不正确。')).toBeTruthy())
    expect(onSignedIn).not.toHaveBeenCalled()
  })

  it('注册必须先获取并填写邮箱验证码', async () => {
    const onSignedIn = vi.fn()
    const calls: string[] = []
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      calls.push(url)
      if (url === '/api/auth/status') return jsonResponse({ enabled: true, mail_ready: true })
      if (url === '/api/auth/send-code') return jsonResponse({ sent: true, email: 'user@company.com' })
      if (url === '/api/auth/register') return jsonResponse({ token: 'tok-456', user: { id: 9, email: 'user@company.com', name: '张三', company: '某科技' } })
      return jsonResponse({}, 404)
    }))
    render(<AuthPage onSignedIn={onSignedIn} />)
    await screen.findByRole('heading', { name: '登录工作区' })
    await userEvent.click(screen.getByRole('tab', { name: '注册' }))
    await userEvent.type(screen.getByLabelText('姓名'), '张三')
    await userEvent.type(screen.getByLabelText('公司名称'), '某科技')
    await userEvent.type(screen.getByLabelText('邮箱'), 'user@company.com')
    await userEvent.type(screen.getByLabelText('密码'), 'Invoice@2026')
    // 提交前必须填写验证码
    await userEvent.click(screen.getByRole('button', { name: '创建账号' }))
    await waitFor(() => expect(screen.getByText('请输入邮箱验证码')).toBeTruthy())
    expect(calls).not.toContain('/api/auth/register')
    // 获取验证码
    await userEvent.click(screen.getByRole('button', { name: '获取验证码' }))
    await waitFor(() => expect(calls).toContain('/api/auth/send-code'))
    await userEvent.type(screen.getByLabelText('验证码'), '123456')
    await userEvent.click(screen.getByRole('button', { name: '创建账号' }))
    await waitFor(() => expect(onSignedIn).toHaveBeenCalledTimes(1))
    expect(onSignedIn.mock.calls[0][0]).toMatchObject({ email: 'user@company.com', token: 'tok-456' })
  })

  it('账号服务不可用时禁用提交并给出提示', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => {
      if (url === '/api/auth/status') return jsonResponse({ enabled: false })
      return jsonResponse({}, 404)
    }))
    render(<AuthPage onSignedIn={vi.fn()} />)
    await waitFor(() => expect(screen.getByText(/账号服务暂不可用/)).toBeTruthy())
    expect(screen.getByRole('button', { name: /^登录$/ }).hasAttribute('disabled')).toBe(true)
  })

  it('会话写入本地存储并可读取，退出后清除', () => {
    expect(readSession()).toBeNull()
    writeSession({ id: 1, email: 'li@company.com', name: '李四', company: '某公司', token: 'tok' })
    expect(readSession()?.email).toBe('li@company.com')
    writeSession(null)
    expect(readSession()).toBeNull()
  })
})
