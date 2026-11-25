"""邮件模板与发送逻辑测试。

不依赖外部 SMTP：用本地假 SMTP 服务器接收邮件内容，
验证主题、收件人、HTML 正文与验证码是否正确渲染。
"""
import email
from email.message import EmailMessage

import pytest

from backend.app import auth_config as cfg, mailer


def test_template_keeps_css_braces_intact():
    """回归：曾用 str.format 渲染模板，导致 CSS 大括号被当成占位符而崩溃。"""
    html = (mailer.TEMPLATE
            .replace('@@NAME@@', '张三')
            .replace('@@CODE@@', '123456')
            .replace('@@MINUTES@@', '10'))
    assert '@@' not in html
    assert '123456' in html
    assert '张三' in html
    assert 'margin:0' in html            # CSS 花括号必须原样保留
    assert 'padding:32px' in html
    assert html.count('{') == html.count('}')


def test_template_placeholders_are_replaced():
    html = mailer.TEMPLATE.replace('@@CODE@@', '654321')
    assert '@@CODE@@' not in html
    assert '654321' in html


def test_send_code_rejects_invalid_settings(monkeypatch):
    monkeypatch.setattr(cfg, 'SMTP_USER', '中文占位符')
    monkeypatch.setattr(cfg, 'SMTP_PASSWORD', 'x')
    with pytest.raises(RuntimeError) as error:
        mailer.send_code('a@example.com', '123456')
    assert '邮箱地址' in str(error.value)


def test_send_code_requires_smtp_config(monkeypatch):
    monkeypatch.setattr(cfg, 'SMTP_USER', '')
    monkeypatch.setattr(cfg, 'SMTP_PASSWORD', '')
    with pytest.raises(RuntimeError) as error:
        mailer.send_code('a@example.com', '123456')
    assert '尚未配置' in str(error.value)


def test_send_code_produces_correct_email(monkeypatch):
    """替换 SMTP 传输层，验证真实生成的邮件内容。"""
    sent: list[EmailMessage] = []

    class RecordingSMTP:
        def __init__(self, host, port, timeout=None, **kwargs):
            self.host, self.port = host, port

        def __enter__(self): return self
        def __exit__(self, *exc): return False
        def ehlo(self): pass
        def has_extn(self, name): return False
        def starttls(self, **kwargs): pass
        def login(self, user, password): self.credentials = (user, password)
        def send_message(self, message): sent.append(message)

    monkeypatch.setattr(cfg, 'SMTP_HOST', 'smtp.example.com')
    monkeypatch.setattr(cfg, 'SMTP_PORT', 465)
    monkeypatch.setattr(cfg, 'SMTP_USE_SSL', False)
    monkeypatch.setattr(cfg, 'SMTP_USER', 'sender@example.com')
    monkeypatch.setattr(cfg, 'SMTP_PASSWORD', 'secret')
    monkeypatch.setattr(mailer.smtplib, 'SMTP', RecordingSMTP)

    mailer.send_code('target@example.com', '246810', '李四')

    assert sent, '未产生邮件'
    message = sent[0]
    assert message['To'] == 'target@example.com'
    assert 'sender@example.com' in message['From']
    assert '246810' in message['Subject']
    parts = {part.get_content_type(): part.get_payload(decode=True).decode('utf-8') for part in message.walk() if not part.is_multipart()}
    assert 'text/plain' in parts and 'text/html' in parts
    html = parts['text/html']
    assert '246810' in html
    assert '李四' in html
    assert 'margin:0' in html          # CSS 花括号必须原样保留
    text = parts['text/plain']
    assert '246810' in text
