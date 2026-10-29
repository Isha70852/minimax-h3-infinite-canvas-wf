"""Compile the supplied API graph; never mutate the template or user prompt."""
import copy
import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

ROOT = Path(__file__).resolve().parents[1]
VIDEO_REGISTRY = json.loads((ROOT/'workflows/video_registry.json').read_text(encoding='utf-8'))
MODELS = ['minimax_h3_fl2va_int8_convrot.safetensors', 'minimax_h3_hybrid_fl2va_ref2va_b25-49-int8_r.safetensors']
LORAS = ['minimax_h3_turbo_4步加速_comfyui.safetensors', 'minimax_h3_fl2v_turbo_4step_v1.2_768p_comfyui_bf16.safetensors']
ASPECTS = ['16:9 (Widescreen)', '9:16 (Portrait Widescreen)', '1:1 (Square)', '4:3 (Standard)', '3:4 (Portrait Standard)']


class Reference(BaseModel):
    asset_id: str
    role: Literal['reference', 'first', 'last'] = 'reference'


class VideoLoRA(BaseModel):
    name: str = Field(max_length=500)
    strength: float = Field(default=1, ge=-20, le=20, allow_inf_nan=False)
    enabled: bool = True


class Generation(BaseModel):
    seed_mode: Literal['fixed', 'randomize'] | None = None
    audio_mode: Literal['native','reference_only','lock_source','remix_source'] = 'native'
    drive_audio_asset_id: str | None = None
    instance_type: Literal['default','plus','ultra'] | None = None
    two_pass: bool = False
    save_first_pass: bool = True
    two_pass_parameters: dict = Field(default_factory=dict)
    noise_seed: str | None = Field(default=None, description='Decimal uint64 string; null/empty selects a fresh random seed. Use a string to avoid JavaScript precision loss.')

    @field_validator('noise_seed', mode='before')
    @classmethod
    def valid_seed(cls, value):
        if value is None or value=='': return None
        if isinstance(value,bool) or not isinstance(value,(str,int)): raise ValueError('Noise seed 必須是十進位整數字串。')
        text=str(value).strip()
        if not re.fullmatch(r'[0-9]{1,20}',text) or int(text)>18446744073709551615: raise ValueError('Noise seed 範圍為 0–18446744073709551615。')
        return str(int(text))
    motion_context: bool = False
    context_run_id: str | None = None
    context_video_asset_id: str | None = None
    prompt_source: str | None = None
    provider: Literal['comfyui', 'runninghub'] = 'comfyui'
    prompt: str = Field(min_length=1, max_length=100000)
    mode: Literal['T2VA', 'I2VA', 'L2VA', 'FL2VA', 'Ref2VA'] = 'T2VA'
    model: str = Field(default=MODELS[0], min_length=1, max_length=500)
    lora: str = Field(default=LORAS[0], min_length=1, max_length=500)
    lora_enabled: bool = True
    lora_strength: float = Field(default=1, ge=-20, le=20, allow_inf_nan=False)
    extra_loras: list[VideoLoRA] = Field(default_factory=list, max_length=30)
    shift_enabled: bool | None = None
    shift_video: float = Field(default=6, ge=0, le=100)
    shift_audio: float = Field(default=3, ge=0, le=100)
    low_vram_enabled: bool = False
    steps: int = Field(default=8, ge=1, le=200)
    sampler: str = Field(default='euler', min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_. -]+$')
    scheduler: str = Field(default='beta', min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_. -]+$')
    megapixels: float = Field(default=0.7, ge=0.1, le=4)
    aspect_ratio: str = ASPECTS[0]
    duration: float = Field(default=15, ge=1, le=15)
    head_chunks: int | None = Field(default=None, ge=1, le=56)
    chunks: int | None = Field(default=None, ge=1, le=64)
    references: list[Reference] = Field(default_factory=list, max_length=15)


def ordered_references(spec, assets):
    refs = []
    for ref in spec.references:
        if ref.asset_id not in assets:
            raise ValueError('引用素材不存在，請重新加入素材。')
        asset = assets[ref.asset_id]
        if ref.role != 'reference' and asset['kind'] != 'image':
            raise ValueError('首尾幀只能使用圖片。')
        refs.append({**asset, 'role': ref.role})
    if spec.mode == 'T2VA' and refs:
        raise ValueError('文生影片不使用素材，請移除引用或改用參考生影片。')
    expected = {'I2VA':['first'], 'L2VA':['last'], 'FL2VA':['first','last']}
    if spec.mode in expected:
        if sorted(r['role'] for r in refs) != expected[spec.mode]:
            raise ValueError('請依模式指定首幀／尾幀圖片，且不要混入參考素材。')
    elif any(r['role'] != 'reference' for r in refs):
        raise ValueError('首／尾幀請使用對應的生成模式。')
    if spec.mode == 'Ref2VA' and not refs:
        raise ValueError('參考生影片至少需要一項素材。')
    order = {'first': 0, 'last': 1, 'reference': 2}
    refs.sort(key=lambda r: (order[r['role']], {'image': 0, 'video': 1, 'audio': 2}[r['kind']]))
    counts = {'image': 0, 'video': 0, 'audio': 0}
    for ref in refs:
        kind = ref['kind']
        counts[kind] += 1
        n = counts[kind]
        ref['alias'] = {'image': '圖片', 'video': '影片', 'audio': '聲音'}[kind] + str(n)
        ref['tag'] = '<' + {'image': 'Picture', 'video': 'Video', 'audio': 'Audio'}[kind] + f' {n}>'
        if n > (9 if kind == 'image' else 3):
            raise ValueError('T8 最多支援 9 張圖片、3 部影片與 3 段聲音。')
    return refs


def translate_prompt(prompt, refs):
    aliases = {r['alias']: r['tag'] for r in refs}
    def replace(match):
        alias = match[1].replace('音訊', '聲音').replace('音頻', '聲音')
        if alias not in aliases:
            raise ValueError(f'提示詞引用 @{alias}，但引用面板沒有該素材。')
        return aliases[alias]
    prompt = re.sub(r'@(圖片\d+|影片\d+|聲音\d+|音訊\d+|音頻\d+)', replace, prompt)
    allowed = {r['tag'] for r in refs}
    for tag in re.findall(r'<(?:Picture|Video|Audio)\s+\d+>', prompt):
        if tag not in allowed:
            raise ValueError(f'提示詞中的 {tag} 沒有對應素材。')
    return prompt


def compile_workflow(spec: Generation, assets: dict, filenames: dict | None = None, seed: int = 0):
    if spec.noise_seed is not None: seed=int(spec.noise_seed)
    if spec.aspect_ratio not in ASPECTS:
        raise ValueError('不支援的畫面比例。')
    refs = ordered_references(spec, assets)
    prompt = translate_prompt(spec.prompt, refs)
    config = VIDEO_REGISTRY
    N = config['nodes']
    graph = json.loads((ROOT / 'workflows' / config['motion_template' if spec.motion_context else 'template']).read_text(encoding='utf-8-sig'))
    cond = graph[N['condition']]['inputs']
    for key in list(cond):
        if key.startswith('ref_') and '.' in key or key in ('first_frame', 'last_frame', 'drive_audio', 'final_audio'):
            del cond[key]
    cond['task_type'] = spec.mode
    cond['audio_mode'] = spec.audio_mode
    values = {'model':spec.model,'lora':spec.lora,'prompt':prompt,'megapixels':0.98 if spec.megapixels==1 else spec.megapixels,'aspect_ratio':spec.aspect_ratio,'duration':spec.duration,'seed':seed,'sampler':spec.sampler.strip(),'steps':spec.steps,'scheduler':spec.scheduler.strip()}
    for key,(role,field) in config['fields'].items():
        if N[role] not in graph or field not in graph[N[role]]['inputs']: raise ValueError(f'影片映射已失效：{key}')
        graph[N[role]]['inputs'][field] = values[key]
    graph[N['lora']]['inputs']['model'] = [N['model'],0]
    graph[N['lora']]['inputs']['strength_model'] = spec.lora_strength
    graph[N['resolution']]['inputs']['multiple'] = 32
    graph[N['output']]['inputs']['filename_prefix'] = f'H3Canvas/{seed}'
    def node(id, cls, **inputs):
        graph[id] = {'class_type': cls, 'inputs': inputs}
        return [id, 0]
    model = [N['lora'], 0] if spec.lora_enabled else [N['model'], 0]
    if spec.lora_enabled:
        for i, lora in enumerate(spec.extra_loras):
            if not lora.enabled or not lora.name.strip(): continue
            id = str(9000+i)
            graph[id] = copy.deepcopy(graph[N['lora']])
            graph[id]['inputs'].update(model=model, lora_name=lora.name.strip(), strength_model=lora.strength)
            model = [id,0]
    shift = spec.shift_enabled if spec.shift_enabled is not None else spec.lora == LORAS[1]
    if spec.lora_enabled and shift:
        model = node(N['shift'], 'MiniMaxH3SigmaShift', model=model, shift_video=spec.shift_video, shift_audio=spec.shift_audio)
    graph[N['kitchen']]['inputs'].update(model=model, attention='comfy kitchen attention')
    graph[N['sol']]['inputs']['model'] = [N['kitchen'], 0]
    model = [N['sol'], 0]
    if spec.low_vram_enabled:
        heads = spec.head_chunks or (8 if spec.megapixels >= 1.5 else 4)
        chunks = spec.chunks or (4 if spec.megapixels >= 1.5 else 2)
        model = node(N['low_vram'], 'MiniMaxLowVRAMAttention', model=model, head_chunks=heads)
        model = node(N['chunks'], 'MiniMaxChunkFeedForward', model=model, chunks=chunks, seq_threshold=4096)
    graph[N['scheduler']]['inputs']['model'] = model
    graph[N['guider']]['inputs']['model'] = model
    counts = {'image': 0, 'video': 0, 'audio': 0}
    for i, ref in enumerate(refs):
        id = str(config['reference_node_start'] + i * 2)
        filename = (filenames or {}).get(ref['id'], ref['filename'])
        kind = ref['kind']
        if kind == 'image':
            link = node(id, 'LoadImage', image=filename)
        elif kind == 'audio':
            link = node(id, 'LoadAudio', audio=filename)
        else:
            video = node(id, 'LoadVideo', file=filename)
            link = node(str(int(id) + 1), 'GetVideoComponents', video=video)
        if ref['role'] != 'reference':
            cond[ref['role'] + '_frame'] = link
        else:
            singular = {'image': 'image', 'video': 'video', 'audio': 'audio'}[kind]
            cond[f'ref_{singular}s.ref_{singular}_{counts[kind]}'] = link
            counts[kind] += 1
    # Only retain nodes reachable from the output, dropping UI-only group controllers
    # and disconnected example media/models, which otherwise fail remote validation.
    active = set()
    def visit(id):
        if id in active:
            return
        active.add(id)
        for val in graph[id]['inputs'].values():
            if isinstance(val, list) and len(val) == 2 and isinstance(val[0], str):
                if val[0] not in graph:
                    raise ValueError(f'工作流缺少節點 {val[0]}')
                visit(val[0])
    if spec.audio_mode in ('lock_source','remix_source') and not spec.drive_audio_asset_id:
        raise ValueError('此 audio_mode 需要連接或選擇 drive audio。')
    if spec.drive_audio_asset_id:
        audio=assets[spec.drive_audio_asset_id]
        if audio['kind']!='audio': raise ValueError('Drive audio 必須是聲音素材。')
        cond['drive_audio']=node('9100','LoadAudio',audio=(filenames or {}).get(audio['id'],audio['filename']))
    has_context=spec.motion_context and bool(spec.context_video_asset_id)
    if has_context:
        asset=assets[spec.context_video_asset_id]
        if asset['kind']!='video': raise ValueError('Motion context 必須使用影片。')
        graph[N['context_video']]['inputs']['file']=(filenames or {}).get(asset['id'],asset['filename'])
    else:
        graph[N['guider']]['inputs']['conditioning']=[N['condition'],0]
    # Both output branches independently bypass overlap trimming without context.
    if not has_context:
        graph[N['output']]['inputs'].update(images=[N['video_decode'],0],audio=[N['audio_decode'],0])
        graph[N['output2']]['inputs'].update(images=[N['decode2'],0],audio=[N['decode2'],1])
    outputs=[N['output']]
    if spec.two_pass:
        for role, parameters in spec.two_pass_parameters.items():
            defaults=config['two_pass_parameters'].get(role)
            if defaults is None or not isinstance(parameters,dict): raise ValueError('未知二採參數群組')
            for key,value in parameters.items():
                if key not in defaults: raise ValueError('未知二採參數：'+key)
                default=defaults[key]
                if key=='restart_seed': value=int(Generation.valid_seed(value))
                elif isinstance(default,bool):
                    if not isinstance(value,bool): raise ValueError(key+' 需要布林值')
                elif isinstance(default,(int,float)):
                    import math
                    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value): raise ValueError(key+' 需要有限數字')
                    if isinstance(default,int) and int(value)!=value: raise ValueError(key+' 需要整數')
                elif not isinstance(value,str) or not value.strip(): raise ValueError(key+' 需要非空字串')
                graph[N[role]]['inputs'][key]=value
        if not 1<=graph[N['upscale']]['inputs']['scale_by']<=4: raise ValueError('scale_by 必須介於 1–4')
        graph[N['plan']]['inputs']['model']=model
        graph[N['mixer']]['inputs']['model']=model
        # Keep the supplied full first-pass schedule; parity plan supplies only refinement sigmas.
        high=copy.deepcopy(cond)
        high.update(width=[N['upscale'],1],height=[N['upscale'],2])
        graph[N['condition2']]['inputs']=high
        outputs=([N['output']] if spec.save_first_pass else [])+[N['output2']]
    for role, label in (('output','first'),('output2','second')):
        graph[N[role]]['inputs'].update(frame_rate=24,filename_prefix=f'H3Canvas/{seed}_{label}')
    for output in outputs: visit(output)
    return {'workflow': {k: v for k, v in graph.items() if k in active}, 'prompt': prompt,
            'mapping': [{k: r[k] for k in ('id', 'name', 'kind', 'role', 'alias', 'tag')} for r in refs],
            'seed': str(seed), 'output_passes': {N['output']:'first',N['output2']:'second'}, 'output_nodes': outputs, 'workflow_version': config['version']}
