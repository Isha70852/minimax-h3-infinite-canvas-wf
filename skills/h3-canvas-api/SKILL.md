---
name: h3-canvas-api
description: Operate a locally running H3 Infinite Canvas through its opt-in API to upload media, write prompts, configure workflows, and generate images (incl. MiniMax H3 Image text-to-image and multi-reference edit), audio, video, or SCAIL-2 motion-transfer / character-replacement clips with RunningHub, local ComfyUI or a Colab bridge. Use when the user wants an AI coding tool to operate this canvas project.
---

# 雪音畫布 Yukine Palette · Canvas API (formerly H3 Canvas)

Use the user's running canvas service, normally `http://127.0.0.1:8766/api/automation/v1`. Ask the user to enable **設定 → 外部 AI 操作 API** and provide the generated token if unavailable. No Codex-specific runtime is required: any HTTP client works. Send `Authorization: Bearer TOKEN` on every API request. Keep the token in process memory/environment; do not place it in prompts, committed files, screenshots or logs. Do not read the app database to obtain credentials. Provider keys/workflow IDs remain configured by the user in the app.

Read `GET /catalog` first for current capabilities, workflow IDs (catalog keys, not private RunningHub IDs), field definitions/defaults, templates and JSON schemas. Read `GET /schema` for exact HTTP request schemas. Never guess a new model's fields. The base URL above already includes the version prefix.

### Where the generators are listed (read this before concluding a model is missing)

`GET /workflows` (also `/catalog.workflows`) is the index of every built-in generator, grouped as `video`, `image`, `motion`, `music`, `tts`, `custom`. Each row gives `workflow`, `name`, the canvas `node_kind`, the node data key that holds the spec (`node_spec_key`), the `request_schema`, and field keys; full field definitions are in `/catalog.config.image_workflows`, `.motion_workflows`, `.audio_workflows`.

- **Built-in** image (MiniMax H3 Image `h3_t2i` / `h3_edit`, Moss, Z-Image, Anima, FLUX.2 Klein), motion (`scail2` with `mode:"animate"` motion transfer or `mode:"replace"` character replacement), music and TTS workflows are **not** in `config.custom_workflows`. That list contains only packages the user imported. They need no template either.
- `node_templates` are optional saved parameter presets. An empty list does **not** mean a workflow is unavailable.
- Do not substitute another model, for example video Ref2VA in place of an image request, because you could not find a workflow. Check `/workflows` first. If it is really absent, report that to the user.

| Task | node_kind | spec key on node | spec `kind` / `workflow` |
|---|---|---|---|
| Video (H3) | `generation` | `spec` | Generation (no `workflow`) |
| H3 Image text-to-image | `imagegen` | `image_spec` | `image` / `h3_t2i` |
| H3 Image edit (1–6 refs) | `imagegen` | `image_spec` | `image` / `h3_edit` |
| Motion transfer | `motiongen` | `motion_spec` | `motion` / `scail2`, `values.mode:"animate"` |
| Character replacement | `motiongen` | `motion_spec` | `motion` / `scail2`, `values.mode:"replace"` |
| Music / TTS | `music` / `tts` | `audio_spec` | `audio` / catalog key |
| Imported package | `custom` | `custom_spec` | `custom` / `package_id`+`version` |

## Execution procedure

1. List projects with `GET /projects`, or create one with `POST /projects` and `{"name":"My film"}`. Get the full canvas with `GET /projects/{id}`. Prefer a dedicated project for automation. Avoid concurrent edits in the browser; reload the project when automation finishes.
2. Upload local files as multipart field `file` to `POST /assets?scope=project&project_id=PROJECT_ID`. Images, videos and audio use this same endpoint (512 MB per file). Retain returned asset IDs. `GET /assets?project_id=...` lists project assets. Copy an existing shared asset into this project with `POST /projects/{project_id}/import/{asset_id}` before referencing it.
3. Create/update canvas nodes and edges through `PUT /projects/{id}`. Send the current `name`, `nodes`, `edges`, `viewport`, and header `If-Match: UPDATED_AT` using the exact `updated_at` from the latest GET. On 409, fetch again and merge; never overwrite unrelated nodes. This endpoint replaces the supplied canvas arrays.
4. Write a prompt directly into a text node or generation spec. Optionally use the configured AI assistant as described below. The agent can also author prompts itself without a model API call.
5. Validate unbound specs with `POST /workflow/preview`. This compiles locally; it does not prove remote model/node availability. For text-bound specs, resolve the text yourself for preview; submission resolves project text sources.
6. Submit `POST /runs` with `project_id`, `node_id`, a unique `request_id` (UUID), and `spec`. This uses provider credits/GPU. Submit only the quantity and providers authorized by the user. Poll `GET /runs/{request_id}` every 5–10 seconds. Inspect `status`, `stage`, `error`, `outputs`, `usage`; stop polling on success/failed/attention. On an uncertain response, query that same request ID; do not create another paid request ID automatically. Retrying the same ID returns the existing record, not a new generation.
7. Successful outputs are project assets. Use their IDs as subsequent inputs; set the node's `data.output_id` to the selected output ID when saving the project. Download `outputs[].url` relative to the service origin, not the versioned API base. No endpoint executes shell commands or accepts arbitrary filesystem paths.
8. For long videos, generate the next segment only after the previous succeeds. Set `motion_context:true, context_run_id:PREVIOUS_REQUEST_ID` on its video spec. The server uploads the previous MP4 for image/audio context. `context_video_asset_id` can explicitly select a project video; do not put this context into ordinary `references` unless independently requested. Overlap trimming can shorten output. Follow the user's plan for concatenation; this API does not automatically join segments.

## Canvas and generation data

Every node has `id`, `type:"card"`, `position:{"x":0,"y":0}`, and `data`. Use stable unique IDs.

- Text: `data:{"kind":"text","label":"Scene 1 prompt","text":"..."}`.
- Uploaded asset: `data:{"kind":"asset","label":"Character","asset_id":"ASSET_ID"}`.
- Video generation: `data:{"kind":"generation","label":"Scene 1","spec":VIDEO_SPEC}`.
- Image generation: `data:{"kind":"imagegen","label":"Storyboard","image_spec":IMAGE_SPEC}`.
- Music/TTS: `data:{"kind":"music" or "tts","label":"Voice","audio_spec":AUDIO_SPEC}`.
- Motion transfer / character replacement: `data:{"kind":"motiongen","label":"Dance","motion_spec":MOTION_SPEC}` (see below).

A reference edge is `{"id":"edge-uuid","source":"asset-node-id","target":"generation-node-id","data":{"asset_id":"ASSET_ID","role":"reference"}}`. For video first/last frames use roles `first` / `last` with mode `FL2VA`. For a video prompt text connection use `targetHandle:"prompt"`, source text-node ID, and also set `spec.prompt_source` in the submitted spec. Other text fields use their catalog key as targetHandle and `text_sources:{FIELD_KEY:TEXT_NODE_ID}`. Image edges use the image field key as targetHandle; audio inputs use `audio`.

Edges provide the visible canvas connections. **Submission must also contain the corresponding references/image_assets/audio_asset_id/text_sources in spec; adding an edge alone does not bind an API request.**

Minimal video spec:
```json
{"provider":"runninghub","prompt":"A quiet forest at dawn.","mode":"T2VA","duration":5,"megapixels":0.7,"references":[]}
```
Merge the user's desired values with `/catalog.config.video_defaults` when appropriate. `Generation` schema defines model, LoRA, shift, steps, sampler, scheduler and memory options. `Ref2VA` references are `[{"asset_id":"...","role":"reference"}]`; Picture/Video/Audio labels are independently numbered in the compiler's order (role then media kind). Inspect preview `mapping` rather than inventing numbers.

Image spec uses `kind:"image"`, `provider`, `workflow`, `values`, `image_assets`, `text_sources`, plus schema-defined advanced fields. Audio spec uses `kind:"audio"`, `provider`, `workflow`, `values`, `audio_asset_id`, `text_sources`. Discover exact workflow keys and fields from the catalog; never use the private RunningHub workflow number as `workflow`.

MiniMax H3 Image workflows: `h3_t2i` (text-to-image) and `h3_edit` (multi-image editing). `h3_edit` takes `image_assets` keys `image`, `image2` … `image6`, filled in order without gaps; the prompt refers to them as `<Picture 1>`, `<Picture 2>`, … `values.aspect_ratio` is `match_input` (follow reference 1, size = `ref_megapixels`) or a ResolutionSelector ratio such as `"16:9 (Widescreen)"`; `megapixels` 0.5–16 (default 4). Both accept `loras:[{name,strength,enabled}]`; the text encoder file is shared with H3 video. Advanced values: `steps` (6), `cfg` (1), `sampler`, `scheduler`, `model`, `text_encoder`; read defaults from the catalog.

```json
{"kind":"image","provider":"comfyui","workflow":"h3_t2i","values":{"prompt":"Portrait of a knight, soft window light","aspect_ratio":"2:3 (Portrait Photo)","megapixels":4},"loras":[]}
```
```json
{"kind":"image","provider":"comfyui","workflow":"h3_edit","values":{"prompt":"Put the character from <Picture 1> into the room of <Picture 2>","aspect_ratio":"match_input","ref_megapixels":4},"image_assets":{"image":"CHARACTER_ASSET_ID","image2":"ROOM_ASSET_ID"},"loras":[]}
```
Put this spec in an `imagegen` node as `data.image_spec` and submit it to `/runs` with that node ID. Visible edges use the image key as `targetHandle` (`image`, `image2`, …). A prompt text node binds through `text_sources:{"prompt":TEXT_NODE_ID}`. Output is one image asset.

## Optional AI prompt drafting and history

`POST /prompt-drafts` accepts the `DraftRequest` schema: `request_id`, `project_id`, `node_id`, `target_type` (`text`/`video`), `requirement`, `spec` (Generation schema), `template_mode` (`saved`/`custom`/`none`/`inherit`), optional `template_id`, `custom_template`, `material_notes`, `ending_notes`, `history_ids`, `history_include_templates`.

Use `GET /context-options?project_id=...` to discover eligible history IDs: AI drafts, current text/video nodes (`node:ID`) and submitted video prompts (`run:ID`). Pass selected IDs in narrative order. Manual content is explicitly labeled user-authored prior scene context, not an AI reply. Each request snapshots the selected prompt/materials; repeated historical snapshots are deduplicated. Historical reference numbers belong to their own segment. Current inputs and user requirements take precedence; continuity is optional, not automatically seamless.

`history_include_templates:false` excludes old template contents; `template_mode` independently chooses the current writing instructions. Poll `GET /prompt-drafts?project_id=...&node_id=...` for result/status. Applying a draft requires explicitly updating the text/spec and, if authorized, submitting `/runs`; drafting does not generate a video. The assistant sees current reference images, sampled frames of current videos and historical images; audio is described via notes, not listened to.

## Scope and failures

The interface is off by default and bound to the app's localhost service. Disabling it rejects new API requests but does not cancel already submitted work. Rotating the token invalidates its predecessor. The automation API does not expose provider credentials, settings changes, file deletion or arbitrary command execution. Sharing the skill does not share credentials or personal workflow IDs. Internal browser endpoints remain separate; do not bypass a disabled automation interface through them.

401: token missing/invalid. 403: API disabled. 409: refresh/merge the project or inspect the existing job. 422: correct the inputs from the schema and error. Failed/attention jobs must be diagnosed before any new paid submission. Report actual output duration, usage when supplied, and whether continuation was visually verified. Never call two independent generations a verified motion-context continuation.

IndexTTS 2.5 supports `audio_assets:{"audio":"SPEAKER_ASSET_ID","emotion_audio":"EMOTION_ASSET_ID"}`. The legacy `audio_asset_id` still selects the speaker reference. Omit `emotion_audio` to reuse the speaker audio for emotion. For visible canvas connections use target handles `audio` and `emotion_audio`, respectively. Its emotion weight is the official ComfyUI `PrimitiveFloat` node (no extra node pack).

Breeze TTS 2 (`breeze_clone`, `breeze_direction`, `breeze_design`) exposes `values.download_if_missing` as the string `"true"` (default: the loader downloads missing weights on first run) or `"false"` (weights must already exist).

## Node parameter templates (v0.2)

These are generation parameters, separate from AI writing-instruction templates. Discover `GET /node-templates` (also `/catalog.node_templates`). Categories: `video`, `image`, `motion`, `music`, `tts`. Create with `POST /node-templates`, update with `PUT /node-templates/{id}`; body: `{category,name,tags:["tag"],is_default:false,spec:{...}}`. Only mapped parameters persist; scene text, media bindings and motion context are excluded. Users manage them from the left canvas menu. Delete a preset only when requested with `DELETE /node-templates/{id}`.

`POST /runs` additionally accepts top-level `template_id`, `template_tag`, `use_default_template` (default true). ID or an unambiguous tag selects a preset; otherwise the category default is used. Explicit spec fields override preset values; `values` merges by key, LoRA lists replace in full. Omit unwanted explicit defaults so they do not override the chosen preset. An explicit incompatible workflow is rejected; an incompatible category default is skipped. Set `use_default_template:false` to use only the supplied spec. Preview does not apply templates: merge the selected preset and overrides yourself before `/workflow/preview`, then use the same effective spec for submission. Use schema fields supported by that workflow; audio workflows do not acquire arbitrary LoRA support from templates.

Video `lora_strength` adjusts the main LoRA; `extra_loras:[{name,strength,enabled}]` loads additional LoRAs in order. `lora_enabled:false` disables the entire chain and shift. Image LoRA lists retain their existing `loras` schema.

Motion-context submissions automatically create/update a director node and its segment list in the project, including the preceding run's node when present. GET the project again before every subsequent PUT so you preserve the new director and fresh `updated_at`. Reload the browser project to see it. Branching from an earlier segment creates a separate director chain. In the UI, continuation must use the director's **生成此段** action; the standalone node's generation button starts an independent clip.

## Reusing video noise seeds

Set `spec.noise_seed` to a decimal **string** in `0..18446744073709551615`, e.g. `"1234567890123456789"`. Set `seed_mode:"fixed"` to reuse it; set `seed_mode:"randomize"` to generate a fresh seed even when a prior seed remains in the spec. Legacy requests without seed_mode retain the old null=random / supplied=fixed behavior. Read the actual `seed` string from the run result and pass that exact string to a subsequent request; do not convert it through JavaScript Number. Video run specs also record the resolved seed. Preview honors an explicit seed without generating media. Image/audio seed semantics are unchanged. RH billing (`usage.consumeCoins`, `usage.taskCostTime`) is optional and RunningHub-only; local ComfyUI results may omit usage entirely. Use `finished_at-created_at` only as total local elapsed time, not GPU time.

AI writing templates are built-ins shipped in `backend/builtin_prompts/` plus the user's local `data/prompts/*.md|*.txt` (user files override built-ins of the same name; entries carry `builtin`/`customized` flags). Discover current IDs/content via `/catalog.prompt_templates`; IDs are filenames including the extension, not the removed built-in `characters` ID. Do not assume a specific template exists. Select a suitable saved template or use the existing custom/none modes. Node parameter presets and AI writing templates remain distinct.

## Unified video workflow and two-pass controls

All video combinations use the configured unified workflow ID; do not request a separate motion ID. Read the current Generation schema and `config.video_two_pass_parameters` from `/catalog`.

- `two_pass:true` enables refinement; `save_first_pass:true` (default) saves both passes, false saves only second-pass. First-pass computation is always required. `two_pass_parameters` is an optional nested override, e.g. `{"upscale":{"scale_by":2}}`; supported groups are `plan`, `upscale`, `reconcile`, `mixer`. Preserve unspecified workflow defaults. `mixer.restart_seed` is a uint64 decimal string. Both outputs are 24 fps.
- Output assets carry `generation_pass:"first"|"second"` plus `output_node_id`. To continue, set `motion_context:true, context_run_id:PREVIOUS_RUN`; omission of context_video_asset_id prefers that run's first-pass video, falling back to second-pass. Set context_video_asset_id explicitly to select one of its video outputs. Do not choose by download order. First segments omit both context IDs. Independent submissions must set motion_context false.
- `audio_mode` supports native (default), reference_only, lock_source, remix_source. The latter two require `drive_audio_asset_id` pointing to a project audio asset. For canvas wiring use targetHandle `drive_audio`; this edge is separate from references. Include the spec field when submitting through the API (visual edges do not replace explicit API bindings). Both conditioning nodes receive all selected references, first/last frames and drive audio.
- `mode:T2VA` requires no references; I2VA one image role first; L2VA one image role last; FL2VA two images roles first and last; Ref2VA reference roles. Do not send keyframes as ref_images. Drive audio is separate and may accompany any mode.
- Optional `instance_type:"default"|"plus"|"ultra"` overrides RunningHub resources for this run. Null inherits global settings; local ComfyUI ignores it.
- Rename any canvas node by changing its `data.label` through the optimistic project PUT API, preserving other nodes/edges and the server's latest updated_at.


### Canvas comparison and keyframe slots
- A comparison is a saved canvas node: `type: "card"`, `data: {"kind":"compare","label":"Compare"}`, `style: {"width":760,"height":560}`. Connect two image/video asset or generation nodes with edges whose `targetHandle` is `a` / `b` and `data.asset_id` is the corresponding output asset ID. It is a viewer, not a generation workflow; do not submit it to `/runs`.
- Video references retain explicit API roles: I2VA needs one image with `role:first`; L2VA one with `role:last`; FL2VA both. Additional audio/video references use `role:reference`. Ref2VA uses reference roles; T2VA has no references. The UI assigns the image roles through labeled slots; automation must still supply them explicitly. `<Picture N>` numbering follows the ordered references, independently of the slot label. Drive audio remains a separate `drive_audio_asset_id`.


### Canvas groups
Use the existing optimistic-concurrency project PUT; no new generation endpoint is needed. A group is a `type: "card"` node with `data: {"kind":"group","label":"Group","collapsed":false}`, a top-level absolute position, `style.width/height`, `dragHandle: ".canvas-group-header"`, and `zIndex:-1`. Place groups before their children in the nodes array. Members have `parentId` set to the group ID and positions relative to the group origin. Keep original child IDs and edges. Toggle `data.collapsed` only; do not write derived hidden flags or shrink the stored group size. Ungroup by adding the group position to member positions and removing their parentId. No nested groups. Do not submit group nodes to /runs.

Avoid concurrent graph edits while the user is editing the same project: browser saves are full replacements, not collaborative merges. Polling results and media playback are read-only. Connection visibility and playback volume are presentation preferences and do not change generation parameters.


### Colab video generation
`Generation.provider` also accepts `colab`. With the universal notebook (below) image, audio, motion and custom specs accept `colab` too; the legacy 20261102 notebook is video only. Configure Colab URL/token locally in Settings before automation; catalog exposes the video schema, not credentials. All other video fields and reference roles are unchanged. The backend compiles the same unified graph used for ComfyUI/RunningHub and posts it to the notebook `/prompt` endpoint, not `/canvas/generate`. The 20261102 notebook requires the updated canvas bridge cell and Cell 7, with the unified API JSON uploaded and all referenced models/custom nodes installed. Output assets keep first/second pass labels and can be used by director Motion Context. Preserve group `data.collapsed_size` when updating projects; expanded dimensions remain in node style. Do not persist rendered collapsed dimensions over expanded style.

Legacy Colab bridges without `/object_info` can submit full graphs after health/endpoint checks; ComfyUI validates the submission. Downloads fall back to `/canvas/result/{prompt_id}/{first|upscaled}` for output nodes 356/357. Audio references require `/upload/audio`; do not repeatedly submit an unsupported audio job.

Group headers support `data.group_color` as a CSS hex color (for example `#25303b`). Preserve it during project updates. Expanded group resize must contain all children; collapsed dimensions remain independent.

### Named sources and cancellation
Discover `config.provider_profiles` in GET /catalog (ID, name, provider only). All generation specs accept optional `provider_profile_id`; it must match `provider`. Omission/null uses the original default connection. Parameter templates persist this field. Never place credentials in specs or templates; source settings are managed locally.
POST `/runs/{id}/cancel` requests cancellation. Poll the same ID: `cancel_requested` indicates pending, `cancelled` is terminal, `cancel_error` means the request failed and monitoring continues. Do not submit a replacement automatically. A submission already in flight waits for its remote ID; a completed result can win. Colab requires the updated authenticated cancellation bridge.

Video specs accept `sigma_mode:"scheduler"|"manual"` (default scheduler) and `manual_sigmas` as a comma-separated descending nonnegative decimal string ending in zero. Default: `1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0`. Manual mode rewires first-pass sampler #125 to ManualSigmas #358; first-pass steps/scheduler are retained but inactive. Second-pass refinement sigmas are unchanged. Templates persist both fields. Preview validates the schedule; remote node availability requires provider support.

Colab v0.5.1: the dual-JSON import cell (⑥, after Cell 5) no longer blocks on model presence. Cell 7 registers authenticated `/canvas/cancel/{prompt_id}`, `/upload/audio`, and `/view`. Update and rerun the full Cell 7 for cancellation support. `cancel_error` is the concise string `取消失敗`.


## Custom workflow packages

All paths below are relative to the authenticated automation base. Read `/custom-workflows` and `/custom-workflows/{id}/versions/{version}` before building a spec. `POST /custom-workflows/inspect` accepts `{name,graph}`; its candidate types are hints, not authoritative custom-node schemas. `POST /custom-workflows` and `PUT /custom-workflows/{id}` accept the Package schema from `/schema`. Each update creates a pinned revision; re-map IDs explicitly when replacing a graph. Do not guess bypass types, indexed input names, slot numbers, or copy private sample prompts into shared files.

A canvas node uses `data:{kind:"custom",label:"Name",custom_spec:SPEC}`. SPEC has `kind:"custom"`, `package_id`, `version`, `provider`, optional `provider_profile_id`, `mode`, `values:{FIELD_KEY:VALUE}`, `media_assets:{FIELD_OR_GROUP_KEY:[ASSET_ID,...]}`, and optional `text_sources:{TEXT_FIELD_KEY:TEXT_NODE_ID}`. Media order determines explicit tag numbering; repeated groups have configurable maximum counts, not the number connected in the source graph. Seed values should be `"random"` or decimal strings to preserve 64-bit precision. Visible edges use `targetHandle:FIELD_OR_GROUP_KEY`; submit bindings in SPEC as well.

Use the existing preview/run/poll/cancel endpoints. Resolve text bindings for preview; run submission resolves them from the project. `/custom-workflows/presets/list` lists presets; POST `/custom-workflows/presets` accepts `{name,tags,is_default,spec}`. Submit with `template_id`, unique `template_tag`, or `use_default_template`; an explicit spec version must match the chosen preset version. Model library GET/PUT `/custom-workflows/models/library` uses `{groups:{unet:[...],vae:[...],clip:[...],lora:[...]}}` for PUT. It stores filenames only. Never interpret a successful compile as proof the provider has the required custom nodes/models. Colab category restrictions were removed for the universal notebook (the legacy notebook still only has the H3 video stack installed); 3D outputs are downloadable standard files, not arbitrary executable plugins.

Built-in video specs also accept `clip_name`, `video_vae_name`, and `audio_vae_name`; blank preserves the graph default. Custom run results expose `compiled.seed_values` as decimal strings keyed by `NODE_ID:INPUT_NAME`. To replay these exactly, submit `seed_overrides` with that map; do not parse uint64 seeds as JavaScript numbers. Overrides must match active seed inputs in the pinned graph.


## SCAIL-2 motion transfer / character replacement (motiongen)

Catalog key: `config.motion_workflows` (currently `scail2`). MOTION_SPEC is `{"kind":"motion","provider":"comfyui|runninghub|colab","provider_profile_id":null,"workflow":"scail2","values":{...},"media_assets":{"reference_image":IMAGE_ASSET_ID,"drive_video":VIDEO_ASSET_ID},"text_sources":{"prompt":TEXT_NODE_ID}}`. Visible edges use targetHandle `reference_image`, `drive_video` or `prompt`; submit the same bindings in the spec.

- `values.mode`: `animate` (motion transfer — keep the reference image background) or `replace` (character replacement — keep the drive video background; maps to SCAIL `replacement_mode:true`). Both are the same `scail2` workflow on a `motiongen` node; there is no separate replacement workflow. Example replacement spec: `{"kind":"motion","provider":"comfyui","workflow":"scail2","values":{"mode":"replace","length_mode":"extend","prompt":"a woman dancing","video_mask_prompt":"person","max_objects":1},"media_assets":{"reference_image":IMAGE_ASSET_ID,"drive_video":VIDEO_ASSET_ID}}`.
- `values.length_mode`: `single` (one chunk, `frames` 17–81, 4n+1) or `extend` (long video). Extend unrolls official SCAIL-2 chunks inside one graph: 81 frames per chunk, 76-frame stride, 5-frame `previous_frames` anchor, overlap trimmed and colour-matched (`color_match`), joined with `BatchImagesNode`, audio from the drive video (`keep_audio`). `max_segments` 2–6 caps the chunk count. The backend probes the uploaded (normalized to 24 fps; no length limit) video locally; `run.compiled.segments` reports the plan.
- `reference_fit`: `pad_white` (default) / `pad_black` keep the whole reference via `ResizeAndPadImage`; `crop` centre-crops and can cut off the head when aspect ratios differ. `video_mask_prompt` describes the person in the **drive video** (e.g. `person`), `image_mask_prompt` the character in the reference; for one reference character use `max_objects:1`. `start_frame` skips the beginning of the drive video; `drive_fps` resamples it (0 = keep the uploaded 24 fps). Also exposed: `negative_prompt`, `detect_interval`, `crf`, and model file names `dpo_lora_name`, `distill_lora_name`, `text_encoder`, `vae`, `clip_vision`, `sam_model`.
- `width`/`height` must be multiples of 32. `seed` -1 = fresh task seed. Advanced keys: `model`, `steps` (default 6), `cfg` (1), `shift` (5), `sampler`, `scheduler`, `distill_lora_strength` (0.8), `dpo_lora_strength` (1), `pose_strength/start/end`, `detection_threshold`, `max_objects`, `sort_by`, `object_indices`, `video_mask_prompt`, `image_mask_prompt`. Defaults are the accelerated recipe (lightx2v distill LoRA); there is no slow 40-step path.
- Nodes are official ComfyUI core (`WanSCAILToVideo`, `SCAIL2ColoredMask`, `SAM3_VideoTrack`, `ColorTransfer`, `BatchImagesNode`, `ImageScale`…) plus VideoHelperSuite load/save. Models: `wan2.1_14B_SCAIL_2_int8_convrot`, SCAIL-2 DPO LoRA, lightx2v I2V distill LoRA, `umt5_xxl_fp8_e4m3fn_scaled`, `clip_vision_h`, `Wan2_1_VAE_bf16`, `sam3.1_multiplex_fp16`.
- RunningHub uses `motion_workflow_ids.scail2` from the selected source (upload `example_workflows/motion_scail2_single_無限畫布.json` to RunningHub to obtain it). Output is one MP4 asset.

## Colab notebook (`colab/Yukine_Palette_Colab.ipynb`)

No workflow JSON is uploaded to Colab. The notebook installs only the ticked feature packs/models (official Comfy-Org Hugging Face sources first), starts ComfyUI on localhost and exposes an authenticated native bridge: `/object_info`, `/prompt`, `/history/{id}`, `/queue`, `/interrupt`, `/upload/image` (also `type=output` latents), `/canvas/upload/video`, `/upload/audio`, `/view`, `/canvas/cancel/{id}`, `/health`, `/heartbeat`, `/models`. The canvas `Colab` provider compiles the same graphs as ComfyUI and posts them there, so every node kind works when its nodes/models are installed. Preflight uses `/object_info`, so missing model files are reported before submission. The user configures `H3_API_URL` and token locally; never request or log them.
