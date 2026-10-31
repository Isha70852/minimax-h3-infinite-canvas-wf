"""Read-only media archive: registered folders, canvas provenance and embedded metadata."""
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from threading import RLock, Lock
from urllib.parse import urlencode

import imageio_ffmpeg
from PIL import Image, ImageOps
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from . import storage as db
from .archive_comfy import extract, summarize

router=APIRouter(prefix='/api/archive',tags=['Media archive'])
KINDS={**dict.fromkeys(['.mp4','.webm','.mov','.mkv','.avi'],'video'),**dict.fromkeys(['.png','.jpg','.jpeg','.webp','.gif','.bmp','.tif','.tiff'],'image'),**dict.fromkeys(['.mp3','.wav','.flac','.ogg','.m4a','.aac','.opus'],'audio')}
LOCK=RLock()
THUMB_LOCK=Lock()
INDEX={}
CACHE={}
THUMBS=db.DATA/'archive-thumbnails'
FLAGS={'creationflags':0x08000000} if os.name=='nt' else {}

def safe_numbers(value):
    if isinstance(value,int) and abs(value)>9007199254740991:return str(value)
    if isinstance(value,dict):return {str(k):safe_numbers(v) for k,v in value.items()}
    if isinstance(value,list):return [safe_numbers(v) for v in value]
    return value

def folder(path):
    p=Path(path).expanduser()
    if not p.is_absolute() or not p.is_dir():raise HTTPException(400,'請選擇存在的絕對資料夾路徑。')
    return p.resolve()

class Source(BaseModel):
    path:str=Field(min_length=1,max_length=2000)
    label:str=Field(default='',max_length=120)

@router.get('/sources')
def sources():
    return [{'id':'canvas','label':'畫布專案素材','path':'','builtin':True}]+db.all_records('archive_sources')

@router.post('/sources')
def add_source(body:Source):
    p=folder(body.path);sid=hashlib.sha256(str(p).casefold().encode()).hexdigest()[:24]
    return db.put('archive_sources',sid,{'path':str(p),'label':body.label.strip() or p.name or str(p)})

@router.delete('/sources/{sid}')
def remove_source(sid:str):
    # Removing a source only unregisters it; never changes files on disk.
    with db.connection() as conn:conn.execute("DELETE FROM records WHERE kind='archive_sources' AND id=?",(sid,))
    with LOCK:
        for key in list(INDEX):
            if INDEX[key]['source_id']==sid:INDEX.pop(key,None)
    return {'ok':True}

@router.get('/folders')
def folders(path:str=''):
    if not path:
        roots=[str(Path(f'{chr(n)}:/')) for n in range(65,91) if Path(f'{chr(n)}:/').is_dir()] if os.name=='nt' else ['/']
        return {'path':'','parent':None,'folders':[{'name':p,'path':p} for p in roots]}
    p=folder(path)
    try:children=sorted((x for x in p.iterdir() if x.is_dir() and not x.is_symlink()),key=lambda x:x.name.casefold())
    except OSError:raise HTTPException(403,'無法讀取此資料夾。')
    return {'path':str(p),'parent':str(p.parent) if p.parent!=p else '', 'folders':[{'name':x.name,'path':str(x)} for x in children]}

def item(path,source,asset=None):
    st=path.stat();key=hashlib.sha256((source['id']+'\0'+str(path)+'\0'+(asset.get('id','') if asset else '')).encode()).hexdigest()
    result={'id':key,'name':asset['name'] if asset else path.name,'kind':KINDS[path.suffix.lower()],'source_id':source['id'],'source':source['label'],'path':str(path),'size':st.st_size,'modified':st.st_mtime,'asset_id':asset.get('id') if asset else None,'run_id':asset.get('run_id') if asset else None,'project_id':asset.get('project_id') if asset else None}
    result['url']='/api/archive/media/'+key
    result['thumbnail_url']='/api/archive/thumbnail/'+key+'?v='+str(st.st_mtime_ns)
    return result

@router.get('/items')
def items(source_id:str='',project_id:str='',q:str='',kind:str='',offset:int=Query(0,ge=0),limit:int=Query(80,ge=1,le=200),refresh:bool=False):
    with LOCK:
        if refresh or not INDEX:
            found={};warnings=[]
            projects={p['id']:p for p in db.all_records('projects')}
            runs={r['id']:r for r in db.all_records('runs')}
            for a in db.all_records('assets'):
                if a.get('deleted') or not a.get('project_id') or projects.get(a.get('project_id'),{}).get('deleted'):continue
                p=(db.MEDIA/a['filename']).resolve()
                if not p.is_relative_to(db.MEDIA.resolve()) or not p.is_file() or p.suffix.lower() not in KINDS:continue
                try:
                    project=projects.get(a.get('project_id'),{})
                    run=runs.get(a.get('run_id'),{})
                    node=next((n for n in project.get('nodes',[]) if n['id']==run.get('node_id')),None)
                    label=node.get('data',{}).get('label') if node else None
                    display={**a,'name':(label+' · '+a['name']) if label else a['name']}
                    entry=item(p,{'id':'canvas','label':'畫布 · '+project.get('name','專案')},display);found[entry['id']]=entry
                except OSError:pass
            for source in db.all_records('archive_sources'):
                root=Path(source['path'])
                if not root.is_dir():warnings.append('資料夾不存在：'+source['label']);continue
                count=0
                def onerror(error):warnings.append('部分子資料夾無法讀取：'+source['label'])
                for base,dirs,files in os.walk(root,followlinks=False,onerror=onerror):
                    dirs[:]=[d for d in dirs if not d.startswith('.') and not Path(base,d).is_symlink()]
                    for name in files:
                        p=Path(base,name)
                        if p.suffix.lower() not in KINDS:continue
                        try:
                            p=p.resolve()
                            if not p.is_relative_to(root.resolve()):continue
                            entry=item(p,source);found[entry['id']]=entry;count+=1
                        except OSError:continue
                    if count>=20000:warnings.append(source['label']+' 已達單來源 20,000 筆上限');break
            INDEX.clear();INDEX.update(found);CACHE.clear()
            CACHE['_warnings']=warnings
        selected=[v for v in INDEX.values() if (not project_id or v['source_id']!='canvas' or v.get('project_id')==project_id) and (not source_id or v['source_id']==source_id) and (not kind or v['kind']==kind) and (not q or q.casefold() in (v['name']+' '+v['path']).casefold())]
        selected.sort(key=lambda v:v['modified'],reverse=True)
        return {'items':selected[offset:offset+limit],'total':len(selected),'warnings':CACHE.get('_warnings',[])}

def resolve(id):
    with LOCK:entry=INDEX.get(id)
    if not entry:raise HTTPException(404,'請重新整理素材列表。')
    p=Path(entry['path']).resolve()
    source=db.get('archive_sources',entry['source_id']) if entry['source_id']!='canvas' else {'path':str(db.MEDIA)}
    if not source or not p.is_relative_to(Path(source['path']).resolve()) or not p.is_file() or p.suffix.lower() not in KINDS:raise HTTPException(404,'來源已移除或檔案不存在。')
    return entry,p

@router.get('/media/{id}')
def media(id:str):
    _,p=resolve(id);return FileResponse(p)

@router.get('/thumbnail/{id}')
def thumbnail(id:str):
    entry,p=resolve(id)
    if entry['kind']=='audio':raise HTTPException(404,'音訊無縮圖。')
    st=p.stat();key=hashlib.sha256(f'{p}:{st.st_mtime_ns}:{st.st_size}'.encode()).hexdigest()
    THUMBS.mkdir(exist_ok=True);target=THUMBS/(key+'.jpg')
    with THUMB_LOCK:
        if not target.exists():
            try:
                if entry['kind']=='image':
                    with Image.open(p) as im:
                        im=ImageOps.exif_transpose(im);im.thumbnail((480,360));im.convert('RGB').save(target,quality=82)
                else:
                    result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-i',str(p),'-frames:v','1','-vf','scale=480:-2','-y',str(target)],capture_output=True,timeout=25,**FLAGS)
                    if result.returncode:raise ValueError('thumbnail failed')
            except Exception:
                target.unlink(missing_ok=True);raise HTTPException(422,'無法擷取縮圖，可嘗試直接播放。')
    return FileResponse(target,media_type='image/jpeg')

def text_value(raw):
    if isinstance(raw,bytes):
        if raw.startswith(b'UNICODE\x00'):
            raw=raw[8:]
            return raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-16-be',errors='replace').strip('\x00')
        if raw.startswith(b'ASCII\x00\x00\x00'):raw=raw[8:]
        return raw.decode('utf-8',errors='replace')
    return str(raw)

def sidecar(text):
    fields={};mapping=[];prompt=[];inside=False
    for line in text.splitlines():
        if line.strip()=='PROMPT BEGIN':inside=True;continue
        if line.strip()=='PROMPT END':inside=False;continue
        if inside:prompt.append(line);continue
        m=re.match(r'^([A-Za-z0-9_]+)=(.*)$',line)
        if m:fields[m[1]]=m[2]
        elif re.match(r'^<(Picture|Video|Audio) \d+>=',line):mapping.append(line)
    body='\n'.join(prompt).strip().strip('=').strip()
    return {'label':'同名 TXT / Colab','prompt':body or (text if not fields else ''),'parameters':fields,'references':mapping,'raw':text}

def webui(text):
    lines=text.strip().splitlines();start=next((i for i in range(len(lines)-1,-1,-1) if re.match(r'^Steps:\s*\d+',lines[i])),None)
    if start is None:return None
    prompt='\n'.join(lines[:start]);positive,sep,negative=prompt.partition('Negative prompt:')
    params=dict(re.findall(r'([\w /-]+):\s*("(?:[^"\\]|\\.)*"|.*?)(?=,\s*[\w /-]+:|$)',', '.join(lines[start:])))
    return {'label':'Stable Diffusion WebUI','prompt':positive.strip(),'negative_prompt':negative.strip() if sep else '', 'parameters':{k.strip():v.strip() for k,v in params.items()},'raw':text}

def probe(path):
    ffprobe=shutil.which('ffprobe')
    if ffprobe:
        result=subprocess.run([ffprobe,'-v','error','-show_format','-show_streams','-of','json',str(path)],capture_output=True,timeout=30,**FLAGS)
        if result.returncode:raise ValueError('ffprobe 無法讀取媒體')
        return json.loads(result.stdout)
    # Portable installation already bundles ffmpeg; ffprobe is optional.
    result=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-i',str(path),'-f','ffmetadata','-'],capture_output=True,timeout=30,**FLAGS)
    text=result.stdout.decode('utf-8',errors='replace');tags={};pending=''
    for line in text.splitlines():
        pending+=line
        if pending.endswith('\\') and not pending.endswith('\\\\'):pending=pending[:-1]+'\n';continue
        if '=' in pending and not pending.startswith((';','[')):
            k,v=pending.split('=',1);tags[k]=re.sub(r'\\([\\=;#])',r'\1',v)
        pending=''
    stderr=result.stderr.decode('utf-8',errors='replace');duration=re.search(r'Duration: (\d+):(\d+):([\d.]+)',stderr)
    return {'format':{'tags':tags,'duration':sum(float(n)*factor for n,factor in zip(duration.groups(),(3600,60,1))) if duration else None},'streams':[], 'probe_note':'使用內附 ffmpeg 讀取；安裝 ffprobe 可取得更完整的編碼及串流資訊。'}

@router.get('/items/{id}')
def detail(id:str):
    entry,p=resolve(id);stat=p.stat()
    sibling=next((x for x in p.parent.iterdir() if x.stem.casefold()==p.stem.casefold() and x.suffix.lower()=='.txt'),None)
    if sibling and not sibling.resolve().is_relative_to(p.parent.resolve()):sibling=None
    stamp=(stat.st_mtime_ns,stat.st_size,sibling.stat().st_mtime_ns if sibling else None)
    with LOCK:
        cached=CACHE.get(id)
        if cached and cached[0]==stamp:return cached[1]
    records=[];warnings=[];technical={};embedded={}
    if entry.get('run_id'):
        run=db.get('runs',entry['run_id'])
        if run:
            spec=run.get('spec',{});records.append({'label':'畫布生成紀錄','prompt':run.get('compiled',{}).get('prompt') or spec.get('prompt') or '', 'parameters':safe_numbers({'spec':spec,'seed':run.get('seed'),'usage':run.get('usage'),'status':run.get('status'),'created_at':run.get('created_at')}),'raw':json.dumps({k:run[k] for k in ('id','spec','seed','compiled','usage') if k in run},ensure_ascii=False,indent=2)})
    if sibling:
        if sibling.stat().st_size<=4*1024*1024:records.append(sidecar(sibling.read_text(encoding='utf-8-sig',errors='replace')))
        else:warnings.append('同名 TXT 超過 4 MB，未載入。')
    try:
        if entry['kind']=='image':
            with Image.open(p) as im:
                technical={'width':im.width,'height':im.height,'format':im.format,'mode':im.mode}
                tags={k:text_value(v) for k,v in im.info.items() if isinstance(v,(str,bytes)) and k!='icc_profile'}
                exif=im.getexif()
                comment=exif.get(37510) or exif.get_ifd(34665).get(37510) if exif else None
                if comment:tags['UserComment']=text_value(comment)
                embedded=extract({'format':{'tags':tags}})
                for k in ('parameters','UserComment','comment','Description','description'):
                    if tags.get(k):
                        record=webui(tags[k])
                        if record:records.append(record);break
                if tags:records.append({'label':'圖片文字中繼資料','parameters':tags,'raw':json.dumps(tags,ensure_ascii=False,indent=2)})
        else:
            raw=probe(p);fmt=raw.get('format',{});streams=raw.get('streams',[])
            technical={k:fmt[k] for k in ('duration','bit_rate','format_name','size') if k in fmt}
            technical['streams']=[{k:s[k] for k in ('codec_type','codec_name','width','height','avg_frame_rate','sample_rate','channels','duration') if k in s} for s in streams]
            if raw.get('probe_note'):warnings.append(raw['probe_note'])
            embedded=extract(raw)
            tags={'format':fmt.get('tags',{}),'streams':[s.get('tags',{}) for s in streams if s.get('tags')]}
            if tags['format'] or tags['streams']:records.append({'label':'媒體內嵌標籤','parameters':safe_numbers(tags),'raw':json.dumps(tags,ensure_ascii=False,indent=2)})
        if embedded:
            summary=summarize(embedded);records.append({'label':'ComfyUI 內嵌工作流（靜態解析）','prompt':'\n\n'.join(str(e['value']) for e in summary.get('prompts',[]) if isinstance(e['value'],str)),'parameters':safe_numbers(summary),'raw':json.dumps(embedded,ensure_ascii=False,indent=2)})
            warnings.extend(summary.get('warnings',[]))
    except Exception as error:warnings.append('部分中繼資料無法解析：'+str(error)[:300])
    if not records:warnings.append('沒有找到生成紀錄；無法從成品還原未保存的提示詞或模型參數。')
    value={**entry,'technical':technical,'records':records,'warnings':warnings}
    with LOCK:
        if len(CACHE)>400:CACHE.clear()
        CACHE[id]=(stamp,value)
    return value
