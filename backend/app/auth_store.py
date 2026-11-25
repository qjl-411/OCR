"""账号与验证码的数据访问层。密码与验证码只以哈希形式落库。"""
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta

import bcrypt
import pymysql

from . import auth_config as cfg


@contextmanager
def connection():
    con = pymysql.connect(
        host=cfg.MYSQL_HOST, port=cfg.MYSQL_PORT, user=cfg.MYSQL_USER,
        password=cfg.MYSQL_PASSWORD, database=cfg.MYSQL_DATABASE,
        charset='utf8mb4', autocommit=False, connect_timeout=10,
        cursorclass=pymysql.cursors.DictCursor,
    )
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ---- 口令哈希 ----
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('ascii')


def verify_password(password: str, stored: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode('utf-8'), stored.encode('ascii'))
    except (ValueError, TypeError):
        return False


# ---- 验证码哈希 ----
def _pepper() -> bytes:
    """验证码哈希混入服务端密钥，避免离线爆破纯数字码。"""
    return (cfg.JWT_SECRET or 'piao-local-dev').encode('utf-8')


def hash_code(email: str, code: str) -> str:
    message = f'{email.lower()}:{code}'.encode('utf-8')
    return hmac.new(_pepper(), message, hashlib.sha256).hexdigest()


def new_code() -> str:
    return f'{secrets.randbelow(1000000):06d}'


# ---- 用户 ----
def find_user(email: str):
    with connection() as con:
        with con.cursor() as cur:
            cur.execute('SELECT * FROM users WHERE email=%s LIMIT 1', (email.strip().lower(),))
            return cur.fetchone()


def create_user(email: str, name: str, company: str, password: str):
    with connection() as con:
        with con.cursor() as cur:
            cur.execute(
                'INSERT INTO users(email,name,company,password_hash) VALUES(%s,%s,%s,%s)',
                (email.strip().lower(), name.strip(), company.strip(), hash_password(password)),
            )
            cur.execute('SELECT * FROM users WHERE id=%s', (cur.lastrowid,))
            return cur.fetchone()


def touch_login(user_id: int):
    with connection() as con:
        with con.cursor() as cur:
            cur.execute('UPDATE users SET last_login_at=NOW() WHERE id=%s', (user_id,))


def update_password(user_id: int, password: str):
    with connection() as con:
        with con.cursor() as cur:
            cur.execute('UPDATE users SET password_hash=%s WHERE id=%s', (hash_password(password), user_id))


# ---- 验证码 ----
def issue_code(email: str, purpose: str = 'register'):
    """生成验证码并落库；同一邮箱的旧验证码立即作废。"""
    code = new_code()
    expires = datetime.now() + timedelta(seconds=cfg.CODE_TTL_SECONDS)
    with connection() as con:
        with con.cursor() as cur:
            cur.execute(
                'UPDATE email_codes SET consumed_at=NOW() WHERE email=%s AND purpose=%s AND consumed_at IS NULL',
                (email.strip().lower(), purpose),
            )
            cur.execute(
                'INSERT INTO email_codes(email,code_hash,purpose,expires_at) VALUES(%s,%s,%s,%s)',
                (email.strip().lower(), hash_code(email, code), purpose, expires),
            )
    return code, expires


def latest_code(email: str, purpose: str = 'register'):
    with connection() as con:
        with con.cursor() as cur:
            cur.execute(
                'SELECT * FROM email_codes WHERE email=%s AND purpose=%s AND consumed_at IS NULL '
                'ORDER BY id DESC LIMIT 1',
                (email.strip().lower(), purpose),
            )
            return cur.fetchone()


def consume_code(email: str, purpose: str, code: str) -> tuple[bool, str]:
    """校验并消费验证码。返回 (是否通过, 失败原因)。"""
    row = latest_code(email, purpose)
    if row is None:
        return False, '验证码不存在或已被使用，请重新获取。'
    if row['attempts'] >= cfg.CODE_MAX_ATTEMPTS:
        return False, '验证码错误次数过多，请重新获取。'
    if row['expires_at'] < datetime.now():
        return False, '验证码已过期，请重新获取。'
    if not hmac.compare_digest(row['code_hash'], hash_code(email, code)):
        with connection() as con:
            with con.cursor() as cur:
                cur.execute('UPDATE email_codes SET attempts=attempts+1 WHERE id=%s', (row['id'],))
        return False, '验证码不正确。'
    with connection() as con:
        with con.cursor() as cur:
            cur.execute('UPDATE email_codes SET consumed_at=NOW() WHERE id=%s', (row['id'],))
    return True, ''


def resend_allowed(email: str, purpose: str = 'register') -> bool:
    row = latest_code(email, purpose)
    if row is None:
        return True
    created = row['created_at']
    if isinstance(created, str):
        created = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
    return (datetime.now() - created).total_seconds() >= cfg.CODE_RESEND_SECONDS


def purge_expired_codes():
    with connection() as con:
        with con.cursor() as cur:
            cur.execute('DELETE FROM email_codes WHERE expires_at < NOW() - INTERVAL 1 DAY')
