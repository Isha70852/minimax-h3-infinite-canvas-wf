import asyncio
import io
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import main, storage
from backend.providers import ComfyUI, RunningHub
from backend.workflow import Generation, compile_workflow


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Never create or modify the user's actual projects/settings in tests.
    monkeypatch.setattr(storage, 'DATA', tmp_path)
    monkeypatch.setattr(storage, 'MEDIA', tmp_path / 'media')
    storage.MEDIA.mkdir()
    with TestClient(main.app) as client:
        yield client


def png():
    out = io.BytesIO()
    Image.new('RGB', (32, 24), '#73b5a2').save(out, 'PNG')
    return out.getvalue()


def test_project_roundtrip_and_upload(client):
    project = client.post('/api/projects', json={'name': '中文測試'}).json()
    body = {'name': '中文更新', 'nodes': [{'id': 'n', 'position': {'x': 13, 'y': -77}, 'data': {'prompt': '金髮女性'}}], 'edges': [], 'viewport': {'x': -95, 'y': 25, 'zoom': .7}}
    assert client.put('/api/projects/' + project['id'], json=body).status_code == 200
    result = client.get('/api/projects/' + project['id']).json()
    for key in body:
        assert result[key] == body[key]
    upload = client.post('/api/assets', files={'file': ('測試.png', png(), 'image/png')})
    assert upload.status_code == 200
    asset = upload.json()
    assert asset['name'] == '測試.png' and (storage.MEDIA / asset['filename']).exists()
    spec = {'mode': 'Ref2VA', 'prompt': '@圖片1', 'references': [{'asset_id': asset['id']}]}
    preview = client.post('/api/workflow/preview', json=spec)
    assert preview.status_code == 200 and preview.json()['prompt'] == '<Picture 1>'
    assert client.post('/api/assets', files={'file': ('no.txt', b'bad')}).status_code == 422


def test_settings_never_return_secret_and_block_cross_origin(client):
    response = client.put('/api/settings', json={'runninghub_key': 'test-secret'})
    assert response.status_code == 200
    assert response.json()['has_key']
    assert 'test-secret' not in client.get('/api/settings').text
    client.put('/api/settings', json={'comfy_url': 'http://localhost:8188'})
    assert storage.settings()['runninghub_key'] == 'test-secret'
    assert client.post('/api/projects', json={}, headers={'Origin': 'https://unrelated.example'}).status_code == 403


def test_runninghub_requires_workflow_id_before_creating_run(client):
    client.put('/api/settings', json={'runninghub_key': 'test-secret'})
    project = client.post('/api/projects', json={'name': 'validation'}).json()
    result = client.post('/api/runs', json={'project_id': project['id'], 'node_id': 'n',
        'request_id': 'missing-workflow-id', 'spec': {'provider': 'runninghub', 'prompt': 'A quiet room'}})
    assert result.status_code == 422
    assert '工作流 ID' in result.json()['detail']
    assert storage.all_records('runs') == []


def test_project_library_isolation_and_shared_import(client):
    a = client.post('/api/projects', json={'name': 'A'}).json()['id']
    b = client.post('/api/projects', json={'name': 'B'}).json()['id']
    shared = client.post('/api/assets', files={'file': ('shared.png', png(), 'image/png')}).json()
    private = client.post('/api/assets', params={'scope': 'project', 'project_id': a}, files={'file': ('private.png', png(), 'image/png')}).json()
    assert [x['id'] for x in client.get('/api/assets').json()] == [shared['id']]
    assert client.get('/api/assets', params={'project_id': b}).json() == []
    result = client.post('/api/runs', json={'project_id': b, 'node_id': 'n', 'request_id': 'cross-project-denied', 'spec': {'mode': 'Ref2VA', 'prompt': '@圖片1', 'references': [{'asset_id': private['id']}]}})
    assert result.status_code == 422
    imported = client.post(f'/api/projects/{b}/import/{shared["id"]}').json()
    assert imported['id'] != shared['id'] and imported['filename'] == shared['filename']
    client.patch('/api/assets/' + imported['id'], json={'name': 'new name', 'favorite': True, 'deleted': True})
    original = next(x for x in client.get('/api/assets').json() if x['id'] == shared['id'])
    assert original['name'] == 'shared.png' and not original.get('deleted')
    assert (storage.MEDIA / original['filename']).exists()
    restored = client.patch('/api/assets/' + imported['id'], json={'deleted': False}).json()
    assert restored['name'] == 'new name' and restored['favorite'] and not restored['deleted']


def test_legacy_library_migration_preserves_membership(client):
    from backend import library
    p = client.post('/api/projects', json={'nodes': [{'id': 'n', 'data': {'asset_id': 'legacy'}}]}).json()
    storage.put('assets', 'legacy', {'name': 'old.png', 'filename': 'old.png', 'kind': 'image'})
    with storage.connection() as conn:
        conn.execute('DELETE FROM records WHERE kind=? AND id=?', ('migrations', 'library-v1'))
    library.migrate()
    assert library.belongs(storage.get('assets', 'legacy'), p['id'])
    assert (storage.DATA / 'before-library-v1.sqlite').exists()


def test_project_delete_restore_and_aliases(client):
    project = client.post('/api/projects', json={'name': 'remove me'}).json()
    assert client.delete('/api/projects/' + project['id']).status_code == 200
    assert client.get('/api/projects').json() == []
    assert client.get('/api/projects?deleted=true').json()[0]['id'] == project['id']
    assert client.put('/api/projects/' + project['id'], json={'name': 'stale save'}).status_code == 409
    assert client.post('/api/projects/' + project['id'] + '/restore').status_code == 200
    assert client.get('/api/projects').json()[0]['name'] == 'remove me'
    client.put('/api/settings', json={'models': [{'name': 'my-model.safetensors', 'shift_enabled': True}], 'loras': ['my-lora.safetensors'], 'runninghub_key':'secret'})
    conf = client.get('/api/config').json()
    assert conf['models'] == ['my-model.safetensors']
    assert conf['model_profiles'][0]['shift_enabled']
    assert client.put('/api/settings', json={'clear_runninghub_key':True}).json()['has_key'] is False


def test_prompt_settings_deletion(client):
    config = client.get('/api/prompt-assistant/settings').json()
    assert '【人物空間關係與鏡頭軸線】' in config['templates'][0]['content']
    config.update(api_key='private-llm-key', provider='api')
    assert 'private-llm-key' not in client.put('/api/prompt-assistant/settings', json=config).text
    config.update(clear_api_key=True)
    assert client.put('/api/prompt-assistant/settings', json=config).json()['has_key'] is False
    for state in ['success', 'failed', 'running']:
        storage.put('prompt_jobs', state, {'project_id':'p','node_id':'n','status':state,'result':'draft'})
    assert client.delete('/api/prompt-assistant/drafts/running').status_code == 409
    assert client.delete('/api/prompt-assistant/drafts/success').status_code == 200
    assert client.delete('/api/prompt-assistant/drafts/failed').status_code == 200
    assert [j['id'] for j in client.get('/api/prompt-assistant/drafts?project_id=p&node_id=n').json()] == ['running']
    assert client.post('/api/prompt-assistant/handoff', json={}).status_code in (404,405)


def test_explicit_provider_rejection_is_not_uncertain(client, monkeypatch):
    from backend.providers import ProviderRejected
    class Rejected:
        async def preflight(self, graph): pass
        async def submit(self, *args): raise ProviderRejected('RunningHub 301: must not be null')
        async def close(self): pass
    monkeypatch.setattr(main, 'provider', lambda *args: Rejected())
    project = client.post('/api/projects', json={'name': 'rejection'}).json()
    result = client.post('/api/runs', json={'project_id': project['id'], 'node_id': 'n',
        'request_id': 'explicit-rejection', 'spec': {'prompt': 'A quiet room'}})
    for _ in range(50):
        record = storage.get('runs', 'explicit-rejection')
        if record['status'] == 'failed': break
        time.sleep(.01)
    assert record['status'] == 'failed'
    assert record.get('remote_id') is None


def test_complete_generation_history_and_idempotency(client, monkeypatch):
    submitted = []
    class FakeProvider:
        async def preflight(self, graph): pass
        async def upload(self, asset): return asset['filename']
        async def submit(self, graph, client_id, seed):
            submitted.append(graph)
            return 'remote-' + client_id
        async def watch(self, *args): pass
        async def query(self, id): return {'status': 'success', 'outputs': [{'url': 'https://output.test/frame.png', 'filename': 'frame.png'}]}
        async def close(self): pass
    monkeypatch.setattr(main, 'provider', lambda *args: FakeProvider())
    original_client = httpx.AsyncClient
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kwargs: original_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=png())), **kwargs))
    project = client.post('/api/projects', json={}).json()
    def run(request_id, prompt):
        request = {'request_id': request_id, 'project_id': project['id'], 'node_id': 'node-1', 'spec': {'prompt': prompt}}
        response = client.post('/api/runs', json=request)
        assert response.status_code == 200
        for _ in range(100):
            result = next(r for r in client.get('/api/runs', params={'project_id': project['id']}).json() if r['id'] == request_id)
            if result['status'] not in main.ACTIVE: break
            time.sleep(.01)
        assert result['status'] == 'success', result
        assert (storage.MEDIA / result['outputs'][0]['filename']).exists()
        assert 'connection' not in result
        # Repeated requests return the same job instead of charging twice.
        assert client.post('/api/runs', json=request).json()['id'] == request_id
        return result
    first = run('request-0001', 'first prompt')
    second = run('request-0002', 'second prompt')
    history = client.get('/api/runs', params={'project_id': project['id']}).json()
    assert len(submitted) == len(history) == 2
    assert first['compiled']['prompt'] == 'first prompt'
    assert second['compiled']['prompt'] == 'second prompt'
    assert first['seed'] != second['seed']


def test_submit_timeout_is_not_retried(client, monkeypatch):
    attempts = []
    class UncertainProvider:
        async def preflight(self, graph): pass
        async def submit(self, *args):
            attempts.append(1)
            raise httpx.ReadTimeout('timeout')
        async def close(self): pass
    monkeypatch.setattr(main, 'provider', lambda *args: UncertainProvider())
    p = client.post('/api/projects', json={}).json()
    request = {'request_id': 'uncertain-1', 'project_id': p['id'], 'node_id': 'node-1', 'spec': {'prompt': 'test'}}
    client.post('/api/runs', json=request)
    for _ in range(100):
        result = client.get('/api/runs', params={'project_id': p['id']}).json()[0]
        if result['status'] == 'attention': break
        time.sleep(.01)
    assert result['status'] == 'attention'
    assert len(attempts) == 1
    assert client.post('/api/runs/uncertain-1/resume').status_code == 422


def test_runninghub_protocol():
    calls = []
    def handler(request):
        import json
        calls.append(request)
        assert request.headers['Authorization'] == 'Bearer key'
        if request.url.path == '/task/openapi/create':
            payload = json.loads(request.content)
            assert isinstance(payload['workflow'], str)
            assert payload['nodeInfoList'][0]['fieldValue'] == '123'
            assert payload['instanceType'] == 'default'
            assert payload['workflowId'] == '1234567890123456789'
            return httpx.Response(200, json={'code': 0, 'data': {'taskId': 'task123', 'promptTips': '{"node_errors":{}}'}})
        return httpx.Response(200, json={'status': 'SUCCESS', 'usage': {'consumeCoins': '63', 'taskCostTime': '311'}, 'results': [{'url': 'https://example.test/video.mp4', 'outputType': 'mp4'}]})
    async def run():
        engine = RunningHub({**storage.DEFAULT_SETTINGS, 'runninghub_key': 'key', 'workflow_id': '1234567890123456789'})
        await engine.client.aclose()
        engine.client = httpx.AsyncClient(base_url='https://www.runninghub.cn', headers={'Authorization': 'Bearer key'}, transport=httpx.MockTransport(handler))
        task_id = await engine.submit({'129': {'inputs': {'noise_seed': 123}}}, 'client', 123)
        assert task_id == 'task123'
        result = await engine.query(task_id)
        assert result['outputs'][0]['filename'] == 'result.mp4'
        assert result['usage'] == {'consumeCoins': '63', 'taskCostTime': '311'}
        await engine.close()
    asyncio.run(run())
    assert [r.url.path for r in calls] == ['/task/openapi/create', '/openapi/v2/query']


def test_comfy_missing_nodes_and_history():
    def handler(request):
        if request.url.path == '/object_info':
            return httpx.Response(200, json={})
        return httpx.Response(200, json={'p': {'status': {'completed': True}, 'outputs': {'174': {'gifs': [{'filename': 'test.mp4', 'subfolder': 'H3', 'type': 'output'}]}}}})
    async def run():
        engine = ComfyUI(storage.DEFAULT_SETTINGS)
        await engine.client.aclose()
        engine.client = httpx.AsyncClient(base_url='http://localhost:8188', transport=httpx.MockTransport(handler))
        with pytest.raises(ValueError, match='缺少節點'):
            await engine.preflight(compile_workflow(Generation(prompt='test'), {})['workflow'])
        result = await engine.query('p')
        assert result['status'] == 'success'
        assert 'subfolder=H3' in result['outputs'][0]['url']
        await engine.close()
    asyncio.run(run())


def test_real_media_normalization(client, tmp_path):
    import subprocess
    import imageio_ffmpeg
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video = tmp_path / 'source.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'color=c=teal:s=128x96:r=30', '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '3', '-c:v', 'libx264', '-c:a', 'aac', '-pix_fmt', 'yuv420p', str(video)], check=True, capture_output=True)
    result = client.post('/api/assets', files={'file': ('clip.mp4', video.read_bytes(), 'video/mp4')})
    assert result.status_code == 200, result.text
    asset = result.json()
    probe = subprocess.run([ffmpeg, '-hide_banner', '-i', str(storage.MEDIA / asset['filename'])], capture_output=True)
    metadata = probe.stderr.decode('utf-8', errors='replace')
    assert '24 fps' in metadata and 'Audio:' in metadata
    decoded = subprocess.run([ffmpeg, '-v', 'error', '-i', str(storage.MEDIA / asset['filename']), '-f', 'null', '-'], capture_output=True)
    assert decoded.returncode == 0
    import wave
    audio = io.BytesIO()
    with wave.open(audio, 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(22050); wav.writeframes(b'\0\0' * 22050)
    uploaded = client.post('/api/assets', files={'file': ('audio.wav', audio.getvalue(), 'audio/wav')})
    assert uploaded.status_code == 200
    assert uploaded.json()['kind'] == 'audio'
    invalid = client.post('/api/assets', files={'file': ('fake.png', b'not an image', 'image/png')})
    assert invalid.status_code == 422
