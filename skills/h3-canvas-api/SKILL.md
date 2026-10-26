---
name: h3-canvas-api
description: Operate a locally running H3 Infinite Canvas through its opt-in API to upload media, write prompts, configure workflows, and generate image, audio, or video segments with RunningHub or local ComfyUI. Use when the user wants an AI coding tool to operate this canvas project.
---

# H3 Canvas API

Use the user's running canvas service, normally `http://127.0.0.1:8766/api/automation/v1`. Ask the user to enable **設定 → 外部 AI 操作 API** and provide the generated token if unavailable. No Codex-specific runtime is required: any HTTP client works. Send `Authorization: Bearer TOKEN` on every API request. Keep the token in process memory/environment; do not place it in prompts, committed files, screenshots or logs. Do not read the app database to obtain credentials. Provider keys/workflow IDs remain configured by the user in the app.

Read `GET /catalog` first for current capabilities, workflow IDs (catalog keys, not private RunningHub IDs), field definitions/defaults, templates and JSON schemas. Read `GET /schema` for exact HTTP request schemas. Never guess a new model's fields. The base URL above already includes the version prefix.

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

A reference edge is `{"id":"edge-uuid","source":"asset-node-id","target":"generation-node-id","data":{"asset_id":"ASSET_ID","role":"reference"}}`. For video first/last frames use roles `first` / `last` with mode `FL2VA`. For a video prompt text connection use `targetHandle:"prompt"`, source text-node ID, and also set `spec.prompt_source` in the submitted spec. Other text fields use their catalog key as targetHandle and `text_sources:{FIELD_KEY:TEXT_NODE_ID}`. Image edges use the image field key as targetHandle; audio inputs use `audio`.

Edges provide the visible canvas connections. **Submission must also contain the corresponding references/image_assets/audio_asset_id/text_sources in spec; adding an edge alone does not bind an API request.**

Minimal video spec:
```json
{"provider":"runninghub","prompt":"A quiet forest at dawn.","mode":"T2VA","duration":5,"megapixels":0.7,"references":[]}
```
Merge the user's desired values with `/catalog.config.video_defaults` when appropriate. `Generation` schema defines model, LoRA, shift, steps, sampler, scheduler and memory options. `Ref2VA` references are `[{"asset_id":"...","role":"reference"}]`; Picture/Video/Audio labels are independently numbered in the compiler's order (role then media kind). Inspect preview `mapping` rather than inventing numbers.

Image spec uses `kind:"image"`, `provider`, `workflow`, `values`, `image_assets`, `text_sources`, plus schema-defined advanced fields. Audio spec uses `kind:"audio"`, `provider`, `workflow`, `values`, `audio_asset_id`, `text_sources`. Discover exact workflow keys and fields from the catalog; never use the private RunningHub workflow number as `workflow`.

## Optional AI prompt drafting and history

`POST /prompt-drafts` accepts the `DraftRequest` schema: `request_id`, `project_id`, `node_id`, `target_type` (`text`/`video`), `requirement`, `spec` (Generation schema), `template_mode` (`saved`/`custom`/`none`/`inherit`), optional `template_id`, `custom_template`, `material_notes`, `ending_notes`, `history_ids`, `history_include_templates`.

Use `GET /context-options?project_id=...` to discover eligible history IDs: AI drafts, current text/video nodes (`node:ID`) and submitted video prompts (`run:ID`). Pass selected IDs in narrative order. Manual content is explicitly labeled user-authored prior scene context, not an AI reply. Each request snapshots the selected prompt/materials; repeated historical snapshots are deduplicated. Historical reference numbers belong to their own segment. Current inputs and user requirements take precedence; continuity is optional, not automatically seamless.

`history_include_templates:false` excludes old template contents; `template_mode` independently chooses the current writing instructions. Poll `GET /prompt-drafts?project_id=...&node_id=...` for result/status. Applying a draft requires explicitly updating the text/spec and, if authorized, submitting `/runs`; drafting does not generate a video. The assistant sees current reference images, sampled frames of current videos and historical images; audio is described via notes, not listened to.

## Scope and failures

The interface is off by default and bound to the app's localhost service. Disabling it rejects new API requests but does not cancel already submitted work. Rotating the token invalidates its predecessor. The automation API does not expose provider credentials, settings changes, file deletion or arbitrary command execution. Sharing the skill does not share credentials or personal workflow IDs. Internal browser endpoints remain separate; do not bypass a disabled automation interface through them.

401: token missing/invalid. 403: API disabled. 409: refresh/merge the project or inspect the existing job. 422: correct the inputs from the schema and error. Failed/attention jobs must be diagnosed before any new paid submission. Report actual output duration, usage when supplied, and whether continuation was visually verified. Never call two independent generations a verified motion-context continuation.

IndexTTS 2.5 supports `audio_assets:{"audio":"SPEAKER_ASSET_ID","emotion_audio":"EMOTION_ASSET_ID"}`. The legacy `audio_asset_id` still selects the speaker reference. Omit `emotion_audio` to reuse the speaker audio for emotion. For visible canvas connections use target handles `audio` and `emotion_audio`, respectively.

## Node parameter templates (v0.2)

These are generation parameters, separate from AI writing-instruction templates. Discover `GET /node-templates` (also `/catalog.node_templates`). Categories: `video`, `image`, `music`, `tts`. Create with `POST /node-templates`, update with `PUT /node-templates/{id}`; body: `{category,name,tags:["tag"],is_default:false,spec:{...}}`. Only mapped parameters persist; scene text, media bindings and motion context are excluded. Users manage them from the left canvas menu. Delete a preset only when requested with `DELETE /node-templates/{id}`.

`POST /runs` additionally accepts top-level `template_id`, `template_tag`, `use_default_template` (default true). ID or an unambiguous tag selects a preset; otherwise the category default is used. Explicit spec fields override preset values; `values` merges by key, LoRA lists replace in full. Omit unwanted explicit defaults so they do not override the chosen preset. An explicit incompatible workflow is rejected; an incompatible category default is skipped. Set `use_default_template:false` to use only the supplied spec. Preview does not apply templates: merge the selected preset and overrides yourself before `/workflow/preview`, then use the same effective spec for submission. Use schema fields supported by that workflow; audio workflows do not acquire arbitrary LoRA support from templates.

Video `lora_strength` adjusts the main LoRA; `extra_loras:[{name,strength,enabled}]` loads additional LoRAs in order. `lora_enabled:false` disables the entire chain and shift. Image LoRA lists retain their existing `loras` schema.

Motion-context submissions automatically create/update a director node and its segment list in the project, including the preceding run's node when present. GET the project again before every subsequent PUT so you preserve the new director and fresh `updated_at`. Reload the browser project to see it. Branching from an earlier segment creates a separate director chain. In the UI, continuation must use the director's **生成此段** action; the standalone node's generation button starts an independent clip.
