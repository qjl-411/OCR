"""Cross-platform first-run installer and launcher. No Node.js needed to run."""
import argparse
import hashlib
import os
import subprocess
import sys
import threading
import venv
import webbrowser
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def load_env_file():
    """读取项目根目录的 .env，补充环境变量（已存在的环境变量优先）。"""
    env_file=ROOT/'.env'
    if not env_file.is_file():return
    for raw in env_file.read_text(encoding='utf-8').splitlines():
        line=raw.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.split('=',1)
        key=key.strip()
        value=value.strip().strip('"').strip("'")
        if key and key not in os.environ:os.environ[key]=value


def main():
    parser=argparse.ArgumentParser(description='票序 智能发票系统 本地启动器')
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--no-demo',action='store_true',help='首次启动不初始化合成演示数据')
    parser.add_argument('--install-only',action='store_true')
    args=parser.parse_args()
    if sys.version_info<(3,11):raise SystemExit('请先安装 Python 3.11 或更高版本，推荐 Python 3.12。')
    if not 1<=args.port<=65535:raise SystemExit('端口范围应为 1–65535。')
    os.chdir(ROOT)
    load_env_file()
    sys.path.insert(0,str(ROOT/'scripts'))
    from restore_models import restore
    restore()
    env_dir=ROOT/'.venv'
    interpreter=env_dir/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not interpreter.is_file():
        print('正在创建项目运行环境……',flush=True)
        venv.EnvBuilder(with_pip=True).create(env_dir)
    requirements=ROOT/('requirements.lock.txt' if (ROOT/'requirements.lock.txt').is_file() else 'requirements.txt')
    digest=hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker=env_dir/'.invoice-dependencies'
    if not marker.exists() or marker.read_text()!=digest:
        print('正在安装运行依赖，首次安装需要联网……',flush=True)
        subprocess.run([str(interpreter),'-m','pip','install','-r',str(requirements)],check=True)
        marker.write_text(digest)
    if args.install_only:
        print('运行依赖已安装。');return
    if not (ROOT/'dist/index.html').is_file():
        raise SystemExit('缺少预构建前端，请在项目根目录执行 npm --prefix frontend ci，然后执行 npm run build。')
    env=os.environ.copy()
    if args.no_demo:env['INVOICE_SEED_DEMO']='0'
    url=f'http://127.0.0.1:{args.port}'
    print(f'票序已准备启动：{url}\n按 Ctrl+C 停止服务。',flush=True)
    if not args.no_browser:
        # Poll health before opening the page; demo initialization takes a moment.
        def open_when_ready():
            import time
            import urllib.request
            for _ in range(60):
                try:
                    with urllib.request.urlopen(url+'/api/health',timeout=1) as response:
                        if response.status==200:webbrowser.open(url);return
                except Exception:time.sleep(.5)
        threading.Thread(target=open_when_ready,daemon=True).start()
    try:
        result=subprocess.run([str(interpreter),'-m','uvicorn','backend.app.main:app','--host',args.host,'--port',str(args.port)],env=env)
        raise SystemExit(result.returncode)
    except KeyboardInterrupt:
        pass


if __name__=='__main__':
    try:main()
    except subprocess.CalledProcessError as e:
        raise SystemExit(f'启动步骤失败（退出码 {e.returncode}），请检查上方错误信息。')
