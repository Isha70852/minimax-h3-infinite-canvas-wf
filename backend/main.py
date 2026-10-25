import asyncio
import contextlib
import json
import hashlib
import mimetypes
import re
import secrets
import subprocess
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

import httpx
import imageio_ffmpeg
from fastapi import FastAPI, HTTPException, UploadFile, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from pydantic import BaseModel, Field

from . import storage as db
from . import library
from . import recycle
from . import latent_transport
from .capabilities import CAPABILITIES
from . import prompting
from . import image_workflows
from .image_workflows import ImageGeneration
from .audio_workflows import AudioGeneration, REGISTRY, catalog, compile_audio, resolve_text
from .providers import provider, ProviderRejected
from .workflow import Generation, compile_workflow, MODELS, LORAS, ASPECTS, ROOT

workers = {}
ACTIVE = {'uploading', 'submitting', 'queued', 'running', 'downloading', 'reconnecting'}


def require(kind, id):
    value = db.get(kind, id)
    if not value:
        raise HTTPException(404, '找不到資料。')
    return value


def update_run(id, **changes):
    run = require('runs', id)
    return db.put('runs', id, {**run, **changes})


def public_run(run):
    return {k: v for k, v in run.items() if k not in ('connection',)}


def parse_spec(value):
    return ImageGeneration(**value) if value.get('kind') == 'image' else AudioGeneration(**value) if value.get('kind') == 'audio' else Generation(**value)


def compile_spec(spec, assets, filenames=None, seed=0):
    if isinstance(spec, ImageGeneration): return image_workflows.compile_image(spec, assets, filenames, seed)
    return compile_audio(spec, assets, filenames, seed) if isinstance(spec, AudioGeneration) else compile_workflow(spec, assets, filenames, seed)


def assets_for(spec):
    assets = {ref.asset_id: require('assets', ref.asset_id) for ref in spec.references}
    if isinstance(spec, Generation) and spec.context_video_asset_id:
        assets[spec.context_video_asset_id] = require('assets', spec.context_video_asset_id)
    return assets


async def execute(id):
    run = require('runs', id)
    engine = None
    watcher = None
    try:
        settings = {**db.settings(), **run.get('connection', {})}
        engine = provider(run['spec']['provider'], settings)
        spec = parse_spec(run['spec'])
        if not run.get('remote_id'):
            assets = assets_for(spec)
            compiled = compile_spec(spec, assets, seed=int(run['seed']))
            await engine.preflight(compiled['workflow'])
            filenames = {}
            for index, asset in enumerate(assets.values()):
                update_run(id, stage=f'上傳素材 {index + 1}/{len(assets)}')
                filenames[asset['id']] = await engine.upload(asset)
            compiled = compile_spec(spec, assets, filenames, seed=int(run['seed']))
            update_run(id, compiled=compiled, status='submitting', stage='提交生成任務')
            task_id = await engine.submit(compiled['workflow'], id, int(run['seed']))
            run = update_run(id, remote_id=task_id, status='queued', stage='等待運算資源')
        if spec.provider == 'comfyui':
            watcher = asyncio.create_task(engine.watch(id, run['remote_id'], lambda **kw: update_run(id, **kw)))
        errors = 0
        while True:
            try:
                result = await engine.query(run['remote_id'])
                errors = 0
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                errors += 1
                update_run(id, status='reconnecting', stage=f'連線中斷，正在重試查詢（{errors}）', progress=None)
                if errors >= 60:
                    raise ValueError('連續查詢失敗；遠端任務可能仍在執行，可從歷史紀錄恢復查詢。') from error
                await asyncio.sleep(5)
                continue
            if 'usage' in result:
                update_run(id, usage=result['usage'], task_usage_list=result.get('task_usage_list', []))
            if result['status'] == 'success':
                update_run(id, status='downloading', stage='保存生成結果', progress=None)
                outputs = []
                for output in result['outputs']:
                    ext = Path(output['filename']).suffix.lower()
                    if ext not in ('.mp4', '.webm', '.mov', '.png', '.jpg', '.jpeg', '.webp', '.wav', '.mp3', '.flac', '.ogg', '.gif'):
                        continue
                    filename = uuid.uuid4().hex + ext
                    path = db.MEDIA / filename
                    try:
                        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
                            async with client.stream('GET', output['url']) as response:
                                response.raise_for_status()
                                with path.open('wb') as file:
                                    async for chunk in response.aiter_bytes():
                                        file.write(chunk)
                        kind = 'video' if ext in ('.mp4', '.webm', '.mov') else 'audio' if ext in ('.wav', '.mp3', '.flac', '.ogg') else 'image'
                        aid = uuid.uuid4().hex
                        asset = db.put('assets', aid, {'scope': 'project', 'project_id': run['project_id'], 'name': f"生成結果 {len(outputs) + 1}{ext}", 'filename': filename, 'kind': kind, 'url': '/media/' + filename, 'run_id': id, 'size': path.stat().st_size})
                        outputs.append(asset)
                    except Exception:
                        path.unlink(missing_ok=True)
                        raise
                if not outputs:
                    raise ValueError('遠端任務完成，但沒有可保存的圖片、影片或聲音輸出。')
                update_run(id, outputs=outputs)
                latents=[]
                for output in result.get('latents',[]):
                    if Path(output['filename']).suffix.lower() in ('.safetensors','.latent','.zip'):
                        latents.append(await latent_transport.download(output,id))
                update_run(id, status='success', stage='生成完成', progress=100, outputs=outputs, latents=latents, finished_at=time.time(), error=None)
                return
            previous = require('runs', id)
            if result['status'] in ('running', 'queued'):
                update_run(id, status=result['status'], stage='正在生成' if result['status'] == 'running' else '等待運算資源', progress=None)
            elif previous['status'] == 'reconnecting':
                update_run(id, status='queued', stage='已恢復連線，等待遠端結果')
            await asyncio.sleep(3 if spec.provider == 'comfyui' else 5)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        message = str(error)
        key = db.settings().get('runninghub_key', '')
        if key:
            message = message.replace(key, '[redacted]')
        state = require('runs', id)
        uncertain = state['status'] == 'submitting' and not state.get('remote_id') and not isinstance(error, ProviderRejected)
        update_run(id, status='attention' if uncertain else 'failed', error=message[:6000],
                   stage='提交結果不明，請先查詢服務端，避免重複扣費' if uncertain else '生成失敗', progress=None)
    finally:
        if watcher:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher
        if engine:
            await engine.close()
        workers.pop(id, None)


def launch(id):
    if id not in workers:
        workers[id] = asyncio.create_task(execute(id))


@asynccontextmanager
async def lifespan(app):
    library.migrate()
    for job in db.all_records('prompt_jobs'):
        if job['status'] == 'running':
            db.put('prompt_jobs', job['id'], {**job, 'status': 'failed', 'error': '服務重啟；未自動重送提示詞請求，請確認後再試。'})
    for run in db.all_records('runs'):
        if run['status'] in ACTIVE:
            if run.get('remote_id'):
                launch(run['id'])
            else:
                update_run(run['id'], status='attention', stage='服務重啟，請確認遠端是否已收到任務', progress=None)
    yield
    tasks = list(workers.values())
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title='H3 Canvas', lifespan=lifespan)
app.include_router(prompting.router)
from . import chatgpt_auth
app.include_router(chatgpt_auth.router)


@app.middleware('http')
async def local_origin(request: Request, call_next):
    origin = request.headers.get('origin')
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin:
        parsed = urlparse(origin)
        if parsed.hostname not in ('localhost', '127.0.0.1'):
            return JSONResponse({'detail': '僅接受本機頁面的請求'}, status_code=403)
    return await call_next(request)


@app.exception_handler(ValueError)
async def invalid(request, error):
    return JSONResponse({'detail': str(error)}, status_code=422)


@app.get('/api/config')
def config():
    values = db.settings()
    profiles = values.get('models') or [{'name': name, 'shift_enabled': False, 'shift_video': 6, 'shift_audio': 3} for name in MODELS]
    return {'models': [m['name'] for m in profiles], 'model_profiles': profiles, 'image_workflows': image_workflows.catalog(), 'audio_workflows': catalog(), 'video_defaults': values.get('video_defaults', {}), 'loras': values.get('loras') or LORAS, 'aspects': ASPECTS}


@app.get('/api/capabilities')
def capabilities():
    return CAPABILITIES


@app.get('/api/settings')
def settings():
    settings = db.settings()
    return {**{k: v for k, v in settings.items() if k != 'runninghub_key'}, 'has_key': bool(settings['runninghub_key'])}


class ModelEntry(BaseModel):
    name: str = Field(min_length=1, max_length=500)
    shift_enabled: bool = False
    shift_video: float = Field(default=6, ge=0, le=100)
    shift_audio: float = Field(default=3, ge=0, le=100)


class Settings(BaseModel):
    comfy_url: str = 'http://127.0.0.1:8188'
    runninghub_url: str = 'https://www.runninghub.cn'
    runninghub_key: str | None = None
    workflow_id: str = ''
    motion_workflow_id: str = ''
    instance_type: str = 'default'
    models: list[ModelEntry] | None = Field(default=None, min_length=1, max_length=100)
    loras: list[str] | None = Field(default=None, min_length=1, max_length=100)
    clear_runninghub_key: bool = False
    image_workflow_ids: dict[str,str] | None = None
    audio_workflow_ids: dict[str,str] | None = None
    video_defaults: dict | None = None


@app.put('/api/settings')
def save_settings(body: Settings):
    body.motion_workflow_id = body.motion_workflow_id.strip()
    if body.motion_workflow_id and not body.motion_workflow_id.isdigit():
        raise ValueError("Motion Context 工作流 ID 必須為數字。")
    if body.loras and any(not n.strip() or len(n) > 500 for n in body.loras):
        raise ValueError('LoRA 檔名不可空白或超過 500 字。')
    if body.models and any(not m.name.strip() for m in body.models):
        raise ValueError('模型檔名不可空白。')
    for url in (body.comfy_url, body.runninghub_url):
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('服務網址必須是有效的 HTTP/HTTPS 網址。')
    if body.runninghub_url.rstrip('/') not in ('https://www.runninghub.cn', 'https://www.runninghub.ai'):
        raise ValueError('RunningHub 僅支援官方 cn / ai API 網址。')
    if body.instance_type not in ('default', 'plus', 'ultra'):
        raise ValueError('不支援的 RunningHub 機型。')
    data = body.model_dump(exclude_none=True, exclude={'clear_runninghub_key'})
    if body.image_workflow_ids is not None:
        if set(body.image_workflow_ids) - image_workflows.REGISTRY.keys(): raise ValueError('不支援的圖片工作流。')
        if any(v and not v.isdigit() for v in body.image_workflow_ids.values()): raise ValueError('工作流 ID 必須為數字。')
    if body.audio_workflow_ids is not None:
        if set(body.audio_workflow_ids) - REGISTRY.keys(): raise ValueError('不支援的音訊工作流。')
        if any(v and not v.isdigit() for v in body.audio_workflow_ids.values()): raise ValueError('工作流 ID 必須為數字。')
    if body.video_defaults is not None:
        defaults = Generation(**{**body.video_defaults, 'prompt': 'default', 'references': []}).model_dump()
        data['video_defaults'] = {k:v for k,v in defaults.items() if k not in ('prompt','references')}
    if body.clear_runninghub_key:
        data['runninghub_key'] = ''
    if body.models:
        data['models'] = [{**m, 'name': m['name'].strip()} for m in data['models']]
    if body.loras:
        data['loras'] = [n.strip() for n in body.loras]
    db.put('settings', 'default', {**db.settings(), **data})
    return settings()


@app.post('/api/connections/check')
async def check_connection():
    async with httpx.AsyncClient(timeout=8, trust_env=False) as client:
        try:
            response = await client.get(db.settings()['comfy_url'].rstrip('/') + '/object_info')
            response.raise_for_status()
            info = response.json()
            required = ['MiniMaxH3AudioConditioningT8', 'MiniMaxLowVRAMAttention', 'MiniMaxChunkFeedForward', 'MiniMaxH3SigmaShift', 'ModelAttentionBackend', 'BlockSparseAttention']
            return {'ok': True, 'missing': [name for name in required if name not in info]}
        except httpx.HTTPError as error:
            return {'ok': False, 'error': str(error)}


class Project(BaseModel):
    name: str = Field(default='未命名專案', min_length=1, max_length=120)
    nodes: list[dict] = Field(default_factory=list, max_length=3000)
    edges: list[dict] = Field(default_factory=list, max_length=10000)
    viewport: dict = Field(default_factory=lambda: {'x': 0, 'y': 0, 'zoom': 1})


@app.get('/api/projects')
def projects(deleted: bool = False):
    return [{k: p[k] for k in ('id', 'name', 'updated_at')} for p in db.all_records('projects') if bool(p.get('deleted')) == deleted]


@app.post('/api/projects')
def new_project(body: Project):
    return db.put('projects', uuid.uuid4().hex, body.model_dump())


@app.get('/api/projects/{id}')
def get_project(id: str):
    return require('projects', id)


@app.put('/api/projects/{id}')
def save_project(id: str, body: Project):
    if require('projects', id).get('deleted'):
        raise HTTPException(409, '專案已移至回收區，請先還原。')
    return db.put('projects', id, body.model_dump())


@app.delete('/api/projects/{id}')
def delete_project(id: str):
    project = require('projects', id)
    if any(r['project_id'] == id and r['status'] in ACTIVE for r in db.all_records('runs')) or any(j['project_id'] == id and j['status'] == 'running' for j in db.all_records('prompt_jobs')):
        raise HTTPException(409, '此專案還有執行中的任務，完成後才能刪除。')
    return db.put('projects', id, {**project, 'deleted': True})


@app.post('/api/projects/{id}/restore')
def restore_project(id: str):
    return db.put('projects', id, {**require('projects', id), 'deleted': False})


@app.delete('/api/projects/{id}/permanent')
def purge_project(id: str, confirm: bool = False):
    return recycle.purge('projects', id, confirm)


@app.delete('/api/assets/{id}/permanent')
def purge_asset(id: str, confirm: bool = False):
    return recycle.purge('assets', id, confirm)


@app.get('/api/assets')
def assets(project_id: str | None = None):
    if project_id:
        require('projects', project_id)
        return [a for a in db.all_records('assets') if library.belongs(a, project_id)]
    return [a for a in db.all_records('assets') if a.get('scope') == 'shared']


class AssetChange(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    favorite: bool | None = None
    deleted: bool | None = None


@app.patch('/api/assets/{id}')
def change_asset(id: str, body: AssetChange):
    asset = require('assets', id)
    return db.put('assets', id, {**asset, **body.model_dump(exclude_none=True)})


@app.post('/api/assets/{id}/use')
def use_asset(id: str):
    asset = require('assets', id)
    return db.put('assets', id, {**asset, 'use_count': asset.get('use_count', 0) + 1})


@app.post('/api/projects/{project_id}/import/{asset_id}')
def import_asset(project_id: str, asset_id: str):
    require('projects', project_id)
    asset = require('assets', asset_id)
    if asset.get('scope') != 'shared' or asset.get('deleted'):
        raise ValueError('請從共用資產庫選擇可用資產。')
    return library.import_shared(asset, project_id)



def normalize_media(path, kind):
    if kind == 'image':
        with Image.open(path) as image:
            image.verify()
        return path
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    flags = {'creationflags': 0x08000000} if __import__('os').name == 'nt' else {}
    if kind == 'video':
        probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(path)], capture_output=True, timeout=30, **flags)
        text = probe.stderr.decode('utf-8', errors='replace')
        match = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', text)
        if not match:
            raise ValueError('無法讀取影片時長。')
        duration = int(match[1]) * 3600 + int(match[2]) * 60 + float(match[3])
        if duration < 2 or duration > 15.1:
            raise ValueError('T8 參考影片需介於 2–15 秒，請先裁切後再上傳。')
        target = path.with_name(path.stem + '_24fps.mp4')
        command = [ffmpeg, '-v', 'error', '-i', str(path), '-map', '0:v:0', '-map', '0:a?', '-vf', 'fps=24', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-movflags', '+faststart', str(target)]
    else:
        target = path.with_suffix('.normalized.wav')
        command = [ffmpeg, '-v', 'error', '-i', str(path), '-vn', '-ac', '2', '-ar', '44100', str(target)]
    result = subprocess.run(command, capture_output=True, timeout=300, **flags)
    if result.returncode:
        target.unlink(missing_ok=True)
        raise ValueError('素材解碼失敗：' + result.stderr.decode('utf-8', errors='replace')[-500:])
    path.unlink()
    return target


@app.post('/api/assets')
async def upload(file: UploadFile, project_id: str | None = None, scope: str = 'shared'):
    if scope not in ('shared', 'project'):
        raise ValueError('不支援的素材範圍。')
    if scope == 'project':
        require('projects', project_id or '')
    name = Path(file.filename or '素材').name
    ext = Path(name).suffix.lower()
    kind = next((kind for kind, extensions in {'image': ['.png', '.jpg', '.jpeg', '.webp'], 'video': ['.mp4', '.mov', '.webm', '.mkv'], 'audio': ['.mp3', '.wav', '.flac', '.ogg', '.m4a']}.items() if ext in extensions), None)
    if not kind:
        raise ValueError('支援 PNG/JPG/WEBP、MP4/MOV/WEBM/MKV、MP3/WAV/FLAC/OGG/M4A。')
    id = uuid.uuid4().hex
    path = db.MEDIA / (id + ext)
    try:
        size = 0
        with path.open('wb') as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > 512 * 1024 * 1024:
                    raise ValueError('單一素材上限 512 MB。')
                out.write(chunk)
        path = await asyncio.to_thread(normalize_media, path, kind)
    except Exception as error:
        path.unlink(missing_ok=True)
        raise ValueError('無法匯入素材：' + str(error)) from error
    finally:
        await file.close()
    return db.put('assets', id, {'scope': scope, 'project_id': project_id if scope == 'project' else None, 'name': name, 'filename': path.name, 'kind': kind, 'url': '/media/' + path.name, 'size': path.stat().st_size})


@app.post('/api/workflow/preview')
def preview(spec: Generation | AudioGeneration | ImageGeneration):
    return compile_spec(spec, assets_for(spec), seed=0)


class RunRequest(BaseModel):
    project_id: str
    node_id: str
    request_id: str = Field(min_length=8, max_length=100)
    spec: Generation | AudioGeneration | ImageGeneration


@app.post('/api/runs')
async def start_run(body: RunRequest):
    project = require('projects', body.project_id)
    if project.get('deleted'):
        raise ValueError('專案已刪除，請先還原。')
    existing = db.get('runs', body.request_id)
    if existing:
        return public_run(existing)
    for run in db.all_records('runs'):
        if run['project_id'] == body.project_id and run['node_id'] == body.node_id and run['status'] in ACTIVE:
            raise HTTPException(409, '此節點已有進行中的任務。')
    if isinstance(body.spec, ImageGeneration):
        body.spec = image_workflows.resolve_text(body.spec, project)
    if isinstance(body.spec, AudioGeneration):
        body.spec = resolve_text(body.spec, project)
    if isinstance(body.spec, Generation):
        if body.spec.prompt_source:
            source=next((n for n in project.get('nodes',[]) if n['id']==body.spec.prompt_source and n.get('data',{}).get('kind')=='text'),None)
            if not source: raise ValueError('連接的文字提示詞節點不存在。')
            body.spec=body.spec.model_copy(update={'prompt':source['data'].get('text',''),'prompt_source':None})
            if not body.spec.prompt.strip(): raise ValueError('文字提示詞不可為空。')
        if (body.spec.context_run_id or body.spec.context_video_asset_id) and not body.spec.motion_context:
            raise ValueError('請使用導演台啟用 motion context。')
        if body.spec.context_run_id:
            previous=require('runs',body.spec.context_run_id)
            videos=[a for a in previous.get('outputs',[]) if a.get('kind')=='video']
            if previous['project_id']!=body.project_id or previous['status']!='success' or not videos:
                raise ValueError('前段必須為同專案已完成且含影片輸出的生成。')
            context_id=body.spec.context_video_asset_id or videos[0]['id']
            if context_id not in {a['id'] for a in videos}: raise ValueError('指定的影片不是前段輸出。')
            body.spec=body.spec.model_copy(update={'context_video_asset_id':context_id})
    assets = assets_for(body.spec)
    if any(not library.belongs(a, body.project_id) or a.get('deleted') for a in assets.values()):
        raise ValueError('引用素材不屬於此專案或已刪除，請先匯入專案素材。')
    seed = secrets.randbits(63)
    compiled = compile_spec(body.spec, assets, seed=seed)
    settings = db.settings()
    is_motion = isinstance(body.spec,Generation) and body.spec.motion_context
    settings['native_comfy'] = False
    if is_motion:
        settings['workflow_id'] = settings.get('motion_workflow_id', '')
    if isinstance(body.spec, ImageGeneration):
        settings['workflow_id'] = settings.get('image_workflow_ids', {}).get(body.spec.workflow, '')
    if isinstance(body.spec, AudioGeneration):
        settings['workflow_id'] = settings.get('audio_workflow_ids', {}).get(body.spec.workflow, '')
    if body.spec.provider == 'runninghub' and not settings['runninghub_key']:
        raise ValueError('請先在連線設定填入 RunningHub API Key。')
    if body.spec.provider == 'runninghub' and not settings['native_comfy'] and not settings['workflow_id'].strip():
        raise ValueError('請先在連線設定填入 RunningHub 工作流 ID（必填）。')
    run = db.put('runs', body.request_id, {'project_id': body.project_id, 'node_id': body.node_id,
        'spec': body.spec.model_dump(), 'seed': str(seed), 'compiled': compiled, 'status': 'uploading',
        'stage': '準備生成', 'progress': None, 'outputs': [], 'created_at': time.time(),
        'connection': {**{k: settings[k] for k in ('comfy_url', 'runninghub_url', 'workflow_id', 'instance_type','native_comfy')}, 'output_nodes': compiled.get('output_nodes', [])}})
    launch(run['id'])
    return public_run(run)


@app.get('/api/runs/{id}/latent/{filename}')
def download_latent(id:str, filename:str):
    run=require('runs',id)
    entry=next((x for x in run.get('latents',[]) if x['filename']==filename),None)
    if not entry: raise HTTPException(404,'找不到 latent。')
    return FileResponse(db.DATA/'latents'/entry['filename'],filename=entry['name'],media_type='application/octet-stream')


@app.post('/api/runs/{id}/usage')
async def refresh_usage(id: str):
    run = require('runs', id)
    if run['spec']['provider'] != 'runninghub' or not run.get('remote_id'):
        raise ValueError('此任務沒有 RunningHub 用量可查詢。')
    engine = provider('runninghub', {**db.settings(), **run.get('connection', {})})
    try:
        result = await engine.query(run['remote_id'])
        return public_run(update_run(id, usage=result.get('usage'), task_usage_list=result.get('task_usage_list', [])))
    finally:
        await engine.close()


@app.get('/api/runs')
def runs(project_id: str):
    return [public_run(r) for r in db.all_records('runs') if r['project_id'] == project_id]


@app.post('/api/runs/{id}/resume')
async def resume(id: str):
    run = require('runs', id)
    if not run.get('remote_id'):
        raise ValueError('沒有遠端任務 ID，請到服務端確認。')
    if run['status'] == 'success':
        return public_run(run)
    update_run(id, status='reconnecting', error=None, stage='恢復查詢遠端結果')
    launch(id)
    return public_run(require('runs', id))


from . import automation
automation.install(app, globals())

app.mount('/media', StaticFiles(directory=db.MEDIA), name='media')
if (ROOT / 'dist').exists():
    app.mount('/', StaticFiles(directory=ROOT / 'dist', html=True), name='frontend')
