# MiniMax H3 Infinite Canvas · Wizard Forest Studio

[繁體中文](README.zh-TW.md) · [Releases](https://github.com/Isha70852/minimax-h3-infinite-canvas-wf/releases) · [API skill](skills/h3-canvas-api/SKILL.md)

A local infinite canvas for images, video, music, speech and prompt writing, powered by **RunningHub or your local ComfyUI**. Model weights and generation servers are not included.

## Features

- Pan/zoom canvas, minimap, resizable nodes, connected references and generation history.
- MiniMax H3 text/reference/first-last-frame video generation; director segments with MP4 motion context (frames and audio from the preceding clip).
- MOSS Image, FLUX.2 klein editing, Z-Image Turbo, Anima; YuE2 music, Qwen3 TTS, IndexTTS 2.5 and Breeze TTS 2.
- Shared assets and project-specific media, recycling, previews, media trimming, audio extraction and labeled storyboard image composition.
- AI prompt drafts with optional previous AI/manual scene context, editable templates and streaming output.
- Opt-in token-protected automation API for coding agents; discover workflows and schemas rather than hardcoding model inputs.

## Windows quick start

**Release ZIP:** extract into a writable folder. Install Python 3.10+ with `python` available in PATH, then run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Open **http://127.0.0.1:8766**. Alternatively double-click `啟動畫布.cmd` after installing the runtime. The release includes the built frontend; Node.js is not needed to run it.

**From source:** install Python 3.10+ and Node.js 20 LTS or newer, then:

```powershell
git clone https://github.com/Isha70852/minimax-h3-infinite-canvas-wf.git
cd minimax-h3-infinite-canvas-wf
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

Dependencies are installed in this folder (`.venv`, `node_modules`, local caches). Stop the server with Ctrl+C before updating. Back up `data/`; updates must not replace it with another user's data.

## Connect a generation backend

**RunningHub:** import an appropriate public workflow from `example_workflows/` into your own account, resolve missing models/nodes there, then enter your API key and your own workflow ID in Settings. Set IDs separately for normal video, MP4 motion context, image and audio workflows. Shared files contain no personal workflow IDs or keys. Standard/Plus/Ultra select the requested provider tier; generation consumes your service credits.

**Local ComfyUI:** install the required models and custom nodes separately. Start ComfyUI and enter its URL (default `http://127.0.0.1:8188`). Workflow IDs are not required locally. The canvas submits API-format graphs, uploads references and reads generated results. Checkpoint filenames must match the server.

Create a project, double-click empty canvas to add nodes, upload media and connect it to a generation node. Select a function, write a prompt, adjust parameters and submit. Configure default video parameters and prompt providers in Settings. Input files in the public workflows are intentionally empty; replace them before running in ComfyUI/RunningHub.

For continuation, add segments to a director, generate the first, then the next. Each segment may use different prompts/materials. The preceding MP4 supplies motion context; no latent transfer is needed. Overlap trimming can shorten the final duration. Concatenation is a separate editing step.

## External AI / automation

Enable **Settings → External AI operation API** and copy the one-time token. Give your coding agent [this skill](skills/h3-canvas-api/SKILL.md), the local service URL and the token. Base: `http://127.0.0.1:8766/api/automation/v1`; use `Authorization: Bearer TOKEN`.

The API supports discovery, project read/write, image/video/audio uploads, optional AI drafting, generation submission and status/results. It can chain motion-context segments. It does not expose provider credentials or shell execution. Disabling the interface blocks new requests, not already-submitted jobs. Avoid simultaneous browser/API edits to the same project; reload afterward. Internal browser endpoints are separate from this opt-in interface. Keep the server on localhost; it is not a hardened public multi-user service.

## Repository layout and private storage

| Path | Purpose |
|---|---|
| `src/`, `backend/` | React/Vite UI and FastAPI service |
| `workflow_template.json`, `workflows/` | Sanitized runtime graphs and parameter/node registries; preserve compiler mappings |
| `example_workflows/` | Public UI/API exports for import; node numbers may differ from runtime templates |
| `skills/h3-canvas-api/` | Canvas automation skill |
| `colab/`, `skills/minimax-h3-remote-skill/` | **Independent** Google Colab H3 remote tool and its agent skill; not the canvas backend |
| `data/` | Local SQLite settings/projects/jobs, media, outputs and authentication state; NEVER publish |

The Colab notebook can be opened in Google Colab and used with its corresponding remote skill. Configure its runtime and credentials there; it does not automatically connect to the canvas.


## Node templates and director

Configure a video, image, music or TTS node, then expand **Node templates** to save its parameters with a name and tags. Set one default per category and manage presets from the left canvas menu. New nodes use the default; existing nodes can select a preset manually. Templates exclude scene text and media and stay in local data.

**For continuation, click Generate this segment in the director. Generate video on an individual node does not automatically continue the previous segment.** API motion-context submissions create/update a director automatically; reload the project to see it.

## License and acknowledgements

Project code uses the repository's [MIT License](LICENSE). This does **not** relicense model weights, custom nodes, dependencies or outputs. Summaries below reflect upstream pages checked on 2026-10-25; exact checkpoint licenses and provider terms prevail. No weights are distributed. See [third-party notices](THIRD_PARTY_NOTICES.md) and `licenses/` for dependency notices.

Thank you to the model teams, ComfyUI/custom-node maintainers, RunningHub, and the open-source UI/media community that make this project possible.

| Component / model | License summary / 授權摘要 | Source |
|---|---|---|
| MiniMax H3 | MiniMax H3 Community License; territory, commercial-use, attribution and acceptable-use conditions apply. Not MIT/Apache. / 社群授權，含地區、商用、標示及使用限制。 | [License](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE) |
| MOSS-Image | Apache-2.0 model weights; retain required notices. / 權重 Apache-2.0，保留必要聲明。 | [OpenMOSS](https://openmoss.ai/MOSS-Image/) |
| FLUX.2 klein | 4B: Apache-2.0; 9B: FLUX Non-Commercial License, separate commercial permission may be needed. / 4B 與 9B 授權不同。 | [Black Forest Labs](https://help.bfl.ai/articles/7108141705-can-i-run-or-fine-tune-flux-2-klein-locally) |
| Z-Image-Turbo | Apache-2.0. | [Tongyi-MAI](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo) |
| Anima | Current upstream lists CircleStone Labs Non-Commercial License; verify the exact checkpoint/version (including aesthetic derivatives). / 目前上游列非商用授權，請核對實際版本及衍生權重。 | [CircleStone Labs](https://huggingface.co/circlestone-labs/Anima) |
| YuE2 | Weights: CC BY-NC 4.0 in the linked license; additional permissions, if any, must be checked for the exact release. / 權重為非商用授權；額外許可依實際版本確認。 | [MAP license](https://huggingface.co/m-a-p/YuE2-3B/blob/main/LICENSE) |
| Qwen3-TTS | Apache-2.0; retain license/notice requirements. | [Qwen report](https://arxiv.org/abs/2601.15621) |
| Breeze TTS 2 | Code Apache-2.0; weights, derivatives and self-hosted outputs subject to research/non-commercial terms. / 程式碼與權重授權不同，自架輸出亦受限制。 | [BreezeBlue](https://huggingface.co/BreezeBlue/Breeze-TTS-2) |
| IndexTTS 2.5 | Bilibili Model Use License Agreement; not a blanket Apache/MIT grant for weights. / 權重依 Bilibili 模型使用協議。 | [IndexTeam](https://huggingface.co/IndexTeam/IndexTTS-2.5) |
| Qwen encoders, VAEs, LoRAs, quantizations | Separate upstream/derivative licenses apply; availability in a workflow is not permission to redistribute weights. / 各別元件及衍生權重須遵守其原始授權。 | Respective model cards / 各模型卡 |
| React, Vite, XYFlow, FastAPI, Uvicorn, Lucide | MIT / ISC / BSD-style licenses by package; retain supplied notices. / 各套件依自身授權。 | [React](https://github.com/facebook/react), [Vite](https://github.com/vitejs/vite), [XYFlow](https://github.com/xyflow/xyflow), [FastAPI](https://github.com/fastapi/fastapi), [Uvicorn](https://github.com/encode/uvicorn), [Lucide](https://github.com/lucide-icons/lucide) |
| Mediabunny | MPL-2.0; unmodified dependency, preserve notices and applicable source obligations. / 未修改的 MPL-2.0 依賴，保留聲明與適用原始碼義務。 | [Source](https://github.com/Vanilagy/mediabunny/tree/v1.62.1) |
| ComfyUI and custom-node authors | Separate upstream licenses; not bundled as an installed engine. / 外部引擎與節點各自授權，未隨本專案安裝包散布。 | [ComfyUI](https://github.com/Comfy-Org/ComfyUI), [RunningHub](https://www.runninghub.ai/) |

Special thanks:

- [KJ / ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)
- [T8 / comfyui-minimax-h3-audio-T8](https://github.com/T8mars/comfyui-minimax-h3-audio-T8)
- [Motion Context / ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)
