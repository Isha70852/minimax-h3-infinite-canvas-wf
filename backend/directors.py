"""Materialize automation motion-context chains on the project canvas."""
import uuid
from . import storage as db

def attach(project_id, node_id, spec, update_spec=True):
    project = db.get('projects',project_id)
    if not project or project.get('deleted'): return
    nodes = project.get('nodes',[])
    current = next((n for n in nodes if n['id']==node_id),None)
    if not current: return
    if update_spec: current['data']['spec'] = spec
    previous = db.get('runs',spec.get('context_run_id')) if spec.get('context_run_id') else None
    if not previous and spec.get('context_video_asset_id'):
        previous = next((r for r in db.all_records('runs') if r['project_id']==project_id and any(a['id']==spec['context_video_asset_id'] for a in r.get('outputs',[]))),None)
    parent = previous['node_id'] if previous else None
    directors = [n for n in nodes if n.get('data',{}).get('kind')=='director']
    if any(node_id in n['data'].get('segments',[]) for n in directors):
        db.put('projects',project_id,project)
        return
    owner = next((n for n in directors if parent and n['data'].get('segments',[])[-1:]==[parent]),None)
    if owner:
        owner['data']['segments'].append(node_id)
    else:
        prefix = next((n['data']['segments'][:n['data']['segments'].index(parent)+1] for n in directors if parent in n['data'].get('segments',[])),[])
        valid_parent = parent and parent!=node_id and any(n['id']==parent for n in nodes)
        segments = prefix or ([parent] if valid_parent else [])
        nodes.append({'id':uuid.uuid4().hex,'type':'card','position':{'x':current['position']['x']-620,'y':current['position']['y']},'style':{'width':540,'height':540},'data':{'kind':'director','label':'Motion Context 導演台','segments':[*segments,node_id]}})
    db.put('projects',project_id,project)

def migrate():
    if db.get('migrations','automation_directors_v1'): return
    for run in sorted(db.all_records('runs'),key=lambda r:r.get('created_at',0)):
        if run.get('spec',{}).get('motion_context'):
            attach(run['project_id'],run['node_id'],run['spec'],update_spec=False)
    db.put('migrations','automation_directors_v1',{'complete':True})
