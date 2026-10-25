"""Explicit permanent deletion, restricted to items already in the recycle bin."""
import json
from fastapi import HTTPException
from . import storage as db

def purge(kind, ident, confirmed):
    if not confirmed:
        raise HTTPException(400, '請先確認永久刪除。')
    files=set()
    with db.connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        records={(k,i):json.loads(body) for k,i,body in conn.execute('SELECT kind,id,body FROM records')}
        target=records.get((kind,ident))
        if not target or not target.get('deleted'):
            raise HTTPException(409, '只能永久刪除回收區中的項目。')
        if any(k=='runs' and r.get('status') in {'uploading','submitting','queued','running','downloading','reconnecting'} or k=='prompt_jobs' and r.get('status')=='running' for (k,_),r in records.items()):
            raise HTTPException(409, '請等待生成與提示詞任務完成後再永久刪除。')
        removals={(kind,ident)}
        updates={}
        if kind=='projects':
            for (k,i),r in records.items():
                if k in ('runs','prompt_jobs') and r.get('project_id')==ident: removals.add((k,i))
                if k=='assets' and r.get('scope')=='project':
                    owners=r.get('project_ids',[r.get('project_id')])
                    if ident in owners:
                        remaining=[p for p in owners if p!=ident]
                        if remaining: updates[(k,i)]={**r,'project_ids':remaining,'project_id':remaining[0]}
                        else: removals.add((k,i))
        removed_assets={i for k,i in removals if k=='assets'}
        for key,r in records.items():
            if key[0]=='runs' and key not in removals:
                outputs=[a for a in r.get('outputs',[]) if a['id'] not in removed_assets]
                if len(outputs)!=len(r.get('outputs',[])): updates[key]={**r,'outputs':outputs}
        for key in removals:
            r=records[key]
            if key[0]=='assets': files.add(('media',r.get('filename','')))
            if key[0]=='runs': files.update(('latents',a['filename']) for a in r.get('latents',[]))
            conn.execute('DELETE FROM records WHERE kind=? AND id=?',key)
        for key,r in updates.items():
            conn.execute('UPDATE records SET body=? WHERE kind=? AND id=?',(json.dumps(r,ensure_ascii=False),*key))
        # Shared imports reuse immutable files. Never unlink bytes still owned elsewhere.
        for (k,i),r in records.items():
            if (k,i) not in removals and k=='assets': files.discard(('media',r.get('filename','')))
    for folder,name in files:
        root=(db.DATA/folder).resolve()
        path=(root/name).resolve()
        if name and path.parent==root and path.is_file(): path.unlink()
    return {'deleted':True}
