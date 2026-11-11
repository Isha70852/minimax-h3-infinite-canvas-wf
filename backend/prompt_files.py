"""AI writing templates: read-only built-ins shipped with the app plus local user files.

Built-in templates live in backend/builtin_prompts/ and are part of the program.
Everything the user creates, edits, renames or deletes is stored under the local
data directory (data/prompts/, never committed or packaged):

* a user file with the same name as a built-in overrides it;
* deleting or renaming a built-in only hides it (recorded in .hidden.json);
* saving a built-in back to its original text removes the override again.

The legacy repository-level prompts/ folder is migrated once: files that differ
from the built-ins (personal templates or edits) are copied into data/prompts/.
"""
import hashlib
import json
import os
import re
import threading
import uuid
from pathlib import Path
from fastapi import HTTPException
from .workflow import ROOT
from .storage import DATA

BUILTIN = Path(__file__).resolve().parent / 'builtin_prompts'
DIRECTORY = DATA / 'prompts'
LEGACY = ROOT / 'prompts'
HIDDEN = DIRECTORY / '.hidden.json'
MIGRATED = DIRECTORY / '.migrated'
LOCK = threading.RLock()


def _files(folder):
    if not folder.is_dir(): return {}
    found = {}
    for path in sorted(folder.iterdir(), key=lambda p: p.name.casefold()):
        if path.name.startswith('.') or path.suffix.lower() not in ('.md', '.txt') or not path.is_file() or path.is_symlink(): continue
        content = path.read_text(encoding='utf-8-sig')
        if content.strip(): found[path.name] = content
    return found


def _same(a, b):
    return a.replace('\r', '').strip() == b.replace('\r', '').strip()


def _hidden():
    try:
        return set(json.loads(HIDDEN.read_text(encoding='utf-8')))
    except (OSError, ValueError):
        return set()


def _write(path, content):
    temp = path.with_name('.' + uuid.uuid4().hex + '.tmp')
    try:
        temp.write_text(content, encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def migrate():
    with LOCK:
        if MIGRATED.exists(): return
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        builtins = _files(BUILTIN)
        for name, content in _files(LEGACY).items():
            if name in builtins and _same(content, builtins[name]): continue
            target = DIRECTORY / name
            if not target.exists(): _write(target, content)
        MIGRATED.write_text('legacy prompts/ copied\n', encoding='utf-8')


def snapshot():
    migrate()
    builtins, user, hidden = _files(BUILTIN), _files(DIRECTORY), _hidden()
    names = sorted({*(n for n in builtins if n not in hidden), *user}, key=str.casefold)
    templates = [{'id': n, 'name': Path(n).stem, 'content': user.get(n, builtins.get(n)),
                  'builtin': n in builtins, 'customized': n in builtins and n in user} for n in names]
    digest = hashlib.sha256(repr((templates, sorted(hidden))).encode('utf-8')).hexdigest()
    return templates, digest


def save(templates, revision, default_id):
    with LOCK:
        existing, current = snapshot()
        if revision != current: raise HTTPException(409, '模板檔案已變更，請重新開啟設定後再儲存。')
        builtins, user = _files(BUILTIN), _files(DIRECTORY)
        old = {t['id']: t for t in existing}
        plan = {}; ids = set(); mapped_default = ''
        for t in templates:
            name = t['name'].strip()
            if not name or re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name.endswith(('.', ' ')) or name.startswith('.') or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I):
                raise ValueError('模板名稱不可包含路徑、特殊字元或 Windows 保留名稱。')
            suffix = Path(t['id']).suffix if t['id'] in old else '.md'
            filename = name + suffix
            target = DIRECTORY / filename
            if t['id'] in ids or filename.casefold() in plan: raise ValueError('模板名稱或 ID 不可重複。')
            if target.is_symlink() or (target.exists() and filename not in old): raise ValueError('檔名已存在，請選擇其他模板名稱。')
            if not t['content'].strip(): raise ValueError('模板內容不可為空。')
            ids.add(t['id']); plan[filename.casefold()] = (filename, t['content'])
            if t['id'] == default_id: mapped_default = filename
        DIRECTORY.mkdir(parents=True, exist_ok=True)
        # Keep recoverable originals of user files that change or disappear.
        trash = DIRECTORY / '.trash'
        for name, content in user.items():
            replacement = plan.get(name.casefold())
            if not replacement or replacement[1] != content or replacement[0] != name:
                trash.mkdir(exist_ok=True)
                (trash / (uuid.uuid4().hex + '-' + name)).write_text(content, encoding='utf-8')
        for filename, content in plan.values():
            if filename in builtins and _same(content, builtins[filename]):
                (DIRECTORY / filename).unlink(missing_ok=True)  # back to the shipped text
            else:
                _write(DIRECTORY / filename, content)
        for name in user:
            if name.casefold() not in plan: (DIRECTORY / name).unlink(missing_ok=True)
        hidden = {n for n in builtins if n.casefold() not in plan}
        if hidden: _write(HIDDEN, json.dumps(sorted(hidden), ensure_ascii=False))
        else: HIDDEN.unlink(missing_ok=True)
        return mapped_default or (next(iter(plan.values()))[0] if plan else '')
