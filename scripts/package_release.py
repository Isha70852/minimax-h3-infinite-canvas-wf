"""Package only public source/docs and built frontend, never local state or runtimes."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import hashlib
ROOT=Path(__file__).resolve().parents[1]
FILES=['LICENSE','README.md','README.zh-TW.md','THIRD_PARTY_NOTICES.md','index.html','package.json','package-lock.json','requirements.txt','requirements.lock.txt','tsconfig.json','vite.config.ts','workflow_template.json','setup.ps1','install-runtime.ps1','start.ps1','package-share.ps1','啟動畫布.cmd']
DIRS=['prompts','src','backend','workflows','licenses','skills/h3-canvas-api','skills/minimax-h3-remote-skill','colab','example_workflows','dist','scripts']
EXTS={'.py','.tsx','.ts','.css','.json','.mjs','.md','.txt','.yaml','.yml','.ipynb','.html','.js','.svg','.map','.ps1'}
def package():
    if not (ROOT/'dist/index.html').exists():raise SystemExit('Run npm run build first.')
    import json
    version=json.loads((ROOT/'package.json').read_text(encoding='utf-8'))['version']
    out=ROOT/'release'/f'H3-Canvas-v{version}-windows.zip';out.parent.mkdir(exist_ok=True)
    paths=[ROOT/f for f in FILES]
    for folder in DIRS:
        paths += [p for p in (ROOT/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and not any(part.startswith('.') for part in p.relative_to(ROOT).parts) and (p.suffix.lower() in EXTS or p.name.upper().startswith(('LICENSE','NOTICE','COPYING')))]
    with ZipFile(out,'w',ZIP_DEFLATED) as z:
        for p in sorted(set(paths)):
            if p.is_file() and p.name != 'AGENTS.md' and ('prompts' not in p.relative_to(ROOT).parts[:1] or p.relative_to(ROOT/'prompts').as_posix() in json.loads((ROOT/'scripts/public_prompts.json').read_text(encoding='utf-8'))):z.write(p,'H3-Canvas/'+p.relative_to(ROOT).as_posix())
    digest=hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(digest+'  '+out.name+'\n',encoding='ascii')
    print(out)
if __name__=='__main__':package()
