import pytest
from backend.workflow import Generation, compile_workflow, LORAS, MODELS


def asset(id, kind='image'):
    return {'id': id, 'filename': id + '.png', 'kind': kind, 'name': id}


def test_defaults_and_prune_examples():
    result = compile_workflow(Generation(prompt='A rainy city'), {}, seed=18446744073709551615)
    g = result['workflow']
    assert g['303']['inputs']['unet_name'] == MODELS[0]
    assert g['304']['inputs']['lora_name'] == LORAS[0]
    assert g['115']['inputs']['megapixels'] == .7
    assert g['132']['inputs']['value'] == 15
    assert g['124']['inputs']['steps'] == 8
    assert g['124']['inputs']['scheduler'] == 'beta'
    assert g['123']['inputs']['sampler_name'] == 'euler'
    assert g['148']['inputs']['model'] == ['304', 0]
    assert g['126']['inputs']['model'] == ['297', 0]
    assert g['166']['inputs']['task_type'] == 'T2VA'
    assert not any(n['class_type'] in ('LoadImage', 'LoadAudio', 'LoadVideo', '忽略多组孤海') for n in g.values())
    assert result['seed'] == '18446744073709551615'


@pytest.mark.parametrize('size,heads,chunks', [(1, 4, 2), (1.4, 4, 2), (1.5, 8, 4), (2, 8, 4)])
def test_shift_and_memory_exact_order(size, heads, chunks):
    g = compile_workflow(Generation(prompt='test', lora=LORAS[1], megapixels=size, low_vram_enabled=True), {})['workflow']
    assert g['158']['inputs'] == {'model': ['304', 0], 'shift_video': 6., 'shift_audio': 3.}
    assert g['148']['inputs']['model'] == ['158', 0]
    assert g['297']['inputs']['model'] == ['148', 0]
    assert g['229'] == {'class_type': 'MiniMaxLowVRAMAttention', 'inputs': {'model': ['297', 0], 'head_chunks': heads}}
    assert g['230']['inputs'] == {'model': ['229', 0], 'chunks': chunks, 'seq_threshold': 4096}
    assert g['124']['inputs']['model'] == g['126']['inputs']['model'] == ['230', 0]


def test_memory_custom():
    g = compile_workflow(Generation(prompt='test', megapixels=1.5, low_vram_enabled=True, head_chunks=12, chunks=6), {})['workflow']
    assert g['229']['inputs']['head_chunks'] == 12
    assert g['230']['inputs']['chunks'] == 6
    assert '158' not in g


def test_references_and_aliases_are_per_kind_and_ordered():
    assets = {'a': asset('a'), 'b': asset('b'), 'v': asset('v', 'video'), 's': asset('s', 'audio')}
    spec = Generation(prompt='<Subject 1> 是 @圖片2 的金髮女性。@影片1 @聲音1', mode='Ref2VA', references=[{'asset_id': i} for i in ('s', 'b', 'v', 'a')])
    result = compile_workflow(spec, assets, {'a': 'remote/a.png', 'b': 'remote/b.png', 's': 's.wav', 'v': 'v.mp4'})
    assert result['prompt'] == '<Subject 1> 是 <Picture 2> 的金髮女性。<Video 1> <Audio 1>'
    assert [(r['id'], r['tag']) for r in result['mapping']] == [('b', '<Picture 1>'), ('a', '<Picture 2>'), ('v', '<Video 1>'), ('s', '<Audio 1>')]
    g = result['workflow']
    c = g['166']['inputs']
    assert g[c['ref_images.ref_image_1'][0]]['inputs']['image'] == 'remote/a.png'
    assert g[c['ref_videos.ref_video_0'][0]]['class_type'] == 'GetVideoComponents'
    assert not any(k.startswith('ref_video_audios') for k in c)
    assert spec.prompt.startswith('<Subject 1> 是 @圖片2')


def test_first_last_order_is_not_connection_order():
    spec = Generation(prompt='@圖片1 moves toward @圖片2', mode='FL2VA', references=[{'asset_id': 'last', 'role': 'last'}, {'asset_id': 'first', 'role': 'first'}])
    result = compile_workflow(spec, {'first': asset('first'), 'last': asset('last')})
    g = result['workflow']; c = g['166']['inputs']
    assert g[c['first_frame'][0]]['inputs']['image'] == 'first.png'
    assert g[c['last_frame'][0]]['inputs']['image'] == 'last.png'
    assert result['mapping'][0]['id'] == 'first'
    assert not any(k.startswith('ref_images.') for k in c)


@pytest.mark.parametrize('kwargs', [
    {'mode': 'FL2VA'}, {'mode': 'Ref2VA'}, {'prompt': '@圖片1'}, {'prompt': '<Picture 1>'},
    {'aspect_ratio': 'bad'},
    {'references': [{'asset_id': 'x'}]},
])
def test_invalid_inputs_fail_before_submit(kwargs):
    with pytest.raises(ValueError):
        compile_workflow(Generation(**{'prompt': 'test', **kwargs}), {'x': asset('x')})


def test_many_images_alias_ten_is_not_alias_one():
    assets = {str(i): asset(str(i)) for i in range(9)}
    spec = Generation(prompt='@圖片10', mode='Ref2VA', references=[{'asset_id': i} for i in assets])
    with pytest.raises(ValueError, match='圖片10'):
        compile_workflow(spec, assets)


def test_copied_asset_retains_both_reference_connections():
    spec = Generation(prompt='@圖片1 and @圖片2', mode='Ref2VA', references=[{'asset_id': 'same'}, {'asset_id': 'same'}])
    result = compile_workflow(spec, {'same': asset('same')})
    assert result['prompt'] == '<Picture 1> and <Picture 2>'
    graph = result['workflow']
    inputs = graph['166']['inputs']
    first = inputs['ref_images.ref_image_0']
    second = inputs['ref_images.ref_image_1']
    assert first != second
    assert graph[first[0]]['inputs']['image'] == graph[second[0]]['inputs']['image'] == 'same.png'


def test_same_image_can_be_first_and_last():
    spec = Generation(prompt='A seamless loop', mode='FL2VA', references=[{'asset_id': 'same', 'role': 'first'}, {'asset_id': 'same', 'role': 'last'}])
    result = compile_workflow(spec, {'same': asset('same')})
    assert [r['tag'] for r in result['mapping']] == ['<Picture 1>', '<Picture 2>']


def test_custom_parameters_and_disabled_nodes():
    g = compile_workflow(Generation(prompt='test', model='custom.safetensors', lora='my-lora.safetensors',
        lora_enabled=False, shift_enabled=True, low_vram_enabled=False, megapixels=2,
        steps=12, sampler='dpmpp_2m', scheduler='normal'), {})['workflow']
    assert g['303']['inputs']['unet_name'] == 'custom.safetensors'
    assert g['148']['inputs']['model'] == ['303', 0]
    assert not any(i in g for i in ('304', '158', '229', '230'))
    assert g['124']['inputs']['steps'] == 12
    assert g['124']['inputs']['scheduler'] == 'normal'
    assert g['123']['inputs']['sampler_name'] == 'dpmpp_2m'
    g = compile_workflow(Generation(prompt='test', model='custom.safetensors', lora='my-lora.safetensors',
        shift_enabled=True, shift_video=4, shift_audio=2), {})['workflow']
    assert g['304']['inputs']['lora_name'] == 'my-lora.safetensors'
    assert g['158']['inputs']['shift_video'] == 4
    assert g['158']['inputs']['shift_audio'] == 2
