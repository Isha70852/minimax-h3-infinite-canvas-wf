import json
import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('H3_CANVAS_DATA', ROOT / 'data'))
MEDIA = DATA / 'media'
MEDIA.mkdir(parents=True, exist_ok=True)


@contextmanager
def connection():
    db = sqlite3.connect(DATA / 'canvas.sqlite', timeout=30)
    try:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE IF NOT EXISTS records (kind TEXT, id TEXT, body TEXT, updated REAL, PRIMARY KEY(kind,id))')
        with db:
            yield db
    finally:
        db.close()


def put(kind, id, body):
    body = {**body, 'id': id, 'updated_at': time.time()}
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?)', (kind, id, json.dumps(body, ensure_ascii=False), body['updated_at']))
    return body


def get(kind, id):
    with connection() as db:
        row = db.execute('SELECT body FROM records WHERE kind=? AND id=?', (kind, id)).fetchone()
    return json.loads(row[0]) if row else None


def all_records(kind):
    with connection() as db:
        return [json.loads(row[0]) for row in db.execute('SELECT body FROM records WHERE kind=? ORDER BY updated DESC', (kind,))]


DEFAULT_SETTINGS = {'comfy_url': 'http://127.0.0.1:8188', 'runninghub_url': 'https://www.runninghub.cn',
                    'runninghub_key': '', 'workflow_id': '', 'motion_workflow_id': '', 'instance_type': 'default'}


def settings():
    return {**DEFAULT_SETTINGS, **(get('settings', 'default') or {})}
