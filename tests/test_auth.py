"""认证接口测试。连接真实 MySQL，使用独立测试库，绝不触碰正式账号库。

配置在调用时才读取（cfg.X 属性访问），因此直接 monkeypatch 配置模块即可，
无需重载模块——这样测试更稳定，也避免影响其他用例。
"""
import os
import uuid

import pytest

# 密码只从环境变量或项目 .env 读取，绝不写死默认值（避免凭据进入版本库）。
# auth_config 在导入时加载 .env，因此这里通过它取值。
from backend.app import auth_config as _auth_config  # noqa: E402

MYSQL_PASSWORD = _auth_config.MYSQL_PASSWORD
TEST_DB = 'piao_invoice_test'


def _admin():
    import pymysql
    return pymysql.connect(host='127.0.0.1', port=3306, user='root', password=MYSQL_PASSWORD, autocommit=True)


@pytest.fixture(scope='module')
def mysql_available():
    if not MYSQL_PASSWORD:
        pytest.skip('未配置 PIAO_MYSQL_PASSWORD，跳过认证测试')
    try:
        con = _admin()
        con.close()
        return True
    except Exception:
        return False


@pytest.fixture(scope='module')
def client(mysql_available):
    if not mysql_available:
        pytest.skip('MySQL 不可用，跳过认证测试')
    from backend.app import auth_config, auth_store

    con = _admin()
    with con.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS {TEST_DB}')
        cur.execute(f'CREATE DATABASE {TEST_DB} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    con.close()

    # 用正式库已建好的表结构复制到测试库，保证两边结构一致。
    source = _admin()
    with source.cursor() as cur:
        cur.execute('SHOW CREATE TABLE piao_invoice.users')
        users_ddl = cur.fetchone()[1]
        cur.execute('SHOW CREATE TABLE piao_invoice.email_codes')
        codes_ddl = cur.fetchone()[1]
    source.close()

    con = _admin()
    with con.cursor() as cur:
        cur.execute(f'USE {TEST_DB}')
        cur.execute(users_ddl)
        cur.execute(codes_ddl)
    con.close()

    # 指向测试库：两个模块共享同一 config 对象，改属性即生效。
    original = (auth_config.MYSQL_DATABASE, auth_config.JWT_SECRET)
    auth_config.MYSQL_DATABASE = TEST_DB
    auth_config.JWT_SECRET = 'test-secret-for-auth-suite'

    from fastapi.testclient import TestClient
    from backend.app.main import app
    with TestClient(app) as c:
        yield c

    auth_config.MYSQL_DATABASE, auth_config.JWT_SECRET = original
    con = _admin()
    with con.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS {TEST_DB}')
    con.close()


@pytest.fixture
def sent_codes(monkeypatch):
    """拦截真实发信，记录验证码，测试不依赖外部 SMTP。"""
    from backend.app import auth_api
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(auth_api, 'send_code', lambda email, code, name='': captured.append((email, code)))
    return captured


def _register(client, sent_codes, password='Invoice@2026'):
    email = f'{uuid.uuid4().hex[:10]}@example.com'
    client.post('/api/auth/send-code', json={'email': email, 'purpose': 'register', 'name': '测试'})
    code = sent_codes[-1][1]
    response = client.post('/api/auth/register', json={
        'email': email, 'name': '测试用户', 'company': '测试公司',
        'password': password, 'code': code,
    })
    return email, code, response


def test_status_reports_service_state(client):
    response = client.get('/api/auth/status')
    assert response.status_code == 200
    body = response.json()
    assert body['enabled'] is True
    assert body['code_ttl_seconds'] > 0


def test_register_requires_valid_code(client, sent_codes):
    email = f'{uuid.uuid4().hex[:10]}@example.com'
    response = client.post('/api/auth/register', json={
        'email': email, 'name': '测试用户', 'company': '测试公司',
        'password': 'Invoice@2026', 'code': '000000',
    })
    assert response.status_code == 422
    assert '验证码' in response.json()['detail']


def test_full_register_login_flow(client, sent_codes):
    email, code, response = _register(client, sent_codes)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['user']['email'] == email
    assert payload['user']['name'] == '测试用户'
    token = payload['token']
    assert token

    me = client.get('/api/auth/me', headers={'Authorization': f'Bearer {token}'})
    assert me.status_code == 200 and me.json()['user']['email'] == email

    # 同一验证码不能重复使用
    again = client.post('/api/auth/register', json={
        'email': f'{uuid.uuid4().hex[:10]}@example.com', 'name': 'x', 'company': 'y',
        'password': 'Invoice@2026', 'code': code,
    })
    assert again.status_code == 422

    assert client.post('/api/auth/login', json={'email': email, 'password': 'Invoice@2026'}).status_code == 200
    assert client.post('/api/auth/login', json={'email': email, 'password': 'wrong-password'}).status_code == 401

    dup = client.post('/api/auth/register', json={
        'email': email, 'name': 'x', 'company': 'y', 'password': 'Invoice@2026', 'code': '123456',
    })
    assert dup.status_code == 409


def test_invalid_token_is_rejected(client):
    assert client.get('/api/auth/me', headers={'Authorization': 'Bearer not-a-real-token'}).status_code == 401


def test_me_requires_authorization(client):
    assert client.get('/api/auth/me').status_code == 401


def test_password_is_hashed_in_database(client, sent_codes):
    from backend.app import auth_store
    email, _, response = _register(client, sent_codes, password='PlainText@123')
    assert response.status_code == 200
    user = auth_store.find_user(email)
    assert user is not None
    assert user['password_hash'] != 'PlainText@123'
    assert user['password_hash'].startswith('$2b$')
    assert auth_store.verify_password('PlainText@123', user['password_hash'])


def test_code_is_not_stored_in_plaintext(client, sent_codes):
    from backend.app import auth_store
    email = f'{uuid.uuid4().hex[:10]}@example.com'
    client.post('/api/auth/send-code', json={'email': email, 'purpose': 'register'})
    code = sent_codes[-1][1]
    row = auth_store.latest_code(email, 'register')
    assert row is not None
    assert row['code_hash'] != code
    assert len(row['code_hash']) == 64


def test_check_email_reports_registered_state(client, sent_codes):
    """注册前检查：已注册邮箱必须被识别出来，前端才能提前引导去登录。"""
    email, _, response = _register(client, sent_codes)
    assert response.status_code == 200
    status, body = call_json(client, '/api/auth/check-email', {'email': email})
    assert status == 200 and body['registered'] is True
    assert body['valid'] is True

    fresh = f'{uuid.uuid4().hex[:10]}@example.com'
    status, body = call_json(client, '/api/auth/check-email', {'email': fresh})
    assert status == 200 and body['registered'] is False

    status, body = call_json(client, '/api/auth/check-email', {'email': 'not-an-email'})
    assert status == 200 and body['valid'] is False


def test_send_code_refuses_registered_email(client, sent_codes):
    """已注册邮箱发码应被拒绝，并给出明确提示而非通用错误。"""
    email, _, response = _register(client, sent_codes)
    assert response.status_code == 200
    status, body = call_json(client, '/api/auth/send-code', {'email': email, 'purpose': 'register'})
    assert status == 409
    assert '已注册' in body['detail']


def call_json(client, path, payload):
    response = client.post(path, json=payload)
    return response.status_code, response.json()


def test_change_password_requires_current_password(client, sent_codes):
    email, _, response = _register(client, sent_codes)
    token = response.json()['token']
    headers = {'Authorization': f'Bearer {token}'}
    assert client.post('/api/auth/change-password', json={'current_password': 'wrong', 'new_password': 'NewPass@2026'}, headers=headers).status_code == 422
    assert client.post('/api/auth/change-password', json={'current_password': 'Invoice@2026', 'new_password': 'NewPass@2026'}, headers=headers).status_code == 200
    assert client.post('/api/auth/login', json={'email': email, 'password': 'NewPass@2026'}).status_code == 200
