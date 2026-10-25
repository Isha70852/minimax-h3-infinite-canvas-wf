import asyncio
import json
import pytest
from backend import main, prompting, storage
from backend.image_workflows import ImageGeneration, REGISTRY, compile_image, resolve_text
from backend.workflow import ROOT, Generation

ASSETS={'a':{'id':'a','filename':'local.png','name':'input','kind':'image'},'b':{'id':'b','filename':'second.png','name':'second','kind':'image'}}

@pytest.mark.parametrize('key',list(REGISTRY))
def test_image_templates_preserve_unexposed_values_and_bypass_lora(key):
    entry=REGISTRY[key]
    spec=ImageGeneration(workflow=key,values={'prompt':'new prompt'},image_assets={'image':'a'} if key=='flux_klein' else {})
    result=compile_image(spec,ASSETS,{'a':'uploaded.png'},123)['workflow']
    original=json.loads((ROOT/'workflows'/entry['template']).read_text(encoding='utf-8-sig'))
    allowed={(f['node'],f['input']) for f in entry['fields']}|{(entry['sampler'],'seed')}
    if key=='flux_klein':allowed|={('139','clip_name'),('158','positive'),('158','negative')}
    if 'lora' in entry:
        placeholder=entry['lora']['placeholder']
        assert placeholder not in result
        allowed|={(id,k) for id,n in original.items() for k,v in n['inputs'].items() if v==[placeholder,0]}
    for id,node in result.items():
        for field,value in node['inputs'].items():
            if (id,field) not in allowed:assert value==original[id]['inputs'][field],(key,id,field)
    assert result[entry['sampler']]['inputs']['seed']==123
    assert not any(n['class_type']=='LoraLoaderModelOnly' for n in result.values())

def test_flux_optional_second_image_clip_pair_and_size():
    spec=ImageGeneration(workflow='flux_klein',values={'prompt':'edit','model':'flux-2-klein-9b-fp8.safetensors','keep_size':False,'width':768,'height':512},image_assets={'image':'a'})
    one=compile_image(spec,ASSETS)['workflow']
    assert all(id not in one for id in ('159','160','161','163','164'))
    assert one['158']['inputs']['positive']==['156',0]
    assert one['139']['inputs']['clip_name']=='qwen_3_8b_fp8mixed.safetensors'
    assert one['165']['inputs']['switch'] is False and one['166']['inputs']['width']==768
    two=compile_image(spec.model_copy(update={'image_assets':{'image':'a','image2':'b'}}),ASSETS,{'b':'uploaded2.png'})['workflow']
    assert two['159']['inputs']['image']=='uploaded2.png' and two['158']['inputs']['positive']==['163',0]

def test_lora_chain_and_bound_text_snapshot():
    spec=ImageGeneration(workflow='moss',text_sources={'prompt':'t'},loras=[{'name':'first.safetensors','strength':.4},{'name':'','strength':1},{'name':'off','enabled':False},{'name':'last.safetensors','strength':.8}])
    resolved=resolve_text(spec,{'nodes':[{'id':'t','data':{'kind':'text','text':'linked prompt'}}]})
    graph=compile_image(resolved,{})['workflow']
    loras=[(id,n) for id,n in graph.items() if n['class_type']=='LoraLoaderModelOnly']
    assert len(loras)==2 and loras[1][1]['inputs']['model']==[loras[0][0],0]
    assert graph['2']['inputs']['model']==[loras[1][0],0] and graph['5']['inputs']['text']=='linked prompt'
    with pytest.raises(ValueError):compile_image(resolved.model_copy(update={'values':{'prompt':'x','width':1001}}),{})
    assert isinstance(main.RunRequest(project_id='p',node_id='n',request_id='test-img1',spec=resolved.model_dump()).spec,ImageGeneration)

def test_text_draft_uses_shared_template_without_h3_output_validation(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DATA',tmp_path)
    storage.put('projects','p',{'nodes':[{'id':'n','data':{'kind':'text','text':''}}]})
    config=prompting.AssistantSettings(provider='chatgpt',model='test',default_template_id='plain',templates=[{'id':'plain','name':'Plain','content':'Write a short story.'}])
    prompting.save_settings(config)
    body=prompting.DraftRequest(project_id='p',node_id='n',request_id='text-draft-1',target_type='text',template_id='plain',requirement='hello',spec=Generation(prompt='existing text'))
    settings,template,refs=prompting.context(body)
    async def fake(*args):return 'Normal text, not six H3 sections.',None
    monkeypatch.setattr(prompting.chatgpt_auth,'draft',fake)
    storage.put('prompt_jobs',body.request_id,{'status':'running'})
    asyncio.run(prompting.execute(body.request_id,body,settings,template,refs))
    job=storage.get('prompt_jobs',body.request_id)
    assert job['status']=='success' and job['result']=='Normal text, not six H3 sections.' and not job['warnings']
    assert prompting.public_settings()['default_template_id']=='plain'
