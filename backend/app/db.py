import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from . import config


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


@contextmanager
def connection():
    con = sqlite3.connect(config.DATA / 'invoices.sqlite3', timeout=30)
    con.row_factory = sqlite3.Row
    con.execute('PRAGMA foreign_keys=ON')
    try:
        yield con
        con.commit()
    except BaseException:
        con.rollback()
        raise
    finally:
        con.close()


def init():
    config.ensure_dirs()
    with connection() as con:
        con.execute('PRAGMA journal_mode=WAL')
        con.executescript('''
        CREATE TABLE IF NOT EXISTS invoices (
          id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, page INTEGER NOT NULL,
          filename TEXT NOT NULL, original_path TEXT NOT NULL, preview_path TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'needs_review', source TEXT NOT NULL,
          doc TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          revision INTEGER NOT NULL DEFAULT 1,
          UNIQUE(sha256, page)
        );
        CREATE TABLE IF NOT EXISTS jobs (
          id TEXT PRIMARY KEY, data TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit (
          id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL,
          invoice_id TEXT, summary TEXT NOT NULL, changes TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')


DEFAULTS = {'workspace_name': '我的财务工作区', 'confidence_threshold': 0.9, 'amount_tolerance': '0.02'}


def settings():
    with connection() as con:
        result = DEFAULTS.copy()
        result.update({r['key']: json.loads(r['value']) for r in con.execute('SELECT * FROM settings')})
        return result


def audit(action, summary, invoice_id=None, changes=None, con=None):
    values = (action, invoice_id, summary, json.dumps(changes or {}, ensure_ascii=False), now())
    if con is not None:
        con.execute('INSERT INTO audit(action,invoice_id,summary,changes,created_at) VALUES (?,?,?,?,?)', values)
    else:
        with connection() as conn:
            conn.execute('INSERT INTO audit(action,invoice_id,summary,changes,created_at) VALUES (?,?,?,?,?)', values)


def save_job(job):
    with connection() as con:
        con.execute('INSERT OR REPLACE INTO jobs VALUES(?,?,?)', (job['id'], json.dumps(job, ensure_ascii=False), now()))


def interrupted_jobs():
    with connection() as con:
        for row in con.execute('SELECT * FROM jobs').fetchall():
            job = json.loads(row['data'])
            if job['status'] in ['queued', 'running']:
                job.update(status='failed', error='服务重启导致任务中断，请重新导入；已完成的票据会自动跳过。')
                con.execute('UPDATE jobs SET data=?,updated_at=? WHERE id=?', (json.dumps(job, ensure_ascii=False), now(), job['id']))
