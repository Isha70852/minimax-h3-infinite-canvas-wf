"""Opt-in, versioned automation facade; reuses the application's validated services."""
import hashlib
import secrets
from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from . import storage as db, prompting

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
             ('/workflow/preview','POST','preview'),('/runs','GET','runs')]
    for path,method,name in aliases:
        router.add_api_route(path,services[name],methods=[method],name='automation_'+name)

    @router.get('/catalog')
    def catalog():
        return {'version':1,'config':services['config'](),'capabilities':services['capabilities'](),
                'schemas':{c.__name__:c.model_json_schema() for c in (services['Generation'],services['ImageGeneration'],services['AudioGeneration'],prompting.DraftRequest)},
                'prompt_templates':prompting.public_settings().get('templates',[])}

    @router.get('/schema')
    def schema():
        return get_openapi(title='H3 Canvas Automation',version='1',routes=router.routes)

    # Require optimistic concurrency for full canvas updates to avoid overwriting edits.
    async def update_project(id: str, body: services['Project'], if_match: str | None = Header(default=None)):
        current=services['get_project'](id)
        if if_match != str(current['updated_at']): raise HTTPException(409,'專案已變更或缺少 If-Match；請重新讀取專案後合併修改。')
        return services['save_project'](id,body)
    router.add_api_route('/projects/{id}',update_project,methods=['PUT'])

    async def submit(body: services['RunRequest']):
        project=services['get_project'](body.project_id)
        node=next((n for n in project.get('nodes',[]) if n['id']==body.node_id),None)
        expected=('imagegen',) if isinstance(body.spec,services['ImageGeneration']) else ('music','tts') if isinstance(body.spec,services['AudioGeneration']) else ('generation',)
        if not node or node.get('data',{}).get('kind') not in expected: raise HTTPException(422,'請先建立對應類型的生成節點。')
        old=db.get('runs',body.request_id)
        if old and (old['project_id']!=body.project_id or old['node_id']!=body.node_id): raise HTTPException(409,'request_id 已被其他任務使用。')
        return await services['start_run'](body)
    router.add_api_route('/runs',submit,methods=['POST'])

    @router.get('/runs/{id}')
    def run(id: str):
        return services['public_run'](services['require']('runs',id))

    router.add_api_route('/prompt-drafts',prompting.draft,methods=['POST'])
    router.add_api_route('/prompt-drafts',prompting.drafts,methods=['GET'])
    router.add_api_route('/context-options',prompting.context_options,methods=['GET'])
    app.include_router(management)
    app.include_router(router)
