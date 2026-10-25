"""Extensible audio registry: only declared fields may override supplied templates."""
import json
from typing import Literal
from pydantic import BaseModel, Field
from .workflow import ROOT, Reference

REGISTRY = json.loads((ROOT/'workflows/audio_registry.json').read_text(encoding='utf-8'))

class AudioGeneration(BaseModel):
    kind: Literal['audio'] = 'audio'
    provider: Literal['comfyui','runninghub'] = 'comfyui'
    workflow: str
    values: dict[str, str | float] = Field(default_factory=dict)
    audio_asset_id: str | None = None
    text_sources: dict[str,str] = Field(default_factory=dict)

    @property
    def references(self):
        return [Reference(asset_id=self.audio_asset_id)] if self.audio_asset_id else []

def catalog():
    return [{'id':key, **{k:v for k,v in entry.items() if k!='output'},
             'fields':[{k:v for k,v in f.items() if k not in ('node','field')} for f in entry['fields']]}
            for key,entry in REGISTRY.items()]

def resolve_text(spec, project):
    entry = REGISTRY.get(spec.workflow)
    if not entry: raise ValueError('不支援的音樂／TTS 功能。')
    fields={f['key']:f for f in entry['fields']}
    values=dict(spec.values)
    for key,node_id in spec.text_sources.items():
        if key not in fields or fields[key]['type']!='text': raise ValueError('此欄位不支援文字連線。')
        node=next((n for n in project.get('nodes',[]) if n['id']==node_id),None)
        if not node or node.get('data',{}).get('kind')!='text': raise ValueError('連接的文字節點不存在。')
        values[key]=node['data'].get('text','')
    return spec.model_copy(update={'values':values,'text_sources':{}})

def compile_audio(spec, assets, filenames=None, seed=0):
    entry=REGISTRY.get(spec.workflow)
    if not entry: raise ValueError('不支援的音樂／TTS 功能。')
    if spec.text_sources: raise ValueError('請先解析專案文字連線。')
    graph=json.loads((ROOT/'workflows'/entry.get('template',f'{spec.workflow}.json')).read_text(encoding='utf-8-sig'))
    if entry.get('active_nodes'):
        graph={k:v for k,v in graph.items() if k in entry['active_nodes']}
    fields={f['key']:f for f in entry['fields']}
    if set(spec.values)-fields.keys(): raise ValueError('此功能不支援指定的輸入欄位。')
    mapping=[]
    for key,f in fields.items():
        if f['type']=='audio':
            asset=assets.get(spec.audio_asset_id)
            if not asset or asset.get('kind')!='audio': raise ValueError('請選擇或連接一個聲音素材。')
            value=(filenames or {}).get(asset['id'],asset['filename'])
            mapping.append({'id':asset['id'],'name':asset['name'],'field':key})
        else:
            value=spec.values.get(key,f.get('default',''))
            if f['type']=='text':
                if not isinstance(value,str) or (not value.strip() and not f.get('optional')) or len(value)>100000:
                    raise ValueError(f"請填寫有效的 {f['label']}。")
            elif f['type']=='select' and value not in f['options']: raise ValueError(f"不支援的 {f['label']}。")
            elif f['type']=='number':
                value=float(value)
                if not f['min']<=value<=f['max']: raise ValueError('情感權重需介於 0 和 1。')
        graph[f['node']]['inputs'][f['field']]=value
    if spec.audio_asset_id and not any(f['type']=='audio' for f in fields.values()): raise ValueError('此功能不接受聲音輸入。')
    return {'workflow':graph,'prompt':str(spec.values.get('text',spec.values.get('lyrics',''))),'mapping':mapping,'seed':'template','output_nodes':[entry['output']]}
