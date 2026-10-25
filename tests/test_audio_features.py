import asyncio
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from backend import main, storage, prompting
from backend.audio_workflows import AudioGeneration, REGISTRY, compile_audio, resolve_text
from backend.providers import RunningHub
from backend.workflow import ROOT

@pytest.mark.parametrize('name',list(REGISTRY))
def test_only_declared_audio_inputs_change(name):
    entry=REGISTRY[name]
    values={f['key']:('new text' if f['type']=='text' else f.get('default')) for f in entry['fields'] if f['type']!='audio'}
    uses_audio=any(f['type']=='audio' for f in entry['fields'])
    spec=AudioGeneration(workflow=name,values=values,audio_asset_id='a' if uses_audio else None)
    assets={'a':{'id':'a','kind':'audio','filename':'local.wav','name':'voice'}}
    result=compile_audio(spec,assets,{'a':'remote.wav'})['workflow']
    original=json.loads((ROOT/'workflows'/f'{name}.json').read_text(encoding='utf-8-sig'))
    allowed={(f['node'],f['field']) for f in entry['fields']}
    assert result.keys()==original.keys()
    for node,body in original.items():
        assert body['class_type']==result[node]['class_type']
        for field,value in body['inputs'].items():
            if (node,field) not in allowed: assert result[node]['inputs'][field]==value
    if uses_audio:
        f=next(f for f in entry['fields'] if f['type']=='audio')
        assert result[f['node']]['inputs'][f['field']]=='remote.wav'

def test_text_snapshot_and_language_validation():
    spec=AudioGeneration(workflow='qwen_clone',values={'text':'fallback','ref_text':'','language':'Chinese'},audio_asset_id='a',text_sources={'text':'n'})
    resolved=resolve_text(spec,{'nodes':[{'id':'n','data':{'kind':'text','text':'linked words'}}]})
    assert resolved.values['text']=='linked words' and not resolved.text_sources
    asset={'a':{'id':'a','kind':'audio','filename':'a.wav','name':'voice'}}
    graph=compile_audio(resolved,asset)['workflow']
    assert graph['40']['inputs']['target_text']=='linked words'
    assert graph['40']['inputs']['ref_text']==''
    with pytest.raises(ValueError):compile_audio(resolved.model_copy(update={'values':{**resolved.values,'language':'invalid'}}),asset)

def test_audio_rh_has_no_h3_seed_override():
    def respond(request):
        payload=json.loads(request.content)
        assert payload['workflowId']=='test-workflow'
        assert payload['nodeInfoList']==[]
        return httpx.Response(200,json={'code':0,'data':{'taskId':'test-task'}})
    async def run():
        engine=RunningHub({**storage.DEFAULT_SETTINGS,'workflow_id':'test-workflow','runninghub_key':'test-key'})
        await engine.close()
        engine.client=httpx.AsyncClient(base_url='https://www.runninghub.cn',transport=httpx.MockTransport(respond))
        assert await engine.submit({'38':{}},'id',123)=='test-task'
        await engine.close()
    asyncio.run(run())

def test_audio_run_routing_defaults_and_preferences(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DATA',tmp_path)
    monkeypatch.setattr(storage,'MEDIA',tmp_path/'media');storage.MEDIA.mkdir()
    monkeypatch.setattr(main,'launch',lambda _:None)
    with TestClient(main.app) as client:
        client.put('/api/settings',json={'runninghub_key':'key','workflow_id':'video-only','audio_workflow_ids':{'yue_text':'12345'},'video_defaults':{'duration':9,'steps':12}})
        conf=client.get('/api/config').json()
        assert conf['video_defaults']['duration']==9 and conf['video_defaults']['steps']==12
        assert len(conf['audio_workflows'])==5
        project=client.post('/api/projects',json={'nodes':[{'id':'text','data':{'kind':'text','text':'bright pop'}}]}).json()
        response=client.post('/api/runs',json={'project_id':project['id'],'node_id':'audio','request_id':'audio-test-1','spec':{'kind':'audio','provider':'runninghub','workflow':'yue_text','values':{'lyrics':'hello'},'text_sources':{'style':'text'}}})
        assert response.status_code==200,response.text
        run=storage.get('runs','audio-test-1')
        assert run['connection']['workflow_id']=='12345'
        assert run['compiled']['workflow']['54']['inputs']['value']=='bright pop'
        assert run['spec']['text_sources']=={}
        client.put('/api/prompt-assistant/model-preference',json={'provider':'api','model':'chosen-model'})
        assert client.get('/api/prompt-assistant/settings').json()['model']=='chosen-model'
        storage.put('prompt_jobs','stream-test',{'status':'success','partial':'part','result':'finished'})
        stream=client.get('/api/prompt-assistant/drafts/stream-test/stream')
        assert 'text/event-stream' in stream.headers['content-type']
        assert 'finished' in stream.text

def test_live_prompt_stream_keeps_partial_before_completion(tmp_path,monkeypatch):
    from backend import chatgpt_auth
    monkeypatch.setattr(storage,'DATA',tmp_path)
    monkeypatch.setattr(storage,'MEDIA',tmp_path/'media');storage.MEDIA.mkdir()
    monkeypatch.setattr(chatgpt_auth,'vault',lambda:{'active':'test-account'})
    async def fake_draft(prompt,attachments,model,account,on_delta):
        on_delta('hello')
        await asyncio.sleep(.5)
        on_delta(' world')
        return 'hello world',None
    monkeypatch.setattr(chatgpt_auth,'draft',fake_draft)
    with TestClient(main.app) as client:
        config=client.get('/api/prompt-assistant/settings').json()
        config.update(provider='chatgpt',model='test-model')
        client.put('/api/prompt-assistant/settings',json=config)
        project=client.post('/api/projects',json={'nodes':[{'id':'n','data':{'kind':'generation'}}]}).json()
        response=client.post('/api/prompt-assistant/drafts',json={'request_id':'live-stream-test','project_id':project['id'],'node_id':'n','template_id':'characters','requirement':'test','spec':{'prompt':'test'}})
        assert response.status_code==200,response.text
        stream=client.get('/api/prompt-assistant/drafts/live-stream-test/stream').text
        events=[json.loads(line[6:]) for line in stream.splitlines() if line.startswith('data: ')]
        assert any(e['status']=='running' and e['partial']=='hello' for e in events)
        assert events[-1]['status']=='success' and events[-1]['result']=='hello world'
