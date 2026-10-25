"""Capability manifest. Future engines must provide their own validated request schema/compiler."""
CAPABILITIES = [
    {'id': 'video.generate', 'enabled': True, 'providers': ['runninghub', 'comfyui'], 'request_schema': 'Generation', 'output_kinds': ['video', 'audio', 'image']},
    {'id': 'image.generate', 'enabled': True, 'providers': ['runninghub', 'comfyui'], 'output_kinds': ['image']},
    {'id': 'audio.generate', 'enabled': True, 'providers': ['runninghub', 'comfyui'], 'output_kinds': ['audio']},
    {'id': 'text.enhance', 'enabled': True, 'providers': ['chatgpt', 'lmstudio', 'api'], 'output_kinds': ['text']},
]
