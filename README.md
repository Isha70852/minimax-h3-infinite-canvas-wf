# Yukine Palette (雪音畫布)

[繁體中文](README.zh-TW.md) · [Download a release](https://github.com/Isha70852/minimax-h3-infinite-canvas-wf/releases) · [Guide for AI tools (skill)](skills/h3-canvas-api/SKILL.md)

Yukine Palette is an infinite canvas that runs on your own computer. Drop images, videos, sounds and text onto the canvas, connect them with lines, and generate videos, images, music and speech — or make a reference character copy the motion in a video.

The canvas contains no AI models itself. Generation runs on the service you choose: **RunningHub** (cloud), **your own ComfyUI**, or **Google Colab** (free or paid GPUs).

## What it can do

| Area | Features |
|---|---|
| Video | MiniMax H3: text-to-video, reference-to-video, first/last frame, second-pass upscaling, and a "director" that continues from the previous clip |
| Motion transfer | SCAIL-2: animate a reference character with a video's motion, or replace the people in a video with your character |
| Images | Z-Image Turbo, FLUX.2 klein image editing, MOSS Image, Anima |
| Music & speech | YuE2 music, Qwen3 TTS, IndexTTS 2.5, Breeze TTS 2 |
| Custom workflows | Import your own ComfyUI API workflows and choose which fields to edit on the canvas |
| Helpers | AI prompt assistant, media library, media viewer with A/B compare, trimming, audio extraction, storyboard stitching, groups |

The default look is kraft paper. The moon/sun button at the top left switches to the original dark colours (colours only; nothing else changes).

## Quick start (Windows)

**Release ZIP (easiest):** unzip it, install [Python 3.10+](https://www.python.org/) (tick "Add to PATH"), then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Open **http://127.0.0.1:8766**. Later you can just double-click `啟動畫布.cmd`. Node.js is not needed.

**From source:** you also need Node.js 20+.

```powershell
git clone https://github.com/Isha70852/minimax-h3-infinite-canvas-wf.git
cd minimax-h3-infinite-canvas-wf
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Before updating, stop the server (Ctrl+C) and back up the `data/` folder — your projects and settings live there.

## Connect a generation service

Open the gear icon → **Generation sources**. You can add and name several sources; every node can pick which one to use.

### RunningHub (cloud)
1. Import the workflows from `example_workflows/` into your own RunningHub account.
2. Enter your API key and the workflow ID for each feature in settings.
3. Runs use your account's credits; Standard / Plus / Ultra select the machine size.

### Your own ComfyUI
1. Install the nodes and models the workflows need, then start ComfyUI.
2. Enter its address in settings (default `http://127.0.0.1:8188`). No workflow IDs are needed — the canvas builds the full workflow and sends it.
3. Model file names must match your installation (edit them under "Model and LoRA names" in settings).

### Google Colab
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Isha70852/minimax-h3-infinite-canvas-wf/blob/main/colab/Yukine_Palette_Colab.ipynb)

Use `colab/Yukine_Palette_Colab.ipynb`. It works like RunningHub, but **you never upload workflow JSON files**:

1. **Cell 1** – tick the features you want; the needed models are ticked for you. You can change where models are stored (for example Google Drive).
2. **Cell 2** – installs ComfyUI, the nodes for your features, and ComfyUI-Manager (to install more nodes from the ComfyUI web page).
3. **Cell 3** – downloads the models (safe to re-run or extend later).
4. **Cell 4** – starts ComfyUI.
5. **Cell 5** – opens a secure link and shows `H3_API_URL` and a token. Paste both into a Colab source on the canvas.

Every node type (video, image, music, TTS, motion transfer, custom workflows) can use Colab. Before sending, the canvas checks that the required nodes and models exist there. The last cell opens the ComfyUI web page so you can inspect examples or install packages.

> The older `MiniMax_H3_MotionContext_Remote_20261102.ipynb` keeps its manual generation panel; its "import two JSON files" step is now optional.

## Basic use

1. Create a project, then **double-click empty space** (or right-click) to add nodes. Drag files onto the canvas or add them from the library.
2. Connect media nodes to a generation node, write a prompt, adjust settings and press Generate.
3. Results appear on the node and in "Project outputs" on the right. Running jobs can be stopped.

Tips:
- **Node templates** save a node's settings (not its media or text) and can be applied to new nodes automatically.
- **Director**: to continue a video clip by clip, press "Generate this segment" in the director. It feeds the previous clip in as picture and sound context. The video node's own Generate button does not continue.
- **Groups**: Shift-select nodes, then press Group on the left. Groups can be moved, arranged and collapsed.
- **`@` in prompts** inserts a marker for a connected media item.
- **Noise seed**: fix it in the advanced settings to reproduce a result; history lets you reuse a seed.

## Feature notes

### Video (MiniMax H3)
- All video modes share one workflow. On RunningHub you only need one "unified video workflow ID" (import `MiniMax_H3_一採保留_二採Latent放大_無限畫布.json`).
- "Second pass" gives a higher resolution; "also keep first pass" saves both versions. Output is 24 fps.
- Image roles must match the mode: first frame → first, last frame → last, reference image → reference.
- Uploaded videos are converted to 24 fps. There is no length limit; each workflow trims or splits what it needs.

### Motion transfer / character replacement (SCAIL-2)
Right-click → "Motion transfer / character replacement", then connect one **reference character image** and one **motion video**.

- **Motion transfer** keeps the reference image's background and animates the character.
- **Character replacement** keeps the video's background and swaps the person for your character.
- **Length**: one segment is up to 81 frames. "Long video" splits the clip into chained segments (up to 6) and keeps the original audio.
- The reference image is padded by default so tall character art doesn't lose its head.
- "Person to track in the video" describes the person in the video (e.g. `person`). To replace one person, set "max people" to 1.
- **Replacing several people**: put all characters side by side in one reference image, in the same order as the people in the video (earlier appearance first, then left to right), set "max people" to that number and sorting to `left_to_right`. Videos with cuts can confuse identities; use "start frame" to begin where everyone is visible.
- The defaults are the fast 6-step recipe and rarely need changing.

### Music and speech
- YuE2 makes songs from lyrics or covers; Qwen3, IndexTTS 2.5 and Breeze TTS 2 clone or design voices.
- IndexTTS 2.5 accepts an optional emotion reference; its emotion weight uses ComfyUI's built-in Float node.
- Breeze TTS 2 has "download missing model" on by default, so the first run downloads the weights. Turn it off if the files are already in place.

### Custom workflows
Use **Workflows** on the left to import a ComfyUI **API-format** JSON:
1. Pick a category and the output node.
2. Tick the fields you want to edit on the canvas (text, numbers, switches, menus, models, seed, media).
3. For several media inputs use a "media group"; loader nodes are duplicated and wired to match how many you connect.
4. Use "Check mapping / graph" before generating.

Node IDs can change when you replace the JSON, so re-check the mapping. Workflows and model lists are stored locally only.

### Media viewer and comparison
"Media viewer" (top left) browses everything the canvas generated and can add folders from your computer (files are never copied or moved). Click an item to see its prompt and settings; pick two images or videos to compare side by side or with a slider.

## AI prompt templates

- **Built-in templates** ship with the app in `backend/builtin_prompts/`.
- **Your templates** are stored in `data/prompts/`, which is never committed or packaged.
- Editing a built-in template saves your own copy; restoring the original text brings back the built-in. Deleting a built-in only hides it.
- To share a template with everyone, add it to `backend/builtin_prompts/`.

## Let AI tools drive the canvas

Turn on **Settings → External AI API**, copy the token, and give the [skill](skills/h3-canvas-api/SKILL.md), the address `http://127.0.0.1:8766/api/automation/v1` and the token to an AI tool you trust (such as Claude Code or Codex). It can then create projects, upload media, write prompts and start generations.

- The API never reveals your service keys and cannot run system commands.
- Keep it on localhost; do not expose it to the internet.
- Avoid editing the same project in the browser and through the API at the same time.

## Files and data

| Path | Contents |
|---|---|
| `src/`, `backend/` | Front end (React) and back end (FastAPI) |
| `workflows/` | The workflows the canvas runs and their field mappings |
| `example_workflows/` | Shareable workflows to import into ComfyUI / RunningHub |
| `colab/` | Google Colab notebooks |
| `skills/` | Guides for AI tools |
| `data/` | **Your** projects, media, settings, keys and templates (never share it) |

### Advanced: change settings the UI doesn't expose
To swap a model or fixed value that the UI does not offer, back up and edit the matching JSON in `workflows/`, keep node IDs and links unchanged, restart the server and check the preview. `workflows/*_registry.json` lists which JSON each feature uses. Editing `example_workflows/` does not affect the canvas.

## License and thanks

The code in this project is under the [MIT License](LICENSE). MIT covers this project's code only — **not** the models, nodes or generated content — and no model weights are distributed here. Check each model's license before use (several are non-commercial). Third-party notices: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and `licenses/`.

**Models** (summary only; the official pages are authoritative)

| Model | License in short |
|---|---|
| [MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE) | Community license with territory, commercial-use, attribution and use restrictions |
| [SCAIL-2](https://huggingface.co/Comfy-Org/SCAIL-2) (built on Wan 2.1), [SAM 3.1](https://huggingface.co/Comfy-Org/sam3.1) | See each model card |
| [Z-Image Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo), [MOSS Image](https://openmoss.ai/MOSS-Image/), [Qwen3-TTS](https://arxiv.org/abs/2601.15621) | Apache-2.0 |
| [FLUX.2 klein](https://help.bfl.ai/articles/7108141705-can-i-run-or-fine-tune-flux-2-klein-locally) | 4B Apache-2.0; 9B non-commercial |
| [Anima](https://huggingface.co/circlestone-labs/Anima) | Non-commercial license |
| [YuE2](https://huggingface.co/m-a-p/YuE2-3B/blob/main/LICENSE) | Weights CC BY-NC 4.0 (non-commercial) |
| [Breeze TTS 2](https://huggingface.co/BreezeBlue/Breeze-TTS-2) | Code Apache-2.0; weights and outputs research / non-commercial |
| [IndexTTS 2.5](https://huggingface.co/IndexTeam/IndexTTS-2.5) | Bilibili Model Use License Agreement |
| Speed-up LoRAs, quantized files, encoders, VAEs | Their own upstream licenses |

**Thanks to**

- **Model teams**: MiniMax, the SCAIL-2 and Wan teams, Meta SAM, Tongyi Z-Image, Black Forest Labs, OpenMOSS, CircleStone Labs, M-A-P (YuE2), Qwen, BreezeBlue, Bilibili IndexTeam.
- **ComfyUI and Comfy-Org** for the engine, official nodes and model packaging.
- **Node and model authors**:
  [T8](https://github.com/T8mars/comfyui-minimax-h3-audio-T8) (H3 audio nodes, [IndexTTS 2.5 nodes](https://github.com/T8mars/comfyui-indextts25-t8), [4-step turbo LoRA](https://huggingface.co/t8star/minimax-h3-4step-turbo-loras-comfyui-exp)),
  [Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context),
  [Kijai / KJNodes](https://github.com/kijai/ComfyUI-KJNodes),
  [VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite),
  [lightx2v](https://huggingface.co/lightx2v/Minimax-h3-Turbo),
  [LBH Latent Upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler),
  [Qwen-TTS nodes](https://github.com/flybirdxx/ComfyUI-Qwen-TTS),
  [Breeze TTS 2 nodes](https://github.com/Saganaki22/ComfyUI-Breeze-TTS-2),
  [ListHelper](https://github.com/dseditor/ComfyUI-ListHelper),
  [Goohai Tools](https://github.com/goohai/Goohaitools-comfyui),
  [MieNodes](https://github.com/MieMieeeee/ComfyUI-MieNodes),
  [Pika H3 Flex](https://huggingface.co/Pika-Labs/Pika-H3-Flex).
- **Services and open source**: [RunningHub](https://www.runninghub.ai/), React, Vite, XYFlow, FastAPI, Uvicorn, Lucide, Mediabunny.
