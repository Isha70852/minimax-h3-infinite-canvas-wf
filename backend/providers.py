"""Provider adapters. Submission is deliberately never retried automatically."""
import asyncio
import json
from urllib.parse import urlencode, urlparse

import httpx
import websockets

from .storage import MEDIA

class ProviderRejected(ValueError):
    """The provider explicitly rejected the request, so submission is not uncertain."""


def checked(response):
    response.raise_for_status()
    return response.json()


def rh_checked(response):
    body = checked(response)
    if body.get('code', 0) != 0:
        raise ProviderRejected(f"RunningHub {body.get('code')}: {body.get('msg', 'API error')}")
    return body.get('data', body)


class ComfyUI:
    def __init__(self, settings):
        self.base = settings['comfy_url'].rstrip('/')
        self.output_nodes = settings.get('output_nodes', [])
        self.native_proxy = settings.get('native_comfy', False)
        self.settings = settings
        self.client = httpx.AsyncClient(base_url=self.base, timeout=120, trust_env=False)

    async def close(self):
        await self.client.aclose()

    async def upload(self, asset):
        with (MEDIA / asset['filename']).open('rb') as file:
            body = checked(await self.client.post('/upload/image', files={'image': (asset['filename'], file)}, data={'type': 'input', 'overwrite': 'false'}))
        return '/'.join(x for x in (body.get('subfolder'), body['name']) if x)

    async def upload_latent(self, path):
        # The H3 loader on RunningHub accepts output/ only. Use the standard
        # upload API's output type, with a unique filename, never a shared slot.
        with path.open('rb') as file:
            body = checked(await self.client.post('/upload/image', files={'image': (path.name, file, 'application/octet-stream')}, data={'type':'output','subfolder':'H3Canvas/imported','overwrite':'false'}))
        if 'name' not in body: raise ValueError('服務未回傳 latent 上傳檔名。')
        return '/'.join(x for x in (body.get('subfolder'),body['name']) if x)

    async def preflight(self, graph):
        info = checked(await self.client.get('/object_info'))
        missing = sorted({n['class_type'] for n in graph.values()} - info.keys())
        if missing:
            raise ValueError('ComfyUI 缺少節點：' + ', '.join(missing))
        # RH proxy lists only favourites for UNET/LoRA. Its submission validator
        # resolves workflow model names; that list is not the full server catalog.
        if self.native_proxy: return
        # Server versions and model paths differ. Report mismatch before submitting.
        for node in graph.values():
            schema = info[node['class_type']].get('input', {})
            fields = {**schema.get('required', {}), **schema.get('optional', {})}
            for name in ('unet_name', 'lora_name', 'vae_name', 'clip_name', 'aspect_ratio'):
                value = node['inputs'].get(name)
                definition = fields.get(name)
                if value is not None and definition and isinstance(definition[0], list) and value not in definition[0]:
                    raise ValueError(f'ComfyUI {name} 找不到 {value}；請確認模型檔案及節點版本。')

    async def submit(self, graph, client_id, seed):
        body = checked(await self.client.post('/prompt', json={'prompt': graph, 'client_id': client_id}))
        if body.get('error') or body.get('node_errors'):
            raise ValueError(json.dumps(body, ensure_ascii=False))
        return str(body['prompt_id'])

    async def watch(self, client_id, task_id, update):
        url = self.base.replace('http://', 'ws://', 1).replace('https://', 'wss://', 1) + '/ws?' + urlencode({'clientId': client_id})
        try:
            async with websockets.connect(url, max_size=4 * 1024 * 1024, proxy=None) as ws:
                async for raw in ws:
                    if not isinstance(raw, str):
                        continue
                    event = json.loads(raw)
                    data = event.get('data', {})
                    if data.get('prompt_id') not in (None, task_id):
                        continue
                    if event['type'] == 'progress' and data.get('max'):
                        update(status='running', progress=round(data['value'] / data['max'] * 100), stage='取樣進度')
                    elif event['type'] == 'executing' and data.get('node'):
                        update(status='running', progress=None, stage='執行節點 ' + str(data['node']))
        except (OSError, websockets.WebSocketException):
            pass  # HTTP history remains the source of truth.

    async def query(self, task_id):
        history = checked(await self.client.get('/history/' + task_id)).get(task_id)
        if not history:
            return {'status': 'pending'}
        status = history.get('status', {})
        if status.get('status_str') == 'error':
            raise ValueError(json.dumps(status.get('messages', []), ensure_ascii=False))
        if not status.get('completed') and status.get('status_str') != 'success':
            return {'status': 'pending'}
        outputs, latents = [], []
        for node_id, node in history.get('outputs', {}).items():
            if self.output_nodes and node_id not in self.output_nodes: continue
            for key in ('gifs', 'videos', 'images', 'audio', 'latents'):
                for item in node.get(key, []):
                    if item.get('filename'):
                        (latents if key=='latents' else outputs).append({'url': self.base + '/view?' + urlencode({k: item[k] for k in ('filename', 'subfolder', 'type') if k in item}), 'filename': item['filename']})
        result = {'status': 'success', 'outputs': outputs, 'latents':latents}
        if self.native_proxy:
            # RH history omits `completed` and returns only published file types.
            # v2 carries billing and durable result URLs, unlike Comfy history.
            rh = RunningHub(self.settings)
            try:
                published = await rh.query(task_id)
                if published.get('status') == 'success':
                    result.update(published)
            finally:
                await rh.close()
        return result


class RunningHub:
    def __init__(self, settings):
        if not settings.get('runninghub_key'):
            raise ValueError('請先在連線設定輸入 RunningHub API Key。')
        self.settings = settings
        self.key = settings['runninghub_key']
        self.client = httpx.AsyncClient(base_url=settings['runninghub_url'].rstrip('/'), headers={'Authorization': 'Bearer ' + self.key}, timeout=120)

    async def close(self):
        await self.client.aclose()

    async def preflight(self, graph):
        if not str(self.settings.get('workflow_id', '')).strip():
            raise ValueError('請先填入 RunningHub 工作流 ID（必填），可從工作流網址取得。')

    async def upload(self, asset):
        with (MEDIA / asset['filename']).open('rb') as file:
            body = rh_checked(await self.client.post('/task/openapi/upload', data={'apiKey': self.key, 'fileType': 'input'}, files={'file': (asset['filename'], file)}))
        return body['fileName']

    async def upload_latent(self, path):
        proxy = provider('runninghub', {**self.settings, 'native_comfy': True})
        try:
            return await proxy.upload_latent(path)
        finally:
            await proxy.close()

    async def submit(self, graph, client_id, seed):
        await self.preflight(graph)
        payload = {'apiKey': self.key, 'workflow': json.dumps(graph, ensure_ascii=False),
                   'nodeInfoList': [{'nodeId': '129', 'fieldName': 'noise_seed', 'fieldValue': str(seed)}] if 'noise_seed' in graph.get('129', {}).get('inputs', {}) else [],
                   'instanceType': self.settings['instance_type']}
        payload['workflowId'] = str(self.settings['workflow_id']).strip()
        body = rh_checked(await self.client.post('/task/openapi/create', json=payload))
        tips = body.get('promptTips')
        if tips:
            tips = json.loads(tips) if isinstance(tips, str) else tips
            if tips.get('node_errors') or tips.get('error'):
                raise ValueError(json.dumps(tips, ensure_ascii=False))
        if body.get('taskStatus') == 'FAILED':
            raise ValueError('RunningHub 任務提交失敗。')
        return str(body['taskId'])

    async def query(self, task_id):
        body = rh_checked(await self.client.post('/openapi/v2/query', json={'taskId': task_id}))
        status = body.get('status', '')
        if status == 'SUCCESS':
            media, latents = [], []
            for r in body.get('results', []):
                if not r.get('url') or (self.settings.get('output_nodes') and str(r.get('nodeId')) not in self.settings['output_nodes']): continue
                ext = str(r.get('outputType') or '').lower().lstrip('.')
                item = {'url':r['url'], 'filename':'result.'+ext}
                (latents if ext in ('zip','safetensors','latent') else media).append(item)
            return {'status': 'success', 'usage': body.get('usage'), 'task_usage_list': body.get('taskUsageList', []), 'outputs':media, 'latents':latents}
        if status in ('FAILED', 'FAILURE', 'CANCELED'):
            raise ValueError(body.get('errorMessage') or body.get('failedReason') or 'RunningHub 生成失敗')
        if body.get('errorCode'):
            raise ValueError(f"RunningHub {body['errorCode']}: {body.get('errorMessage', '')}")
        return {'status': 'running' if status == 'RUNNING' else 'queued'}


def provider(name, settings):
    if name == 'runninghub' and settings.get('native_comfy'):
        if not settings.get('runninghub_key'): raise ValueError('請先設定 RunningHub API Key。')
        if settings.get('instance_type') == 'ultra': raise ValueError('官方原生代理僅列出 Standard / Plus；導演台請選這兩種機型。')
        route = 'proxy-plus' if settings.get('instance_type')=='plus' else 'proxy'
        return ComfyUI({**settings,'comfy_url':'https://www.runninghub.ai/'+route+'/'+settings['runninghub_key']})
    adapters = {'comfyui': ComfyUI, 'runninghub': RunningHub}
    if name not in adapters:
        raise ValueError('不支援的運算服務：' + name)
    return adapters[name](settings)
