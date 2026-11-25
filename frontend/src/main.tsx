import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'
import './theme.css'
import './auth.css'

class ErrorBoundary extends React.Component<{ children: React.ReactNode },{ error: string }> {
  state = { error: '' }
  static getDerivedStateFromError(error: Error) { return { error: error.message } }
  render() { return this.state.error ? <main className="fatal"><h1>页面暂时无法显示</h1><p>请刷新重试。数据已保存在本机。</p><button className="btn primary" onClick={() => location.reload()}>刷新页面</button><details><summary>错误详情</summary>{this.state.error}</details></main> : this.props.children }
}
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>)
