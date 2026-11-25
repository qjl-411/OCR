import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.restore_models import restore
restore()
from backend.app import config
from backend.app.main import app


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(config,'DATA',tmp_path/'runtime')
    monkeypatch.setenv('INVOICE_SEED_DEMO','0')
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample():
    return (config.ROOT/'data'/'demo'/'demo-01.pdf').read_bytes()
