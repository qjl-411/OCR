"""Serve prebuilt UI and API together, including in a managed preview."""
import os
import sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
os.chdir(root)
interpreter=root/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
if interpreter.is_file() and Path(sys.executable).resolve()!=interpreter.resolve():
    os.execv(str(interpreter),[str(interpreter),str(Path(__file__).resolve())])
sys.path.insert(0,str(root))
if __name__=='__main__':
    import uvicorn
    port=int(os.getenv('PORT','8000'))
    host=os.getenv('HOST','127.0.0.1')
    # Managed preview daemon needs a reachable interface; ordinary local
    # startup stays on loopback unless explicitly configured.
    if os.getenv('SITES_MANAGED_LINUX_CONTAINER')=='1':host='0.0.0.0'
    uvicorn.run('backend.app.main:app',host=host,port=port)
