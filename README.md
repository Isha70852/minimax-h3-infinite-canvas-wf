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

## Noise seeds and AI prompt files

Video advanced settings accept a **Noise seed**; choose `randomize` for a new seed on each submission, or `fixed` and enter a seed to reuse it. Results, history and directors show the actual seed, with actions to reuse it. The API accepts `spec.noise_seed` as a decimal string (0–18446744073709551615) and returns `seed` as a string to preserve integer precision. Equal seeds do not guarantee equal results across models, settings or environments. RH coins apply only to RunningHub. Local ComfyUI needs no billing fields; its displayed elapsed time includes queueing and output storage.

`prompts/` supplies AI writing templates. Each UTF-8 `.md` or `.txt` file becomes one template: its filename stem is the display name and its full text is the instruction content. Included examples cover H3, images, music and TTS; choose one appropriate to your task. These instructions are separate from generation workflow graphs and node parameter presets (which remain in local data).

**Save settings and templates** writes edits to `prompts/`; changing a template name renames its file. Previous content from edits/deletions is retained in `prompts/.trash/`, excluded from Git and releases. You may also edit files directly and reopen settings/the prompt assistant to reload them. A stale save is rejected if files changed externally. The default selection remains in local settings. The old code-bundled template is removed and SQLite templates are no longer the source; historical draft snapshots remain intact. Current prompt files are published in releases, so keep credentials and private scene material out of this folder.

## Advanced: unexposed models and parameters

1. Back up the JSON you will edit. All video modes now use `workflows/video_unified.json`, selected by `workflows/video_registry.json`. The older `workflow_template.json` and `video_motion_mp4.json` are retained legacy files, not the active video graphs.
2. For images/audio, find the function's `template` in `workflows/image_registry.json` or `workflows/audio_registry.json`; audio entries without a template use `<function ID>.json`. In the runtime graph, edit the relevant loader's actual text-encoder/VAE filename or other fixed input. Compatible weights and nodes must exist on the provider. Editing `example_workflows/` alone does not change the runtime.
3. Preserve node IDs, class types, links and input types. Exposed UI/API parameters overwrite graph defaults during compilation; change those through the UI or node presets. FLUX encoder pairing also uses image registry `model_clip`, which must be updated accordingly.
4. A workflow replacement that changes node IDs/input names requires registry updates (including `video_registry.json` for video). Exposing new controls may require schema/compiler/UI changes. Changing only a fixed loader filename usually does not.
5. Restart after edits. Inspect `/workflow/preview` before deciding to spend provider credits; preview does not verify remote model availability. RunningHub still needs its configured workflow ID; local ComfyUI does not. The app submits the compiled graph, so fixed inputs not overridden by the compiler use your edited runtime JSON.

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

## Unified video generation

Import the new `MiniMax_H3_一採保留_二採Latent放大_無限畫布.json` from `example_workflows/` into RunningHub and set its ID in the video workflow setting. Normal video, motion context, two-pass upscale, and motion context with upscale all use this **one workflow ID**. The previous separate motion ID is no longer used. Local ComfyUI needs the corresponding installed T8 nodes/models but no workflow ID.

- Enable **二採放大** in advanced settings; `scale_by` defaults to 2. Remaining controls use the supplied workflow defaults, including the first-pass schedule. Expand the complete parameter groups to override them. Both saved outputs use **24 fps**.
- Keep **同時保存一採影片** enabled to save both results; otherwise only the second-pass video is saved. The first pass still runs internally. Output assets include `generation_pass: first/second` and `output_node_id`; UI names identify the pass.
- Generate continuations through the director's **生成此段**. Auto selection prefers the previous successful run's first-pass video, falling back to second-pass. Select a particular output when needed. Without a previous clip, both overlap trims are bypassed.
- `audio_mode` defaults to `native`. `lock_source` and `remix_source` require a separate **drive audio** input (audio asset or connected audio node). It is not automatically added to reference-audio numbering. Both passes receive the same materials. Assign image roles explicitly: I2VA = first, L2VA = last, FL2VA = first + last, Ref2VA = reference. Invalid combinations are rejected before submission.
- RunningHub's per-node instance override offers Standard / Plus / Ultra; an empty override inherits settings. It has no effect on local ComfyUI. Higher-resolution refinement can require substantially more VRAM.
- Node titles are editable directly. `@` suggestions use already connected reference materials and insert at the cursor. Video mute state is retained when opening the enlarged player.
- Only the 11 approved filenames listed in `scripts/public_prompts.json` are included in release archives. New prompt files are ignored by Git by default; publishing a new template requires explicit approval and an allowlist update.

Automation clients should refresh `/catalog` and use `seed_mode`, `audio_mode`, `drive_audio_asset_id`, `two_pass`, `save_first_pass`, `two_pass_parameters`, and optional `instance_type` from the Generation schema. Two-pass defaults are in `/catalog.config.video_two_pass_parameters`. See the bundled canvas API skill for exact bindings.
