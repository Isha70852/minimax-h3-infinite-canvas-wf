"""Project media and shared assets. Deletion is reversible and retains referenced files."""
import json
import sqlite3
import time
import uuid
from . import storage as db


def belongs(asset, project_id):
    return asset.get('scope') == 'project' and project_id in asset.get('project_ids', [asset.get('project_id')])


def migrate():
    if db.get('migrations', 'library-v1'):
        return
    # Keep a consistent SQLite backup before changing legacy asset ownership.
    with db.connection() as source:
        with sqlite3.connect(db.DATA / 'before-library-v1.sqlite') as target:
            source.backup(target)
    membership = {}
    for project in db.all_records('projects'):
        ids = {n.get('data', {}).get(k) for n in project.get('nodes', []) for k in ('asset_id', 'output_id')}
        ids.update(e.get('data', {}).get('asset_id') for e in project.get('edges', []))
        for aid in ids - {None}:
            membership.setdefault(aid, set()).add(project['id'])
    for run in db.all_records('runs'):
        ids = {r['asset_id'] for r in run.get('spec', {}).get('references', [])}
        ids.update(a['id'] for a in run.get('outputs', []))
        for aid in ids:
            membership.setdefault(aid, set()).add(run['project_id'])
    with db.connection() as conn:
        for asset in db.all_records('assets'):
            if 'scope' in asset:
                continue
            projects = sorted(membership.get(asset['id'], []))
            asset.update(scope='project' if projects else 'shared', project_ids=projects)
            conn.execute('UPDATE records SET body=? WHERE kind=? AND id=?', (json.dumps(asset, ensure_ascii=False), 'assets', asset['id']))
        conn.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?)', ('migrations', 'library-v1', '{}', time.time()))


def import_shared(asset, project_id):
    for existing in db.all_records('assets'):
        if belongs(existing, project_id) and existing.get('source_asset_id') == asset['id'] and not existing.get('deleted'):
            return existing
    # Independent metadata, shared immutable media bytes; deleting either won't break the other.
    return db.put('assets', uuid.uuid4().hex, {**asset, 'scope': 'project', 'project_id': project_id,
        'project_ids': [project_id], 'source_asset_id': asset['id'], 'deleted': False, 'use_count': 0})
