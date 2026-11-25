"""真实注册登录闭环验证（需要服务已启动）。

用法：
    .venv/Scripts/python.exe scripts/verify_auth_real.py <邮件中收到的6位验证码>

除最后一步"投递邮件"外，全部走真实 HTTP、真实 MySQL、真实 JWT。
"""
import json
import sys
import urllib.request
import urllib.error

BASE = 'http://127.0.0.1:8000'
EMAIL = '1244399824@qq.com'
PASSWORD = 'Invoice@2026'


def call(path, payload=None, token=None):
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(BASE + path, data=data, method='POST' if data else 'GET')
    request.add_header('Content-Type', 'application/json')
    if token:
        request.add_header('Authorization', 'Bearer ' + token)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        body = error.read().decode()
        try:
            return error.code, json.loads(body)
        except json.JSONDecodeError:
            return error.code, body


def main():
    code = sys.argv[1] if len(sys.argv) > 1 else ''
    if not code:
        print('请传入邮件中收到的 6 位验证码：python scripts/verify_auth_real.py 123456')
        return 2
    results = []

    status, body = call('/api/auth/register', {
        'email': EMAIL, 'name': '邱总', 'company': '鹏城信息技术',
        'password': PASSWORD, 'code': code,
    })
    results.append(('用邮件验证码注册', status == 200 and 'token' in body, f'{status} {str(body)[:100]}'))
    token = body.get('token', '') if isinstance(body, dict) else ''

    status, body = call('/api/auth/me', token=token)
    user = body.get('user', {}) if isinstance(body, dict) else {}
    results.append(('令牌换取当前用户', status == 200 and user.get('email') == EMAIL, f'{status} {str(body)[:100]}'))

    status, body = call('/api/auth/login', {'email': EMAIL, 'password': PASSWORD})
    results.append(('用邮箱密码登录', status == 200 and 'token' in body, f'{status} {str(body)[:60]}'))

    status, body = call('/api/auth/login', {'email': EMAIL, 'password': 'wrong-password'})
    results.append(('错误密码被拒绝', status == 401, f'{status} {body}'))

    status, body = call('/api/auth/me', token='bogus-token')
    results.append(('无效令牌被拒绝', status == 401, f'{status} {body}'))

    print('\n=== 真实注册登录闭环验证 ===')
    failed = 0
    for name, ok, detail in results:
        print(('  PASS  ' if ok else '  FAIL  ') + name + '  | ' + str(detail)[:86])
        if not ok:
            failed += 1
    print(f'\n总计 {len(results)} 项，失败 {failed} 项')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
