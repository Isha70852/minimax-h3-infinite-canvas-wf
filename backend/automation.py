"""Opt-in, versioned automation facade; reuses the application's validated services."""
import hashlib
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from . import storage as db, prompting, node_templates, directors, custom_workflows

class AutomationRun(BaseModel):
    project_id: str
    node_id: str
    request_id: str
    spec: dict
    template_id: str | None = None
    template_tag: str | None = None
    use_default_template: bool = True

management = APIRouter(prefix='/api/automation', tags=['Automation settings'])


def state():
    return db.get('automation_settings','default') or {}


@management.get('/settings')
def settings():
    s=state()
    return {'enabled':bool(s.get('enabled')), 'has_token':bool(s.get('token_hash')), 'base_url':'http://127.0.0.1:8766/api/automation/v1'}


class AccessSettings(BaseModel):
    enabled: bool
    rotate_token: bool = False


@management.put('/settings')
def configure(body: AccessSettings):
    s=state(); token=None
    if body.rotate_token or (body.enabled and not s.get('token_hash')):
        token=secrets.token_urlsafe(32)
        s['token_hash']=hashlib.sha256(token.encode()).hexdigest()
    db.put('automation_settings','default',{**s,'enabled':body.enabled})
    return {**settings(), 'token':token}


def authorize(authorization: str | None = Header(default=None)):
    s=state()
    if not s.get('enabled'): raise HTTPException(403,'外部操作 API 尚未開啟。')
    token=(authorization or '').removeprefix('Bearer ')
    if not authorization or not authorization.startswith('Bearer ') or not s.get('token_hash') or not secrets.compare_digest(hashlib.sha256(token.encode()).hexdigest(),s['token_hash']):
        raise HTTPException(401,'需要有效的 Bearer token。',headers={'WWW-Authenticate':'Bearer'})


def install(app, services):
    router=APIRouter(prefix='/api/automation/v1', dependencies=[Depends(authorize)], tags=['Automation v1'])
    # Explicit allowlist. Never expose settings, credentials, arbitrary URLs or deletion.
    aliases=[('/projects','GET','projects'),('/projects','POST','new_project'),('/projects/{id}','GET','get_project'),
             ('/assets','GET','assets'),('/assets','POST','upload'),('/projects/{project_id}/import/{asset_id}','POST','import_asset'),
             ('/runs/{id}/cancel','POST','cancel_run'),('/workflow/preview','POST','preview'),('/runs','GET','runs')]
    for path,method,name in aliases:
        router.add_api_route(path,services[name],methods=[method],name='automation_'+name)
    router.add_api_route('/node-templates',node_templates.templates,methods=['GET'])
    router.add_api_route('/node-templates',node_templates.create_template,methods=['POST'])
    router.add_api_route('/node-templates/{id}',node_templates.save_template,methods=['PUT'])
    router.add_api_route('/node-templates/{id}',node_templates.delete_template,methods=['DELETE'])

    def workflow_index(cfg):
        # One explicit map of every built-in generator, so agents need not guess which config key holds it.
        def rows(items,node_kind,spec_key,schema,extra=lambda w:{}):
            return [{'workflow':w['id'],'name':w['name'],'node_kind':node_kind,'node_spec_key':spec_key,'request_schema':schema,
                     'fields':[f['key'] for f in w.get('fields',[])],**extra(w)} for w in items]
        audio=lambda kind:[w for w in cfg['audio_workflows'] if w.get('category')==kind]
        return {
            'note':'Built-in workflows. custom_workflows lists only user-imported packages; empty node_templates only means no saved presets.',
            'video':[{'workflow':'unified','name':'MiniMax H3 video (T2VA/I2VA/L2VA/FL2VA/Ref2VA)','node_kind':'generation','node_spec_key':'spec','request_schema':'Generation'}],
            'image':rows(cfg['image_workflows'],'imagegen','image_spec','ImageGeneration',lambda w:{'supports_lora':w.get('supports_lora',False),
                        'image_inputs':[f['key'] for f in w['fields'] if f.get('type')=='image']}),
            'motion':rows(cfg['motion_workflows'],'motiongen','motion_spec','MotionGeneration',lambda w:{'modes':next((f.get('options') for f in w['fields'] if f['key']=='mode'),None)}),
            'music':rows(audio('music'),'music','audio_spec','AudioGeneration'),
            'tts':rows(audio('tts'),'tts','audio_spec','AudioGeneration'),
            'custom':[{'package_id':p.get('package_id',p.get('id')),'version':p.get('version'),'name':p.get('name'),'node_kind':'custom','node_spec_key':'custom_spec','request_schema':'CustomGeneration'} for p in cfg['custom_workflows']],
        }

    @router.get('/workflows')
    def workflows():
        return workflow_index(services['config']())

    @router.get('/catalog')
    def catalog():
        cfg=services['config']()
        return {'version':1,'workflows':workflow_index(cfg),'config':cfg,'capabilities':services['capabilities'](),
                'schemas':{c.__name__:c.model_json_schema() for c in (services['Generation'],services['ImageGeneration'],services['AudioGeneration'],services['CustomGeneration'],services['MotionGeneration'],prompting.DraftRequest)},
                'node_templates':node_templates.templates(), 'prompt_templates':prompting.public_settings().get('templates',[])}

    @router.get('/schema')
    def schema():
        return get_openapi(title='H3 Canvas Automation',version='1',routes=router.routes)


    for route in custom_workflows.router.routes:
        router.add_api_route(route.path.replace('/api/custom-workflows','/custom-workflows',1),route.endpoint,methods=list(route.methods))

    # Require optimistic concurrency for full canvas updates to avoid overwriting edits.
    async def update_project(id: str, body: services['Project'], if_match: str | None = Header(default=None)):
        current=services['get_project'](id)
        if if_match != str(current['updated_at']): raise HTTPException(409,'專案已變更或缺少 If-Match；請重新讀取專案後合併修改。')
        return services['save_project'](id,body)
    router.add_api_route('/projects/{id}',update_project,methods=['PUT'])

    async def submit(body: AutomationRun):
        project=services['get_project'](body.project_id)
        node=next((n for n in project.get('nodes',[]) if n['id']==body.node_id),None)
        category={'generation':'video','imagegen':'image','music':'music','tts':'tts','custom':'custom','motiongen':'motion'}.get((node or {}).get('data',{}).get('kind'))
        if not category: raise HTTPException(422,'請先建立對應類型的生成節點。')
        if category=='custom':
            candidates=[p for p in custom_workflows.presets() if p['spec']['package_id']==body.spec.get('package_id')]
            selected=next((p for p in candidates if p['id']==body.template_id),None) if body.template_id else None
            if body.template_tag:
                tagged=[p for p in candidates if body.template_tag in p['tags']]
                if len(tagged)!=1:raise HTTPException(422,'模板標籤不唯一或不存在。')
                selected=tagged[0]
            if body.template_id and not selected:raise HTTPException(422,'自訂模板不存在。')
            if not selected and not body.template_id and not body.template_tag and body.use_default_template:selected=next((p for p in candidates if p['is_default']),None)
            if selected and body.spec.get('version') and selected['spec']['version']!=body.spec['version']:raise HTTPException(422,'模板版本與工作流版本不同，請明確選擇對應版本。')
            spec={**(selected['spec'] if selected else {}),**body.spec}
            spec['values']={**(selected['spec']['values'] if selected else {}),**body.spec.get('values',{})}
        else:spec=node_templates.resolve(category,body.spec,body.template_id,body.template_tag,body.use_default_template)
        body=services['RunRequest'].model_validate({**body.model_dump(),'spec':spec})
        expected=('custom',) if isinstance(body.spec,services['CustomGeneration']) else ('motiongen',) if isinstance(body.spec,services['MotionGeneration']) else ('imagegen',) if isinstance(body.spec,services['ImageGeneration']) else ('music','tts') if isinstance(body.spec,services['AudioGeneration']) else ('generation',)
        if not node or node.get('data',{}).get('kind') not in expected: raise HTTPException(422,'請先建立對應類型的生成節點。')
        old=db.get('runs',body.request_id)
        if old and (old['project_id']!=body.project_id or old['node_id']!=body.node_id): raise HTTPException(409,'request_id 已被其他任務使用。')
        result = await services['start_run'](body)
        if result['spec'].get('motion_context'):
            directors.attach(body.project_id,body.node_id,result['spec'])
        return result
    router.add_api_route('/runs',submit,methods=['POST'])

    @router.get('/runs/{id}')
    def run(id: str):
        return services['public_run'](services['require']('runs',id))

    router.add_api_route('/prompt-drafts',prompting.draft,methods=['POST'])
    router.add_api_route('/prompt-drafts',prompting.drafts,methods=['GET'])
    router.add_api_route('/context-options',prompting.context_options,methods=['GET'])
    app.include_router(management)
    app.include_router(router)
