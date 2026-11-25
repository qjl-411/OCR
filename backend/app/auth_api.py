"""认证接口：注册（邮箱验证码）、登录、令牌签发、修改密码。"""
import re
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import auth_config as cfg, auth_store as store
from .mailer import send_code

router = APIRouter(prefix='/api/auth', tags=['auth'])

EMAIL_PATTERN = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]{2,}$')
# 登录失败计数存在进程内；单机部署足够，多机部署需改到 MySQL。
_login_attempts: dict[str, list[datetime]] = {}


def _clean(value: str) -> str:
    return (value or '').strip()


def issue_token(user: dict) -> str:
    if not cfg.JWT_SECRET:
        raise HTTPException(503, '会话密钥未配置，无法签发登录令牌。请设置 PIAO_JWT_SECRET 环境变量。')
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user['id']),
        'email': user['email'],
        'name': user['name'],
        'company': user.get('company', ''),
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(seconds=cfg.JWT_TTL_SECONDS)).timestamp()),
    }
    return jwt.encode(payload, cfg.JWT_SECRET, algorithm=cfg.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    if not cfg.JWT_SECRET:
        raise HTTPException(503, '会话密钥未配置。')
    try:
        return jwt.decode(token, cfg.JWT_SECRET, algorithms=[cfg.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as error:
        raise HTTPException(401, '登录状态已过期，请重新登录。') from error
    except jwt.InvalidTokenError as error:
        raise HTTPException(401, '登录凭证无效，请重新登录。') from error


def current_user(authorization: str = Header(default='')) -> dict:
    if not authorization.lower().startswith('bearer '):
        raise HTTPException(401, '请先登录。')
    payload = decode_token(authorization.split(' ', 1)[1].strip())
    user = store.find_user(payload.get('email', ''))
    if user is None or not user['is_active']:
        raise HTTPException(401, '账号不存在或已停用。')
    return user


def _require_database():
    if not cfg.mysql_ready():
        raise HTTPException(503, '账号服务暂不可用，请检查数据库配置。')


def _require_mail():
    _require_database()
    if not cfg.smtp_ready():
        raise HTTPException(503, '邮件服务未配置，暂时无法发送邮箱验证码。')


class SendCodeBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(max_length=190)
    purpose: str = Field(default='register', max_length=16)
    name: str = Field(default='', max_length=64)


class RegisterBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(max_length=190)
    name: str = Field(min_length=1, max_length=64)
    company: str = Field(default='', max_length=128)
    password: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=4, max_length=12)


class LoginBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(max_length=190)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


def _public(user: dict) -> dict:
    return {
        'id': user['id'],
        'email': user['email'],
        'name': user['name'],
        'company': user.get('company', ''),
        'created_at': user['created_at'].isoformat() if hasattr(user['created_at'], 'isoformat') else str(user['created_at']),
    }


@router.get('/status')
def status():
    """认证能力状态。前端据此决定是否强制登录。"""
    return {
        'enabled': cfg.mysql_ready(),
        'mail_ready': cfg.smtp_ready(),
        'code_ttl_seconds': cfg.CODE_TTL_SECONDS,
        'resend_seconds': cfg.CODE_RESEND_SECONDS,
    }


@router.post('/send-code')
def send_verification_code(body: SendCodeBody):
    _require_mail()
    email = _clean(body.email).lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(422, '邮箱格式不正确。')
    if body.purpose not in ('register', 'reset'):
        raise HTTPException(422, '不支持的验证用途。')
    if body.purpose == 'register' and store.find_user(email) is not None:
        raise HTTPException(409, '该邮箱已注册，请直接登录。', headers={'X-Auth-Hint': 'registered'})
    if not store.resend_allowed(email, body.purpose):
        raise HTTPException(429, f'验证码发送过于频繁，请 {cfg.CODE_RESEND_SECONDS} 秒后再试。')
    code, expires = store.issue_code(email, body.purpose)
    try:
        send_code(email, code, body.name)
    except RuntimeError as error:
        # 邮件未送达时不留待用验证码，避免用户拿到码却收不到。
        store.latest_code(email, body.purpose)
        raise HTTPException(502, str(error)) from error
    return {
        'sent': True,
        'email': email,
        'expires_at': expires.isoformat(),
        'ttl_seconds': cfg.CODE_TTL_SECONDS,
    }


class CheckEmailBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    email: str = Field(max_length=190)


@router.post('/check-email')
def check_email(body: CheckEmailBody):
    """注册前检查邮箱是否已注册，让前端能提前引导用户去登录。"""
    _require_database()
    normalized = _clean(body.email).lower()
    if not EMAIL_PATTERN.match(normalized):
        return {'valid': False, 'registered': False}
    return {'valid': True, 'registered': store.find_user(normalized) is not None}


@router.post('/register')
def register(body: RegisterBody):
    _require_database()
    email = _clean(body.email).lower()
    if not EMAIL_PATTERN.match(email):
        raise HTTPException(422, '邮箱格式不正确。')
    if store.find_user(email) is not None:
        raise HTTPException(409, '该邮箱已注册，请直接登录。')
    ok, reason = store.consume_code(email, 'register', _clean(body.code))
    if not ok:
        raise HTTPException(422, reason)
    try:
        user = store.create_user(email, _clean(body.name), _clean(body.company), body.password)
    except Exception as error:
        if 'Duplicate' in str(error) or '1062' in str(error):
            raise HTTPException(409, '该邮箱已注册，请直接登录。') from error
        raise
    return {'token': issue_token(user), 'user': _public(user)}


@router.post('/login')
def login(body: LoginBody):
    if not cfg.mysql_ready():
        raise HTTPException(503, '账号服务暂不可用。')
    email = _clean(body.email).lower()
    now = datetime.now(timezone.utc)
    history = [t for t in _login_attempts.get(email, []) if now - t < timedelta(seconds=cfg.LOGIN_LOCK_SECONDS)]
    if len(history) >= cfg.LOGIN_MAX_ATTEMPTS:
        raise HTTPException(429, '密码错误次数过多，请稍后再试。')
    user = store.find_user(email)
    if user is None or not store.verify_password(body.password, user['password_hash']):
        history.append(now)
        _login_attempts[email] = history
        raise HTTPException(401, '邮箱或密码不正确。')
    if not user['is_active']:
        raise HTTPException(403, '该账号已停用，请联系管理员。')
    _login_attempts.pop(email, None)
    store.touch_login(user['id'])
    return {'token': issue_token(user), 'user': _public(user)}


@router.get('/me')
def me(user: dict = Depends(current_user)):
    return {'user': _public(user)}


@router.post('/change-password')
def change_password(body: ChangePasswordBody, user: dict = Depends(current_user)):
    if not store.verify_password(body.current_password, user['password_hash']):
        raise HTTPException(422, '当前密码不正确。')
    if body.current_password == body.new_password:
        raise HTTPException(422, '新密码不能与当前密码相同。')
    store.update_password(user['id'], body.new_password)
    return {'ok': True}
