"""Capability manifest. Future engines must provide their own validated request schema/compiler."""
CAPABILITIES = [
    {'id': 'video.generate', 'enabled': True, 'providers': ['runninghub', 'comfyui', 'colab'], 'request_schema': 'Generation', 'output_kinds': ['video', 'audio', 'image']},
    {'id': 'image.generate', 'enabled': True, 'providers': ['runninghub', 'comfyui', 'colab'], 'output_kinds': ['image']},
    {'id': 'audio.generate', 'enabled': True, 'providers': ['runninghub', 'comfyui', 'colab'], 'output_kinds': ['audio']},
    {'id': 'motion.generate', 'enabled': True, 'providers': ['runninghub', 'comfyui', 'colab'], 'request_schema': 'MotionGeneration', 'output_kinds': ['video']},
    {'id': 'text.enhance', 'enabled': True, 'providers': ['chatgpt', 'lmstudio', 'api'], 'output_kinds': ['text']},
]
