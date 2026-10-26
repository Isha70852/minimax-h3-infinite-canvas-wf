"""Local parameter presets, shared by the UI and authenticated automation facade."""
import json
import math
import uuid
from typing import Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from . import storage as db, audio_workflows, image_workflows
from .workflow import Generation

router = APIRouter(prefix='/api/node-templates', tags=['Node templates'])

class Template(BaseModel):
    category: Literal['video', 'image', 'music', 'tts']
    name: str = Field(min_length=1, max_length=120)
    tags: list[str] = Field(default_factory=list, max_length=30)
    spec: dict
    is_default: bool = False

def clean(category, spec):
    if category == 'video':
        allowed = set(Generation.model_fields) - {'prompt','prompt_source','references','motion_context','context_run_id','context_video_asset_id'}
        result = {k:v for k,v in spec.items() if k in allowed}
        validated = Generation.model_validate({**result, 'prompt':'validation'})
        if 'noise_seed' in result: result['noise_seed']=validated.noise_seed
        return result
    registry = image_workflows.REGISTRY if category == 'image' else audio_workflows.REGISTRY
    entry = registry.get(spec.get('workflow'))
    if not entry or (category != 'image' and entry['category'] != category):
        raise ValueError('模板分類與工作流不符。')
    allowed = {f['key'] for f in entry['fields'] if f['type'] not in ('text','audio','image')}
    values = {k:v for k,v in spec.get('values',{}).items() if k in allowed}
    for f in entry['fields']:
        if f['key'] not in values: continue
        v=values[f['key']]
        if f['type']=='select' and v not in f['options']: raise ValueError('模板選項不支援：'+f['key'])
        if f['type']=='boolean' and not isinstance(v,bool): raise ValueError('需要布林值：'+f['key'])
        if f['type']=='string' and (not isinstance(v,str) or not v.strip()): raise ValueError('需要檔名或參數名稱：'+f['key'])
        if f['type'] in ('integer','number'):
            if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not f.get('min',-math.inf)<=v<=f.get('max',math.inf): raise ValueError('模板數值超出範圍：'+f['key'])
            if f['type']=='integer' and v!=int(v): raise ValueError('需要整數：'+f['key'])
            if f['key'] in ('width','height') and v%16: raise ValueError('圖片寬高需為 16 的倍數。')
    result = {'kind':'image' if category=='image' else 'audio', 'workflow':spec['workflow'], 'provider':spec.get('provider','comfyui'), 'values':values}
    if category == 'image':
        result['loras'] = spec.get('loras',[])
        if result['loras'] and 'lora' not in entry: raise ValueError('此工作流不支援 LoRA。')
    cls = image_workflows.ImageGeneration if category=='image' else audio_workflows.AudioGeneration
    cls.model_validate(result)
    if len(json.dumps(result)) > 100000: raise ValueError('模板過大。')
    return result

@router.get('')
def templates():
    return [x for x in db.all_records('node_templates') if not x.get('deleted')]

@router.put('/{id}')
def save_template(id: str, body: Template):
    if len(id)>100: raise ValueError('模板 ID 過長。')
    if not body.name.strip(): raise ValueError('請輸入模板名稱。')
    value = {**body.model_dump(), 'name':body.name.strip(), 'tags':list(dict.fromkeys(t.strip() for t in body.tags if t.strip())), 'spec':clean(body.category,body.spec)}
    if body.is_default:
        for other in templates():
            if other['category']==body.category and other['id']!=id and other['is_default']:
                db.put('node_templates',other['id'],{**other,'is_default':False})
    return db.put('node_templates',id,value)

@router.post('')
def create_template(body: Template):
    return save_template(uuid.uuid4().hex,body)

@router.delete('/{id}')
def delete_template(id: str):
    item = db.get('node_templates',id)
    if not item: raise HTTPException(404,'模板不存在。')
    db.put('node_templates',id,{**item,'deleted':True})
    return {'ok':True}

def resolve(category, spec, template_id=None, tag=None, use_default=True):
    candidates = [t for t in templates() if t['category']==category]
    selected = None
    if template_id or tag:
        candidates = [t for t in candidates if t['id']==template_id] if template_id else [t for t in candidates if tag in t['tags']]
        if len(candidates)!=1: raise ValueError('模板不存在或標籤對應多個模板，請改用 template_id。')
        selected = candidates[0]
    elif use_default:
        selected = next((t for t in candidates if t['is_default']),None)
    if not selected: return spec
    preset = selected['spec']
    if spec.get('workflow') and preset.get('workflow') and spec['workflow']!=preset['workflow']:
        if template_id or tag: raise ValueError('模板與指定工作流不相容。')
        return spec
    return {**preset,**spec,'values':{**preset.get('values',{}),**spec.get('values',{})}} if category!='video' else {**preset,**spec}
