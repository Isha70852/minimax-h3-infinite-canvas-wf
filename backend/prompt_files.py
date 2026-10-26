"""UTF-8 prompt templates stored as editable files, with optimistic save checks."""
import hashlib
import os
import re
import threading
import uuid
from pathlib import Path
from fastapi import HTTPException
from .workflow import ROOT

DIRECTORY = ROOT / 'prompts'
LOCK = threading.RLock()

def snapshot():
    DIRECTORY.mkdir(exist_ok=True)
    templates=[]
    for path in sorted(DIRECTORY.iterdir(),key=lambda p:p.name.casefold()):
        if path.name.startswith('.') or path.suffix.lower() not in ('.md','.txt') or not path.is_file() or path.is_symlink(): continue
        content=path.read_text(encoding='utf-8-sig')
        if not content.strip(): continue
        templates.append({'id':path.name,'name':path.stem,'content':content})
    digest=hashlib.sha256(repr(templates).encode('utf-8')).hexdigest()
    return templates,digest

def save(templates, revision, default_id):
    with LOCK:
        existing,current=snapshot()
        if revision!=current: raise HTTPException(409,'prompts 檔案已變更，請重新開啟設定後再儲存。')
        old={t['id']:t for t in existing}
        plan={}; ids=set(); mapped_default=''
        for t in templates:
            name=t['name'].strip()
            if not name or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.endswith(('.', ' ')) or name.startswith('.') or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',name,re.I):
                raise ValueError('模板名稱不可包含路徑、特殊字元或 Windows 保留名稱。')
            suffix=Path(t['id']).suffix if t['id'] in old else '.md'
            filename=name+suffix
            target=DIRECTORY/filename
            if t['id'] in ids or filename.casefold() in plan: raise ValueError('模板名稱或 ID 不可重複。')
            if target.is_symlink() or (target.exists() and filename not in old): raise ValueError('檔名已存在，請選擇其他模板名稱。')
            if not t['content'].strip(): raise ValueError('模板內容不可為空。')
            ids.add(t['id']);plan[filename.casefold()]=(filename,t['content'])
            if t['id']==default_id: mapped_default=filename
        # Keep recoverable originals for edits, renames and deletions; never publish .trash.
        trash=DIRECTORY/'.trash'
        for t in existing:
            replacement=plan.get(t['id'].casefold())
            if not replacement or replacement[1]!=t['content'] or replacement[0]!=t['id']:
                trash.mkdir(exist_ok=True)
                (trash/(uuid.uuid4().hex+'-'+t['id'])).write_text(t['content'],encoding='utf-8')
        for filename,content in plan.values():
            temp=DIRECTORY/('.'+uuid.uuid4().hex+'.tmp')
            try:
                temp.write_text(content,encoding='utf-8')
                os.replace(temp,DIRECTORY/filename)
            finally: temp.unlink(missing_ok=True)
        for t in existing:
            if t['id'].casefold() not in plan: (DIRECTORY/t['id']).unlink()
        return mapped_default or (next(iter(plan.values()))[0] if plan else '')
