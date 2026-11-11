"""Declarative user workflow packages. Local, versioned graphs; no plugin code."""
import copy,json,math,re,uuid
from typing import Literal
from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from . import storage as db
from .workflow import Reference
router=APIRouter(prefix='/api/custom-workflows',tags=['Custom workflows'])
MEDIA={'image','audio','video'}
BUILTIN=[{'id':k,'name':v} for k,v in [('video','影片生成'),('image','圖片生成'),('music','音樂生成'),('tts','TTS 生成'),('3d','3D 生成')]]

def graph_check(graph):
    if not isinstance(graph,dict) or not graph or len(graph)>2000: raise ValueError('請提供 API 格式 JSON（最多 2000 節點），不是視覺工作流。')
    if len(json.dumps(graph))>8*1024*1024: raise ValueError('工作流過大。')
    for id,n in graph.items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+',id) or not isinstance(n,dict) or not isinstance(n.get('class_type'),str) or not isinstance(n.get('inputs'),dict): raise ValueError('無效的 API 節點。')
    return graph

def link(value):
    return isinstance(value,list) and len(value)==2 and isinstance(value[0],(str,int)) and isinstance(value[1],int) and not isinstance(value[1],bool)

def prune(graph,outputs):
    seen=set();visiting=set()
    def visit(id):
        id=str(id)
        if id in visiting: raise ValueError('工作流包含循環接線：'+id)
        if id in seen:return
        if id not in graph:raise ValueError('接線指向不存在的節點：'+id)
        visiting.add(id)
        for value in graph[id]['inputs'].values():
            if link(value):visit(value[0])
        visiting.remove(id);seen.add(id)
    for id in outputs:visit(id)
    return {k:v for k,v in graph.items() if k in seen}

class ImportRequest(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    graph:dict

@router.post('/inspect')
def inspect(body:ImportRequest):
    graph=graph_check(body.graph);fields=[]
    for id,n in graph.items():
        for key,value in n['inputs'].items():
            if link(value) or not isinstance(value,(str,int,float,bool)):continue
            kind='boolean' if isinstance(value,bool) else 'integer' if isinstance(value,int) else 'number' if isinstance(value,float) else 'text'
            model=next((v for k,v in [('unet_name','unet'),('vae_name','vae'),('clip_name','clip'),('lora_name','lora'),('ckpt_name','checkpoint')] if key==k),None)
            if model:kind='model'
            elif isinstance(value,str):
                cls=n['class_type'].lower()
                if 'load' in cls and key in ('image','audio','video','file','path'):
                    kind='audio' if 'audio' in cls else 'video' if 'video' in cls else 'image' if 'image' in cls else 'text'
                elif key in ('noise_seed','seed'):kind='seed'
            elif key in ('noise_seed','seed'):kind='seed'
            fields.append({'key':id+'_'+key.replace('.','_'),'label':n.get('_meta',{}).get('title',n['class_type'])+' · '+key,'node':id,'input':key,'type':kind,'model_group':model or 'unet','default':str(value) if kind=='seed' else value,'required':kind in MEDIA,'tag':''})
    consumed={str(v[0]) for n in graph.values() for v in n['inputs'].values() if link(v)}
    return {'name':body.name,'graph':graph,'candidates':fields,'output_candidates':[{'id':id,'name':n.get('_meta',{}).get('title',n['class_type'])} for id,n in graph.items() if id not in consumed]}

class Package(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    category:str='video'
    graph:dict
    fields:list[dict]=Field(default_factory=list,max_length=200)
    media_groups:list[dict]=Field(default_factory=list,max_length=20)
    modes:list[dict]=Field(default_factory=list,max_length=40)
    outputs:list[str]=Field(min_length=1,max_length=30)
    default_mode:str=''
    runninghub_ids:dict[str,str]=Field(default_factory=dict)


def validate_package(d):
    g=graph_check(d['graph'])
    if d['category'] not in {c['id'] for c in categories()}:raise ValueError('請先建立工作流分類。')
    keys=set();targets=set()
    for f in d['fields']:
        if not re.fullmatch(r'[A-Za-z0-9_-]+',f.get('key','')) or f['key'] in keys:raise ValueError('欄位 key 不可重複或含特殊符號。')
        f.setdefault('label',f['key'])
        keys.add(f['key']);id=str(f.get('node'));inp=f.get('input')
        if id not in g or inp not in g[id]['inputs']:raise ValueError('欄位映射失效：'+f['key'])
        if f.get('type') not in MEDIA|{'text','string','integer','number','boolean','select','model','seed'}:raise ValueError('不支援的欄位型別。')
        if f.get('type') not in MEDIA and link(g[id]['inputs'][inp]):raise ValueError('一般參數只能對應常數欄位；請使用模式接線切換連線。')
        f['class_type']=g[id]['class_type']
    for group in d['media_groups']:
        key=group.get('key','')
        if not re.fullmatch(r'[A-Za-z0-9_-]+',key) or key in keys:raise ValueError('素材群組 key 不正確或重複。')
        keys.add(key);group.setdefault('label',key)
        if group.get('kind') not in MEDIA or not 1<=int(group.get('max_items',1))<=32:raise ValueError('素材群組類型或上限錯誤。')
        loader=str(group.get('loader_node'));target=str(group.get('target_node'));pattern=group.get('target_pattern','')
        if loader not in g or group.get('file_input') not in g[loader]['inputs'] or target not in g:raise ValueError('素材群組節點映射失效。')
        if pattern.count('{index}')!=1 or len(pattern)>200:raise ValueError('目標欄位格式需包含一個 {index}。')
        if int(group.get('output_slot',0))<0 or int(group.get('start_index',0))<0:raise ValueError('插槽索引不可為負值。')
        if (target,pattern) in targets:raise ValueError('素材群組不可重複控制同一目標。')
        targets.add((target,pattern))
        component=str(group.get('component_node') or '')
        if component and (group['kind']!='video' or component not in g or g[component]['class_type']!='GetVideoComponents' or g[component]['inputs'].get('video')!=[loader,0]):raise ValueError('影片解包需為連接至 LoadVideo 的 GetVideoComponents。')
        audio_pattern=group.get('video_audio_pattern','')
        if audio_pattern:
            if not component or audio_pattern.count('{index}')!=1 or len(audio_pattern)>200:raise ValueError('影片原音欄位需有 GetVideoComponents 及一個 {index}。')
            if (target,audio_pattern) in targets:raise ValueError('影片原音目標重複。')
            targets.add((target,audio_pattern))
        group['loader_class']=g[loader]['class_type'];group['target_class']=g[target]['class_type']
    modes=[m.get('id') for m in d['modes']]
    if len(set(modes))!=len(modes) or any(not re.fullmatch(r'[A-Za-z0-9_-]+',x or '') for x in modes):raise ValueError('模式 ID 不正確或重複。')
    if d['default_mode'] and d['default_mode'] not in modes:raise ValueError('預設模式不存在。')
    for f in [*d['fields'],*d['media_groups']]:
        if set(f.get('modes',[]))-set(modes):raise ValueError('欄位引用不存在的模式。')
    if any(v and not v.isdigit() for v in d['runninghub_ids'].values()):raise ValueError('RunningHub 工作流 ID 必須為數字。')
    for mode in [None,*d['modes']]:
        transformed=apply_mode(copy.deepcopy(g),mode)
        prune(transformed,d['outputs'])
    return d

def apply_mode(graph,mode):
    if not mode:return graph
    # Explicit per-output bypass: MODEL/CLIP/etc must each have their own mapping.
    for rule in mode.get('bypass',[]):
        node=str(rule.get('node',''));slot=int(rule.get('slot',0));source=[str(rule.get('source','')),int(rule.get('source_slot',0))]
        if node not in graph or source[0] not in graph or node==source[0] or min(slot,source[1])<0:raise ValueError('旁路接線無效。')
        for n in graph.values():
            for key,value in list(n['inputs'].items()):
                if link(value) and str(value[0])==node and value[1]==slot:n['inputs'][key]=source.copy()
    for rule in mode.get('connections',[]):
        target=str(rule.get('target',''));field=rule.get('input','')
        if target not in graph or field not in graph[target]['inputs']:raise ValueError('模式目標欄位不存在。')
        if rule.get('disconnect'):graph[target]['inputs'].pop(field,None)
        else:
            source=str(rule.get('source',''));slot=int(rule.get('slot',0))
            if source not in graph or slot<0:raise ValueError('模式來源不存在。')
            graph[target]['inputs'][field]=[source,slot]
    return graph

def categories():return BUILTIN+(db.get('custom_config','categories') or {}).get('items',[])

@router.get('/categories')
def get_categories():return categories()

class Category(BaseModel):
    name:str=Field(min_length=1,max_length=80)
@router.post('/categories')
def add_category(body:Category):
    item={'id':'category_'+uuid.uuid4().hex[:12],'name':body.name.strip()}
    items=(db.get('custom_config','categories') or {}).get('items',[])
    db.put('custom_config','categories',{'items':items+[item]});return item

@router.get('')
def catalog():
    return [{k:v for k,v in p.items() if k not in ('graph','runninghub_ids')} for p in db.all_records('custom_packages') if not p.get('deleted')]

@router.get('/{id}/versions/{version}')
def get_version(id:str,version:int):
    p=db.get('custom_revisions',id+':'+str(version))
    if not p:raise HTTPException(404,'工作流版本不存在。')
    return p

@router.post('')
def create_package(body:Package):return save_package(uuid.uuid4().hex,body)

@router.put('/{id}')
def save_package(id:str,body:Package):
    value=validate_package(body.model_dump());old=db.get('custom_packages',id);version=(old or {}).get('version',0)+1
    value.update(package_id=id,version=version)
    # No automatic migration: each revision is immutable and nodes pin its version.
    db.put('custom_revisions',id+':'+str(version),value)
    return db.put('custom_packages',id,value)

@router.delete('/{id}')
def delete_package(id:str):
    p=db.get('custom_packages',id)
    if not p:raise HTTPException(404)
    db.put('custom_packages',id,{**p,'deleted':True});return {'ok':True}

class CustomGeneration(BaseModel):
    kind:Literal['custom']='custom'
    provider:Literal['comfyui','runninghub','colab']='comfyui'
    provider_profile_id:str|None=None
    package_id:str
    version:int=Field(ge=1)
    mode:str=''
    values:dict=Field(default_factory=dict)
    media_assets:dict[str,list[str]]=Field(default_factory=dict)
    text_sources:dict[str,str]=Field(default_factory=dict)
    seed_overrides:dict[str,str]=Field(default_factory=dict)
    @property
    def references(self):return [Reference(asset_id=id) for id in dict.fromkeys(id for ids in self.media_assets.values() for id in ids) if id]

def resolve_text(spec,project):
    p=get_version(spec.package_id,spec.version);fields={f['key']:f for f in p['fields']};values=dict(spec.values)
    for key,id in spec.text_sources.items():
        n=next((n for n in project.get('nodes',[]) if n['id']==id and n.get('data',{}).get('kind')=='text'),None)
        if not n or fields.get(key,{}).get('type')!='text':raise ValueError('文字來源或欄位不正確。')
        values[key]=n['data'].get('text','')
    return spec.model_copy(update={'values':values,'text_sources':{}})

def enabled(field,mode):return not field.get('modes') or mode in field['modes']

def compile_custom(spec,assets,filenames=None,seed=0):
    if spec.text_sources:raise ValueError('請先解析文字連線。')
    p=get_version(spec.package_id,spec.version);mode=spec.mode or p['default_mode']
    if mode and mode not in {m['id'] for m in p['modes']}:raise ValueError('模式不存在。')
    graph=apply_mode(copy.deepcopy(p['graph']),next((m for m in p['modes'] if m['id']==mode),None));mapping=[];aliases={}
    fields={f['key']:f for f in p['fields']};groups={g['key']:g for g in p['media_groups']}
    if set(spec.values)-fields.keys() or set(spec.media_assets)-({k for k,f in fields.items() if f['type'] in MEDIA}|groups.keys()):raise ValueError('參數或素材插槽不存在。')
    def media(id,kind,label,tag):
        a=assets.get(id)
        if not a or a['kind']!=kind:raise ValueError('請提供正確素材：'+label)
        mapping.append({'id':id,'name':a['name'],'kind':kind,'alias':label,'tag':tag})
        if tag:aliases['@'+label]=tag
        return (filenames or {}).get(id,a['filename'])
    # Repeated groups own only their declared indexed target inputs.
    reachable=set(prune(graph,p['outputs']))
    for key,g in groups.items():
        target=str(g['target_node']);pattern=g['target_pattern'];regex='^'+re.escape(pattern).replace(re.escape('{index}'),r'\d+')+'$'
        audio_pattern=g.get('video_audio_pattern','')
        audio_regex='^'+re.escape(audio_pattern).replace(re.escape('{index}'),r'\d+')+'$' if audio_pattern else None
        for field in list(graph[target]['inputs']):
            if re.fullmatch(regex,field) or (audio_regex and re.fullmatch(audio_regex,field)):del graph[target]['inputs'][field]
        if not enabled(g,mode) or target not in reachable:continue
        ids=spec.media_assets.get(key,[])
        if len(ids)>int(g['max_items']):raise ValueError(g['label']+' 素材超過上限。')
        for index,id in enumerate(ids):
            nid='custom_'+key+'_'+str(index)
            if nid in graph:raise ValueError('動態節點 ID 衝突。')
            graph[nid]=copy.deepcopy(graph[str(g['loader_node'])]);tag=g.get('tag_pattern','').replace('{index}',str(index+1))
            graph[nid]['inputs'][g['file_input']]=media(id,g['kind'],g['label']+str(index+1),tag)
            source=nid
            if g.get('component_node'):
                source=nid+'_components'
                if source in graph:raise ValueError('動態影片解包節點 ID 衝突。')
                graph[source]=copy.deepcopy(graph[str(g['component_node'])])
                graph[source]['inputs']['video']=[nid,0]
            suffix=str(index+int(g.get('start_index',0)))
            graph[target]['inputs'][pattern.replace('{index}',suffix)]=[source,int(g.get('output_slot',0))]
            if audio_pattern and g.get('include_video_audio',True):graph[target]['inputs'][audio_pattern.replace('{index}',suffix)]=[source,1]
    graph=prune(graph,p['outputs'])
    for key,f in fields.items():
        node=str(f['node'])
        if not enabled(f,mode) or node not in graph:continue
        if f['input'] not in graph[node]['inputs']:raise ValueError('映射被模式移除：'+f['label'])
        typ=f['type']
        if typ in MEDIA:
            ids=spec.media_assets.get(key,[])
            if len(ids)>1:raise ValueError('單一素材欄位僅可接一份素材。')
            if not ids:raise ValueError('有效接線缺少素材：'+f['label']+'；不使用時請用模式斷開此分支。')
            value=media(ids[0],typ,f['label'],f.get('tag',''))
        else:
            value=spec.values.get(key,f.get('default',graph[node]['inputs'][f['input']]))
            if typ=='seed':
                if value not in ('',None,'random') and (isinstance(value,bool) or not re.fullmatch(r'[0-9]+',str(value))):raise ValueError('Seed 必須為非負整數或 random。')
                value=seed if value in ('',None,'random') else int(value)
                if not 0<=value<2**64:raise ValueError('Seed 超出範圍。')
            elif typ in ('integer','number'):
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError(f['label']+' 需為數字。')
                if f.get('min') is not None and value<float(f['min']) or f.get('max') is not None and value>float(f['max']):raise ValueError(f['label']+' 超出範圍。')
                if typ=='integer' and value!=int(value):raise ValueError('需要整數。')
            elif typ=='boolean':
                if not isinstance(value,bool):raise ValueError('需要布林值。')
            else:
                if not isinstance(value,str) or len(value)>100000:raise ValueError('需要文字。')
                if f.get('required') and not value.strip():raise ValueError('必填：'+f['label'])
                if typ=='select' and value not in f.get('options',[]):raise ValueError('不支援的選項。')
        graph[node]['inputs'][f['input']]=value
    # Mapping is explicit; never infer H3 tags for arbitrary workflows.
    for key,f in fields.items():
        if f['type']=='text' and str(f['node']) in graph and enabled(f,mode):
            value=graph[str(f['node'])]['inputs'].get(f['input'],'')
            if isinstance(value,str):
                for alias in sorted(aliases,key=len,reverse=True):value=value.replace(alias,aliases[alias])
                graph[str(f['node'])]['inputs'][f['input']]=value
    seed_values={node+':'+key:str(value) for node,n in graph.items() for key,value in n['inputs'].items() if key in ('noise_seed','seed') and isinstance(value,int) and not isinstance(value,bool)}
    for f in fields.values():
        if f['type']=='seed' and str(f['node']) in graph:
            value=graph[str(f['node'])]['inputs'].get(f['input'])
            if isinstance(value,int):seed_values[str(f['node'])+':'+f['input']]=str(value)
    for key,value in spec.seed_overrides.items():
        if key not in seed_values or not re.fullmatch(r'[0-9]{1,20}',value) or int(value)>=2**64:raise ValueError('沿用 seed 的映射或數值無效。')
        node,field=key.split(':',1);graph[node]['inputs'][field]=int(value);seed_values[key]=str(int(value))
    return {'seed_values':seed_values,'workflow':graph,'mapping':mapping,'prompt':'\n'.join(str(graph[str(f['node'])]['inputs'].get(f['input'],'')) for f in fields.values() if f['type']=='text' and str(f['node']) in graph),'seed':str(seed),'output_nodes':p['outputs'],'workflow_version':spec.version}

class Models(BaseModel):
    groups:dict[str,list[str]]=Field(default_factory=dict)
@router.get('/models/library')
def models():return (db.get('custom_config','models') or {}).get('groups',{'unet':[],'vae':[],'clip':[],'lora':[]})
@router.put('/models/library')
def save_models(body:Models):
    if len(body.groups)>40 or any(len(v)>500 or any(not isinstance(x,str) or len(x)>500 for x in v) for v in body.groups.values()):raise ValueError('模型清單過大。')
    db.put('custom_config','models',body.model_dump());return body.groups

class Preset(BaseModel):
    name:str=Field(min_length=1,max_length=120)
    tags:list[str]=Field(default_factory=list)
    is_default:bool=False
    spec:CustomGeneration
@router.get('/presets/list')
def presets():return [p for p in db.all_records('custom_presets') if not p.get('deleted')]
@router.post('/presets')
def create_preset(body:Preset):return save_preset(uuid.uuid4().hex,body)
@router.put('/presets/{id}')
def save_preset(id:str,body:Preset):
    get_version(body.spec.package_id,body.spec.version)
    value=body.model_dump();value['spec']['media_assets']={};value['spec']['text_sources']={}
    if body.is_default:
        for p in presets():
            if p['spec']['package_id']==body.spec.package_id and p['id']!=id:db.put('custom_presets',p['id'],{**p,'is_default':False})
    return db.put('custom_presets',id,value)
@router.delete('/presets/{id}')
def delete_preset(id:str):
    p=db.get('custom_presets',id)
    if not p:raise HTTPException(404)
    db.put('custom_presets',id,{**p,'deleted':True});return {'ok':True}
