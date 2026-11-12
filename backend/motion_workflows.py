"""Motion transfer / character replacement (SCAIL-2) built from official ComfyUI nodes.

Single-segment requests use the registry template as-is. Long videos are unrolled
into chained 81-frame chunks (76-frame stride, 5-frame anchor) inside one API graph,
following ComfyUI's official "Character Replacement (SCAIL-2 Extend)" blueprint, so
no loop custom nodes are needed on ComfyUI, RunningHub or Colab.
"""
import copy
import json
import math
import re
import subprocess
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from .workflow import ROOT, Reference

REGISTRY = json.loads((ROOT / 'workflows/motion_registry.json').read_text(encoding='utf-8'))
MEDIA_KINDS = ('image', 'video')


class MotionGeneration(BaseModel):
    provider_profile_id: str | None = None
    kind: Literal['motion'] = 'motion'
    provider: Literal['comfyui', 'runninghub', 'colab'] = 'comfyui'
    workflow: str = 'scail2'
    values: dict = Field(default_factory=dict)
    media_assets: dict[str, str] = Field(default_factory=dict)
    text_sources: dict[str, str] = Field(default_factory=dict)

    @property
    def references(self):
        return [Reference(asset_id=id) for id in dict.fromkeys(self.media_assets.values()) if id]


def catalog():
    return [{'id': key, 'name': d['name'], 'version': d['version'],
             'fields': [{k: v for k, v in f.items() if k not in ('node', 'input')} for f in d['fields']]}
            for key, d in REGISTRY.items()]


def definition(spec):
    if spec.workflow not in REGISTRY: raise ValueError('不支援的動作遷移工作流。')
    return REGISTRY[spec.workflow]


def resolve_text(spec, project):
    fields = {f['key']: f for f in definition(spec)['fields']}
    values = dict(spec.values)
    for key, id in spec.text_sources.items():
        node = next((n for n in project.get('nodes', []) if n['id'] == id), None)
        if key not in fields or fields[key]['type'] != 'text' or not node or node.get('data', {}).get('kind') != 'text':
            raise ValueError('動作遷移提示詞需要連接此專案的文字節點。')
        values[key] = node['data'].get('text', '')
    return spec.model_copy(update={'values': values, 'text_sources': {}})


@lru_cache(maxsize=256)
def _probe(path_text, size, mtime):
    """Frame count and audio presence of a local (already normalized) video."""
    import imageio_ffmpeg
    import os
    flags = {'creationflags': 0x08000000} if os.name == 'nt' else {}
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    out = subprocess.run([ffmpeg, '-hide_banner', '-i', path_text, '-map', '0:v:0', '-c', 'copy', '-f', 'null', '-'],
                         capture_output=True, timeout=120, **flags).stderr.decode('utf-8', errors='replace')
    frames = [int(x) for x in re.findall(r'frame=\s*(\d+)', out)]
    fps = re.search(r'(\d+(?:\.\d+)?) fps', out)
    if not frames:
        duration = re.search(r'Duration: (\d+):(\d+):(\d+(?:\.\d+)?)', out)
        if not duration or not fps: raise ValueError('無法讀取動作影片的幀數。')
        seconds = int(duration[1]) * 3600 + int(duration[2]) * 60 + float(duration[3])
        frames = [int(seconds * float(fps[1]))]
    return {'frames': frames[-1], 'audio': bool(re.search(r'Stream #\d+:\d+.*Audio:', out))}


def probe_video(asset):
    from .storage import MEDIA
    path = MEDIA / asset['filename']
    if not path.is_file(): raise ValueError('找不到動作影片檔案，請重新匯入素材。')
    stat = path.stat()
    return _probe(str(path), stat.st_size, stat.st_mtime)


def align(frames):
    """Wan latents need 4n+1 frames."""
    return ((frames - 1) // 4) * 4 + 1


def plan_segments(total, length_mode, frames, max_segments, chunk=81, overlap=5):
    """Return [(skip_first_frames, length)] in source frames."""
    if total < 9: raise ValueError('動作影片太短，至少需要 9 幀。')
    if length_mode == 'single':
        return [(0, align(min(frames, total)))]
    stride = chunk - overlap
    plan = [(0, align(min(chunk, total)))]
    while len(plan) < max_segments:
        start = stride * len(plan)
        remaining = total - start
        if remaining < 9: break
        plan.append((start, align(min(chunk, remaining))))
    return plan


def _validate(f, value):
    label = f['label']
    if f['type'] in ('text', 'string', 'select'):
        if not isinstance(value, str) or len(value) > 100000 or (not value.strip() and not f.get('optional')):
            raise ValueError(f'請填寫 {label}。')
        if f['type'] == 'select' and value not in f['options']: raise ValueError(f'不支援的 {label}。')
        return value
    if f['type'] == 'boolean':
        if not isinstance(value, bool): raise ValueError(f'{label} 必須為 true 或 false。')
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not f['min'] <= value <= f['max']:
        raise ValueError(f'{label} 超出範圍。')
    if f['type'] == 'integer':
        if value != int(value): raise ValueError(f'{label} 必須為整數。')
        value = int(value)
    return value


def compile_motion(spec, assets, filenames=None, seed=0):
    entry = definition(spec)
    if spec.text_sources: raise ValueError('請先解析文字連線。')
    fields = {f['key']: f for f in entry['fields']}
    if set(spec.values) - fields.keys(): raise ValueError('動作遷移包含不支援的參數。')
    if set(spec.media_assets) - {k for k, f in fields.items() if f['type'] in MEDIA_KINDS}: raise ValueError('此功能不接受指定的素材輸入。')
    graph = json.loads((ROOT / 'workflows' / entry['template']).read_text(encoding='utf-8-sig'))
    values, mapping, media = {}, [], {}
    for key, f in fields.items():
        if f['type'] in MEDIA_KINDS:
            id = spec.media_assets.get(key)
            asset = assets.get(id)
            if not asset or asset.get('kind') != f['type']: raise ValueError(f"請選擇或連接 {f['label']}。")
            media[key] = asset
            values[key] = (filenames or {}).get(id, asset['filename'])
            mapping.append({'id': id, 'name': asset['name'], 'field': key})
        else:
            values[key] = _validate(f, spec.values.get(key, f['default']))
        if f.get('node'):
            node = graph.get(f['node'])
            if not node or f['input'] not in node['inputs']: raise ValueError(f'動作遷移映射已失效：{key}')
            node['inputs'][f['input']] = values[key]
    width, height = values['width'], values['height']
    if width % 32 or height % 32: raise ValueError('寬高需為 32 的倍數。')
    N = entry['nodes']
    run_seed = seed if values['seed'] < 0 else values['seed']
    replace = values['mode'] == 'replace'
    if values['reference_fit'] == 'crop':
        graph[N['reference_scale']]['inputs'].update(width=width, height=height)
    else:
        # Keep the whole character: a centre crop of a portrait reference into a
        # landscape frame removes the head, so the model never sees the face.
        graph[N['reference_scale']] = {'class_type': 'ResizeAndPadImage', 'inputs': {
            'image': graph[N['reference_scale']]['inputs']['image'], 'target_width': width, 'target_height': height,
            'padding_color': values['reference_fit'][4:], 'interpolation': 'area'}, '_meta': {'title': 'Fit Reference'}}
    for id in (N['reference_track'], N['drive_track']):
        graph[id]['inputs'].update(detection_threshold=values['detection_threshold'], max_objects=values['max_objects'], detect_interval=values['detect_interval'])
    graph[N['mask']]['inputs']['replacement_mode'] = replace
    graph[N['conditioning']]['inputs']['replacement_mode'] = replace
    graph[N['drive_load']]['inputs'].update(custom_width=width, custom_height=height, force_rate=values['drive_fps'])
    graph[N['sampler']]['inputs']['noise_seed'] = run_seed
    info = probe_video(media['drive_video'])
    # Uploads are normalized to 24 fps; force_rate resamples, so count frames at the new rate.
    total = info['frames'] if not values['drive_fps'] else int(info['frames'] * values['drive_fps'] / 24)
    if values['start_frame'] >= total - 8: raise ValueError('起始幀超過動作影片長度。')
    plan = plan_segments(total - values['start_frame'], values['length_mode'], values['frames'], values['max_segments'],
                         entry['chunk_frames'], entry['overlap_frames'])
    stride = entry['segment_stride']
    segment = {id: copy.deepcopy(graph[id]) for id in entry['segment_nodes']}
    outputs = []
    previous_out = None
    for index, (skip, length) in enumerate(plan):
        offset = stride * index
        ids = {id: str(int(id) + offset) for id in segment}
        if index:
            for id, node in segment.items():
                clone = copy.deepcopy(node)
                for name, value in clone['inputs'].items():
                    if isinstance(value, list) and len(value) == 2 and value[0] in ids:
                        clone['inputs'][name] = [ids[value[0]], value[1]]
                graph[ids[id]] = clone
        graph[ids[N['drive_load']]]['inputs'].update(skip_first_frames=values['start_frame'] + skip, frame_load_cap=length)
        cond = graph[ids[N['conditioning']]]['inputs']
        cond['length'] = length
        decoded = [ids[N['decode']], 0]
        if not index:
            outputs.append(decoded)
            previous_out = decoded
            continue
        # Each chunk already loads its own pose slice, so video_frame_offset stays 0
        # (the official Extend blueprint does the same); only the anchor frames chain.
        cond['previous_frames'] = previous_out
        trim, anchor, color = (str(int(N['decode']) + offset + i) for i in (1, 2, 3))
        graph[trim] = {'class_type': 'ImageFromBatch', 'inputs': {'image': decoded, 'batch_index': entry['overlap_frames'], 'length': 4096}, '_meta': {'title': f'Trim overlap {index + 1}'}}
        current = [trim, 0]
        if values['color_match']:
            graph[anchor] = {'class_type': 'ImageFromBatch', 'inputs': {'image': previous_out, 'batch_index': -1, 'length': 1}, '_meta': {'title': f'Color anchor {index + 1}'}}
            graph[color] = {'class_type': 'ColorTransfer', 'inputs': {'image_target': current, 'image_ref': [anchor, 0], 'method': 'reinhard_lab', 'source_stats': 'per_frame', 'strength': 1.0}, '_meta': {'title': f'Color match {index + 1}'}}
            current = [color, 0]
        outputs.append(current)
        previous_out = current
    out = graph[N['output']]['inputs']
    if len(outputs) > 1:
        graph['300'] = {'class_type': 'BatchImagesNode', 'inputs': {f'images.image{i}': link for i, link in enumerate(outputs)}, '_meta': {'title': 'Join segments'}}
        out['images'] = ['300', 0]
        # The first chunk only carries its own audio span; load the full track instead.
        if values['keep_audio'] and info['audio']:
            graph['401'] = {'class_type': 'LoadAudio', 'inputs': {'audio': values['drive_video']}, '_meta': {'title': 'Drive Audio'}}
            out['audio'] = ['401', 0]
            if values['start_frame']:
                graph['402'] = {'class_type': 'TrimAudioDuration', 'inputs': {'audio': ['401', 0], 'start_index': round(values['start_frame'] / (values['drive_fps'] or 24), 3), 'duration': 3600.0}, '_meta': {'title': 'Align Drive Audio'}}
                out['audio'] = ['402', 0]
    if not values['keep_audio'] or not info['audio']:
        out.pop('audio', None)
    elif len(outputs) == 1:
        out['audio'] = [N['drive_load'], 2]
    out['filename_prefix'] = f'H3Canvas/motion_{run_seed}'
    for node in graph.values():
        for value in node['inputs'].values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str) and value[0] not in graph:
                raise ValueError('動作遷移工作流有遺失的節點連線。')
    return {'workflow': graph, 'prompt': values['prompt'], 'mapping': mapping, 'seed': str(run_seed),
            'output_nodes': [N['output']], 'workflow_version': entry['version'],
            'segments': [{'skip_first_frames': values['start_frame'] + s, 'length': l} for s, l in plan], 'source_frames': info['frames']}
