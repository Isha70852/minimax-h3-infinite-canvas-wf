import pytest
from backend import prompting,storage
from backend.workflow import Generation

@pytest.fixture
def project(tmp_path,monkeypatch):
    monkeypatch.setattr(storage,'DATA',tmp_path)
    storage.put('projects','p',{'nodes':[{'id':'n','data':{'kind':'text'}}]})
    return tmp_path

def request(**values):
    return prompting.DraftRequest(project_id='p',node_id='n',target_type='text',request_id='context-test',requirement='new scene',spec=Generation(prompt='existing'),**values)

def old(id,**values):
    return storage.put('prompt_jobs',id,{'project_id':'p','node_id':'n','status':'success','requirement':'old scene '+id,'result':'old output '+id,'template':{'id':'old','name':'old','content':'prior template'},'spec':Generation(prompt='prior').model_dump(),**values})

def test_blank_and_one_off_templates(project):
    assert prompting.context(request(template_mode='none'))[1]['content']==''
    assert prompting.context(request(template_mode='custom',custom_template='only this time'))[1]['content']=='only this time'
    assert all(t['content']!='only this time' for t in prompting.settings()['templates'])

def test_flat_context_deduplicates_ancestors_and_preserves_inputs(project):
    a=old('a');old('b',conversation_turns=[a],material_notes='two characters')
    body=request(template_mode='inherit',history_ids=['a','b']);_,template,refs=prompting.context(body)
    assert [t['id'] for t in body._turns]==['a','b']
    prompt,_,_=prompting.build_input(body,template,refs,project/'input')
    assert prompt.count('old output a')==1 and 'two characters' in prompt
    assert 'NOT a requirement for seamless continuation' in prompt
    assert template['content']=='prior template'

def test_context_rejects_foreign_project_and_deleted_history(project):
    old('foreign',project_id='other')
    with pytest.raises(ValueError):prompting.context(request(history_ids=['foreign']))
    old('deleted',deleted=True)
    with pytest.raises(ValueError):prompting.context(request(history_ids=['deleted']))

def test_text_empty_refs_is_allowed(project):
    body=request(template_mode='none');body.spec.mode='Ref2VA'
    assert prompting.context(body)[2]==[]
