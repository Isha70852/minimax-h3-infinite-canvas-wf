"""Image workflows: declarative field bindings plus reusable graph transforms."""
import json
import math
from typing import Literal
from pydantic import BaseModel, Field
from .workflow import ROOT, Reference

REGISTRY = json.loads((ROOT / 'workflows/image_registry.json').read_text(encoding='utf-8'))

class LoRA(BaseModel):
    name: str = Field(default='', max_length=500)
    strength: float = Field(default=1, ge=-20, le=20, allow_inf_nan=False)
    enabled: bool = True

class ImageGeneration(BaseModel):
    kind: Literal['image'] = 'image'
    provider: Literal['comfyui','runninghub'] = 'comfyui'
    workflow: str
    values: dict = Field(default_factory=dict)
    image_assets: dict[str,str] = Field(default_factory=dict)
    text_sources: dict[str,str] = Field(default_factory=dict)
    loras: list[LoRA] = Field(default_factory=list, max_length=30)

    @property
    def references(self):
        return [Reference(asset_id=id) for id in dict.fromkeys(self.image_assets.values()) if id]

def catalog():
    return [{'id':key,'name':d['name'],'version':d['version'],'supports_lora':'lora' in d,
             'fields':[{k:v for k,v in f.items() if k not in ('node','input')} for f in d['fields']]}
            for key,d in REGISTRY.items()]

def definition(spec):
    if spec.workflow not in REGISTRY: raise ValueError('不支援的圖片工作流。')
    return REGISTRY[spec.workflow]

def resolve_text(spec, project):
    fields={f['key']:f for f in definition(spec)['fields']}
    values=dict(spec.values)
    for key,id in spec.text_sources.items():
        node=next((n for n in project.get('nodes',[]) if n['id']==id),None)
        if key not in fields or fields[key]['type']!='text' or not node or node.get('data',{}).get('kind')!='text':
            raise ValueError('圖片提示詞需要連接此專案的文字節點。')
        values[key]=node['data'].get('text','')
    return spec.model_copy(update={'values':values,'text_sources':{}})

def rewire(graph, replacements):
    for node in graph.values():
        for key,value in list(node['inputs'].items()):
            if isinstance(value,list) and len(value)==2 and value[0] in replacements:
                node['inputs'][key]=replacements[value[0]].copy()

def compile_image(spec, assets, filenames=None, seed=0):
    entry=definition(spec)
    if spec.text_sources: raise ValueError('請先解析文字連線。')
    graph=json.loads((ROOT/'workflows'/entry['template']).read_text(encoding='utf-8-sig'))
    fields={f['key']:f for f in entry['fields']}
    if set(spec.values)-fields.keys(): raise ValueError('圖片工作流包含不支援的參數。')
    if set(spec.image_assets)-{k for k,f in fields.items() if f['type']=='image'}: raise ValueError('此功能不接受指定的圖片輸入。')
    values={}; mapping=[]
    for key,f in fields.items():
        node=graph.get(f['node'])
        if not node or f['input'] not in node['inputs']: raise ValueError(f'工作流欄位映射已失效：{key}，請更新 registry。')
        if f['type']=='image':
            id=spec.image_assets.get(key)
            if not id and f.get('optional'): continue
            asset=assets.get(id)
            if not asset or asset.get('kind')!='image': raise ValueError(f"請選擇 {f['label']}。")
            value=(filenames or {}).get(id,asset['filename'])
            mapping.append({'id':id,'name':asset['name'],'field':key})
        else:
            value=spec.values.get(key,f['default'])
            if f['type'] in ('text','string','select'):
                if not isinstance(value,str) or (not value.strip() and not f.get('optional')) or len(value)>100000: raise ValueError(f"請填寫 {f['label']}。")
                if f['type']=='select' and value not in f['options']: raise ValueError('不支援的模型選擇。')
            elif f['type']=='boolean':
                if not isinstance(value,bool): raise ValueError('圖片大小選項必須為 true 或 false。')
            elif f['type'] in ('integer','number'):
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not f['min']<=value<=f['max']: raise ValueError(f"{f['label']} 超出範圍。")
                if f['type']=='integer':
                    if value!=int(value): raise ValueError(f"{f['label']} 必須為整數。")
                    value=int(value)
                if key in ('width','height') and value%16: raise ValueError('圖片寬高需為 16 的倍數。')
        values[key]=value
        node['inputs'][f['input']]=value
    if clip:=entry.get('model_clip'):
        graph[clip['node']]['inputs'][clip['input']]=clip['models'][values['model']]
    if branch:=entry.get('optional_branch'):
        if not spec.image_assets.get(branch['field']):
            rewire(graph,branch['rewire'])
            for id in branch['remove']: graph.pop(id,None)
    if spec.loras and 'lora' not in entry: raise ValueError('此工作流沒有開放 LoRA。')
    if chain:=entry.get('lora'):
        previous=chain['source']
        for i,lora in enumerate(spec.loras):
            if not lora.enabled or not lora.name.strip(): continue
            id=str(max(int(k) for k in graph)+1)
            graph[id]={'class_type':'LoraLoaderModelOnly','inputs':{'model':previous,'lora_name':lora.name.strip(),'strength_model':lora.strength}}
            previous=[id,0]
        rewire(graph,{chain['placeholder']:previous})
        graph.pop(chain['placeholder'],None)
    # Fresh task seed; all other non-exposed inputs keep their template values.
    graph[entry['sampler']]['inputs']['seed']=seed
    for node in graph.values():
        for value in node['inputs'].values():
            if isinstance(value,list) and len(value)==2 and str(value[0]) not in graph: raise ValueError('工作流有遺失的節點連線。')
    return {'workflow':graph,'prompt':values['prompt'],'mapping':mapping,'seed':str(seed),'output_nodes':[entry['output']],'workflow_version':entry['version']}
