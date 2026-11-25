"""真实 SMTP 发信。发送失败抛出可读异常，由接口层转成用户提示。"""
import smtplib
import ssl
from email.header import Header
from email.message import EmailMessage
from email.utils import formataddr, formatdate

from . import auth_config as cfg

TEMPLATE = """\
<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<style>
  body{margin:0;padding:32px;background:#f4f6f8;font-family:-apple-system,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}
  .card{max-width:520px;margin:0 auto;background:#fff;border-radius:16px;overflow:hidden;border:1px solid #e5e9ee}
  .head{background:linear-gradient(135deg,#123a2d,#1a4d3c);padding:28px 32px;color:#fff}
  .head h1{margin:0;font-size:20px;font-weight:600;letter-spacing:.4px}
  .head p{margin:8px 0 0;font-size:13.5px;color:rgba(255,255,255,.72)}
  .body{padding:32px}
  .code{margin:26px 0;text-align:center;font-size:38px;font-weight:600;letter-spacing:12px;color:#123a2d;background:#f1f7f4;border:1px dashed #c2dbcd;border-radius:12px;padding:20px 12px}
  .tip{font-size:13px;color:#74838d;line-height:1.9;margin:0}
  .foot{padding:16px 32px;background:#fafbfc;border-top:1px solid #eef1f4;font-size:12px;color:#9aa5ae;line-height:1.8}
</style></head><body>
<div class="card">
  <div class="head"><h1>邮箱验证码</h1><p>票序 智能发票工作台 · 账号注册</p></div>
  <div class="body">
    <p class="tip">你好，<strong>@@NAME@@</strong>：</p>
    <p class="tip">你正在注册票序智能发票工作台账号，请使用下方验证码完成验证。</p>
    <div class="code">@@CODE@@</div>
    <p class="tip">验证码 <strong>@@MINUTES@@ 分钟</strong>内有效，仅可使用一次。<br>
    如果这不是你本人的操作，请忽略此邮件，账号不会被创建。</p>
  </div>
  <div class="foot">本邮件由系统自动发送，请勿直接回复。<br>票序 · 发票数据保存在本机，不上传第三方识别服务。</div>
</div>
</body></html>
"""


def _validate_settings() -> None:
    if not cfg.smtp_ready():
        raise RuntimeError('邮件服务尚未配置，请联系管理员设置 SMTP 授权码。')
    if not cfg.SMTP_USER.isascii():
        raise RuntimeError('发件邮箱地址格式不正确，请填写真实的邮箱地址（如 12345678@qq.com）。')


def send_code(email: str, code: str, name: str = '') -> None:
    """向 email 真实发送验证码邮件。失败时抛出 RuntimeError。"""
    _validate_settings()
    minutes = max(1, cfg.CODE_TTL_SECONDS // 60)
    message = EmailMessage()
    message['Subject'] = f'【票序】您的注册验证码是 {code}'
    message['From'] = formataddr((str(Header(cfg.SMTP_FROM_NAME, 'utf-8')), cfg.SMTP_USER))
    message['To'] = email
    message['Date'] = formatdate(localtime=True)
    message.set_content(f'你的注册验证码是 {code}，{minutes} 分钟内有效。\n\n票序 智能发票工作台')
    # 模板用 @@占位符@@ 替换：CSS 里的花括号不会被误当作占位符。
    html = (TEMPLATE
            .replace('@@NAME@@', name or '你好')
            .replace('@@CODE@@', code)
            .replace('@@MINUTES@@', str(minutes)))
    message.add_alternative(html, subtype='html')

    try:
        if cfg.SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT, context=context, timeout=cfg.SMTP_TIMEOUT) as server:
                server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
                server.send_message(message)
        else:
            with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=cfg.SMTP_TIMEOUT) as server:
                server.ehlo()
                if server.has_extn('STARTTLS'):
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
                server.send_message(message)
    except smtplib.SMTPAuthenticationError as error:
        raise RuntimeError('邮件服务认证失败：邮箱地址或授权码不正确。') from error
    except smtplib.SMTPException as error:
        raise RuntimeError(f'邮件发送失败：{error}') from error
    except OSError as error:
        raise RuntimeError(f'无法连接邮件服务器 {cfg.SMTP_HOST}:{cfg.SMTP_PORT}：{error}') from error


def verify_smtp() -> tuple[bool, str]:
    """连通性自检，用于设置页展示。"""
    if not cfg.smtp_ready():
        return False, '未配置 SMTP 账号'
    if not cfg.SMTP_USER.isascii():
        return False, '发件邮箱地址格式不正确，请填写真实邮箱地址'
    try:
        if cfg.SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg.SMTP_HOST, cfg.SMTP_PORT, context=context, timeout=cfg.SMTP_TIMEOUT) as server:
                server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
        else:
            with smtplib.SMTP(cfg.SMTP_HOST, cfg.SMTP_PORT, timeout=cfg.SMTP_TIMEOUT) as server:
                server.ehlo()
                if server.has_extn('STARTTLS'):
                    server.starttls(context=ssl.create_default_context())
                    server.ehlo()
                server.login(cfg.SMTP_USER, cfg.SMTP_PASSWORD)
        return True, f'{cfg.SMTP_HOST}:{cfg.SMTP_PORT} 连接正常'
    except Exception as error:
        return False, str(error)
