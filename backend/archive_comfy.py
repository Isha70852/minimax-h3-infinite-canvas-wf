"""Read embedded ComfyUI metadata. Never executes workflow code."""
import json


def decode(value):
    for _ in range(4):
        if not isinstance(value, str):
            break
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            break
    return value


def extract(metadata):
    found = {}
    def visit(value, depth=0):
        if depth > 6:
            return
        value = decode(value)
        if not isinstance(value, dict):
            return
        for key, val in value.items():
            val = decode(val)
            if key.lower() in ('prompt', 'workflow') and isinstance(val, dict):
                found[key.lower()] = val
            elif isinstance(val, dict):
                visit(val, depth + 1)
    visit(metadata.get('format', {}).get('tags', {}))
    for stream in metadata.get('streams', []):
        visit(stream.get('tags', {}))
    return found


def summarize(embedded):
    prompt = embedded.get('prompt', {})
    workflow = embedded.get('workflow', {})
    nodes = {str(k): v for k, v in prompt.items() if isinstance(v, dict) and 'class_type' in v}
    modes = {str(n['id']): n.get('mode', 0) for n in workflow.get('nodes', [])}
    warnings = []
    result = {k: [] for k in ('scheduler', 'sampler', 'steps', 'seed', 'models', 'loras', 'prompts')}
    if not nodes:
        warnings.append('未找到 API prompt；僅有畫布工作流時無法可靠判定自訂節點參數與實際執行鏈。可下載原始資料檢查。')
        return dict(result, warnings=warnings, active_nodes=[], excluded_nodes=[])
    def is_link(v):
        return isinstance(v, list) and len(v) == 2 and str(v[0]) in nodes and isinstance(v[1], int)
    roots = [i for i,n in nodes.items() if any(s in n['class_type'].lower() for s in ('videocombine', 'savevideo', 'saveimage', 'saveanimated', 'saveaudio')) and modes.get(i, 0) == 0]
    active = set()
    def walk(i):
        if i in active or modes.get(i, 0) in (2, 4):
            return
        active.add(i)
        for v in nodes[i].get('inputs', {}).values():
            if is_link(v):
                walk(str(v[0]))
    if not roots:
        warnings.append('無法辨識輸出節點；以下列出 API prompt 中非停用節點，無法確認全部參與本影片。')
        roots = list(nodes)
    if len(roots) > 1:
        warnings.append('包含多個輸出節點；結果為這些輸出上游聯集，未必全部屬於同一影片。')
    for i in roots:
        walk(i)
    def resolve(v, seen=None):
        seen = set() if seen is None else seen
        if not is_link(v):
            return v
        i = str(v[0])
        if i in seen:
            return {'unresolved_node': i}
        n = nodes[i]
        inp = n.get('inputs', {})
        if n['class_type'].startswith('Primitive') and 'value' in inp:
            return resolve(inp['value'], seen | {i})
        return {'source_node': i, 'output': v[1], 'class_type': n['class_type']}
    def add(category, i, key, val, **extra):
        result[category].append(dict(node_id=i, class_type=nodes[i]['class_type'], field=key, value=val, **extra))
    model_keys = {'ckpt_name', 'unet_name', 'vae_name', 'clip_name', 'clip_name1', 'clip_name2', 'clip_name3', 'model_name', 'model_path', 'diffusion_model'}
    for i in sorted(active, key=lambda x: (len(x), x)):
        n = nodes[i]; inp = n.get('inputs', {}); typ = n['class_type'].lower()
        for k,v in inp.items():
            val = resolve(v)
            category = {'scheduler': 'scheduler', 'sampler_name': 'sampler', 'steps': 'steps', 'step': 'steps', 'seed': 'seed', 'noise_seed': 'seed'}.get(k)
            if category:
                add(category, i, k, str(val) if category == 'seed' and not isinstance(val,dict) else val)
            if k in model_keys and ('load' in typ or 'model' in typ) and 'lora' not in typ:
                add('models', i, k, val)
            if 'lora' in k.lower() and ('name' in k.lower() or k.lower() == 'lora') and isinstance(val,str):
                strengths = {a:resolve(b) for a,b in inp.items() if 'strength' in a or 'weight' in a}
                if strengths and all(isinstance(b,(int,float)) and b == 0 for b in strengths.values()):
                    continue
                add('loras', i, k, val, strengths=strengths)
            if k in ('prompt', 'positive', 'negative', 'text', 'text_g', 'text_l', 'positive_prompt', 'negative_prompt'):
                if isinstance(val,str):
                    add('prompts', i, k, val, source_node=str(v[0]) if is_link(v) else i)
                elif k in ('prompt','text','text_g','text_l','positive_prompt','negative_prompt'):
                    add('prompts', i, k, val)
        if n['class_type'] == 'ManualSigmas':
            add('scheduler', i, 'sigmas', inp.get('sigmas'), note='手動 sigma 序列')
            try:
                count = len([float(x.strip()) for x in inp['sigmas'].split(',')]) - 1
                add('steps', i, 'sigmas', count, note='由 sigma 數量推算，非獨立 steps 欄位')
            except (ValueError, KeyError, TypeError):
                pass
    warnings.append('結果依影片內嵌紀錄及靜態連線推定；自訂節點、動態切換或遭改寫的 metadata 無法證明實際執行。')
    return dict(result, warnings=warnings, output_nodes=roots, active_nodes=sorted(active), excluded_nodes=[dict(node_id=str(n['id']), class_type=n.get('type'), mode=n.get('mode',0)) for n in workflow.get('nodes',[]) if str(n['id']) not in active])
