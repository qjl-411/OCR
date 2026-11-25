"""账号与邮件配置。敏感值只从环境变量读取，不写入代码或数据库。"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_env_file():
    """回退读取项目根目录 .env，使 pytest 等未走 start.py 的入口也能取到配置。"""
    env_file = ROOT / '.env'
    if not env_file.is_file():
        return
    try:
        for raw in env_file.read_text(encoding='utf-8').splitlines():
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        pass


_load_env_file()


def _flag(name: str, default: str = '') -> str:
    return (os.getenv(name) or default).strip()


# ---- MySQL 账号库 ----
MYSQL_HOST = _flag('PIAO_MYSQL_HOST', '127.0.0.1')
MYSQL_PORT = int(_flag('PIAO_MYSQL_PORT', '3306') or 3306)
MYSQL_USER = _flag('PIAO_MYSQL_USER', 'root')
MYSQL_PASSWORD = os.getenv('PIAO_MYSQL_PASSWORD', '')
MYSQL_DATABASE = _flag('PIAO_MYSQL_DATABASE', 'piao_invoice')

# ---- 会话令牌 ----
JWT_SECRET = os.getenv('PIAO_JWT_SECRET', '')
JWT_ALGORITHM = 'HS256'
JWT_TTL_SECONDS = int(_flag('PIAO_JWT_TTL', str(60 * 60 * 12)) or 43200)

# ---- 邮件（SMTP）----
SMTP_HOST = _flag('PIAO_SMTP_HOST', 'smtp.qq.com')
SMTP_PORT = int(_flag('PIAO_SMTP_PORT', '465') or 465)
SMTP_USER = _flag('PIAO_SMTP_USER')
SMTP_PASSWORD = os.getenv('PIAO_SMTP_PASSWORD', '')
SMTP_USE_SSL = _flag('PIAO_SMTP_SSL', '1') not in ('0', 'false', 'False')
SMTP_FROM_NAME = _flag('PIAO_SMTP_FROM_NAME', '票序 智能发票工作台')
SMTP_TIMEOUT = int(_flag('PIAO_SMTP_TIMEOUT', '20') or 20)

# ---- 注册策略 ----
CODE_TTL_SECONDS = int(_flag('PIAO_CODE_TTL', '600') or 600)
CODE_RESEND_SECONDS = int(_flag('PIAO_CODE_RESEND', '60') or 60)
CODE_MAX_ATTEMPTS = int(_flag('PIAO_CODE_MAX_ATTEMPTS', '5') or 5)
LOGIN_MAX_ATTEMPTS = int(_flag('PIAO_LOGIN_MAX_ATTEMPTS', '5') or 5)
LOGIN_LOCK_SECONDS = int(_flag('PIAO_LOGIN_LOCK', '900') or 900)


def mysql_ready() -> bool:
    """账号库是否可用。不可用时应用仍可运行，只是不提供注册登录。"""
    if not MYSQL_PASSWORD:
        return False
    try:
        import pymysql
        with pymysql.connect(
            host=MYSQL_HOST, port=MYSQL_PORT, user=MYSQL_USER,
            password=MYSQL_PASSWORD, database=MYSQL_DATABASE, connect_timeout=5,
        ):
            return True
    except Exception:
        return False


def smtp_ready() -> bool:
    return bool(SMTP_USER and SMTP_PASSWORD)
