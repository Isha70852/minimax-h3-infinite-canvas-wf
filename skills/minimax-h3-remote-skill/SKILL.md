---
name: minimax-h3-remote
description: Generate MiniMax H3 videos through an authenticated Colab Motion Context API using local picture, video, and audio references, ordered LoRAs, and optional continuation from any selected video or time range.
---

# MiniMax H3 Remote · Motion Context

Use this skill's `scripts/h3_client.py` (Python 3.10+, `pip install -r requirements.txt`).
The user runs `MiniMax_H3_MotionContext_Remote.ipynb` Cells 1–5 and 7 in Colab.
The launching local process needs `H3_API_URL` and `H3_API_TOKEN`. Never print the token, put it in prompts/records, or commit it.

Run `python <skill>/scripts/h3_client.py health` before generating. Require protocol `h3-motion-context-1`.
Health returns applied Cell 3 defaults; omitted generation options inherit those settings. For connection failure, ask the user to check the Colab runtime / Cell 7 and update URL or token as needed. Do not start an alternative GPU service.

## Choose independent generation or continuation

- Independent clip: explicitly pass `--no-motion-context`; omit `--previous`. The server ignores inherited previous-range settings when context is off.
- Continue a clip: pass `--previous "absolute/path/selected.mp4"`. This enables Motion Context. Use the exact clip the user selected, even when it is not the most recently generated clip.
- Continue from part of a clip: also pass `--previous-start SECONDS --previous-end SECONDS`. It takes the tail of that selected interval. End omitted inherits Cell 3; use a settings file with `previous_end:null` to explicitly use the file's end.
- Never automatically choose a previous clip. If continuation is requested but its source cannot be resolved from the user's files or current conversation, ask for the source.

`--previous` is separate from `--video`: it is not assigned `<Video N>` or `<Audio N>` tags, and does not satisfy Ref2VA's reference requirement.
Motion Context owns the opening frames: use `ref2va`, `t2va`, or `l2va` for continuation. I2VA/FL2VA opening anchors conflict and are rejected. A last-frame L2VA anchor remains available.

The result is only the new segment. It does not include or automatically concatenate the previous clip.
Duration is the pre-trim sampling target, aligned up to H3's 17n+5 frame grid at 24fps; context is cut from both video and audio. Report actual duration from the server, not the requested duration.
Context defaults: 22 video frames / 24 audio frames; `--context-length` supports 5, 22, 39, 56; audio context 0 follows video length. The previous clip may be silent; then only its picture motion is continued.

## References and prompt

Preserve user file order and complete supplied prompts. If asked to write a prompt, describe the next segment's action, camera, identities and sound; do not insert a cut or restart at a continuation join unless requested. Save the final prompt in a UTF-8 text file.

Modes:

| Mode | Media |
|---|---|
| `ref2va` | 1–9 Pictures, 0–3 reference Videos, 0–3 standalone Audios; at least one reference in any group |
| `t2va` | No reference media |
| `i2va` | One `--image` = first frame |
| `fl2va` | Two `--image`, first then last |
| `l2va` | One `--image` = last frame |

Ref2VA can have zero pictures if it has a video or audio reference. Repeat `--image`, `--video`, `--audio` in the requested order.
Tags are `<Picture 1>...`, `<Video 1>...`, `<Audio 1>...` within each group. Standalone Audio numbering stays stable; the server translates the conditioning copy when video references contain embedded audio. The original prompt is preserved in TXT. Do not renumber it locally.

For a composed Ref2VA prompt use `subject_definitions`, `summary`, `retention_analysis`, `detailed_description` with timed `[Shot N]` blocks, `overall_soundscape`, and `non_diegetic_music`. Refer only to uploaded tags. For dialogue use `<d>[Chinese] 台詞</d>` or the requested language. Record continuity requirements explicitly.

## Model, LoRA and attention

Run `models` before selecting an installed model or LoRA. Use exact returned names. Checkpoint and conditioning mode are independent. Arbitrary downloads belong in Colab Cell 3 → Cell 4, not the remote generation API.

Use `--loras-file` with a UTF-8 array `[{"name":"installed.safetensors","strength":0.9}, ...]` in the user's order. `--no-lora` clears the chain. Otherwise inherit the chain from health.

Kitchen and Sol default on; lowering VRAM defaults off. Only change these when requested or when the user authorizes parameter tuning:

```text
--low-vram --head-chunks 4 --ff-chunks 2 --seq-threshold 4096
--no-low-vram
--kitchen-attention / --no-kitchen-attention
--sol-attention / --no-sol-attention
--sol-tau 1.3 --sol-start 0.2 --sol-end 1.0
```

Sol kernel availability is in health provenance. Enabled configuration does not prove hardware acceleration; it may use dense fallback. Do not claim a measured speedup without evidence.

## Commands

Read [references/api.md](references/api.md) for all settings, API fields, range reset, and recovery commands.

Independent example (replace paths with actual files):

```powershell
python <skill>/scripts/h3_client.py generate `
  --mode ref2va --image "C:\AI\refs\person.png" `
  --prompt-file "C:\AI\work\prompt.txt" --no-motion-context `
  --output-dir "C:\AI\outputs" --prefix "scene"
```

Continuation from a chosen interval, with an identity reference:

```powershell
python <skill>/scripts/h3_client.py generate `
  --mode ref2va --image "C:\AI\refs\person.png" `
  --previous "C:\AI\outputs\selected.mp4" --previous-start 2 --previous-end 8 `
  --context-length 22 --audio-context-length 24 `
  --prompt-file "C:\AI\work\next.txt" --duration 10 `
  --output-dir "C:\AI\outputs" --prefix "scene02"
```

For continuation with no references use `--mode t2va --previous ...`.
Seeds use decimal strings up to 18446744073709551615. Preserve the user's seed and sampling choices.

## Completion and failures

The client prints a job ID, polls, and downloads MP4 plus the authoritative server TXT. Wait for completion and report both exact paths and actual output duration / dimensions. Do not substitute the prompt file for TXT.

Use `status JOB_ID` or `resume JOB_ID --output-dir ...` after an interrupted wait. A client timeout is not a canceled GPU job. Never blindly resubmit a generation after a connection error, or silently change parameters to fix a failure.
Jobs are in runtime memory; a Colab reset loses their status. A tunnel restart in the same engine preserves jobs.
If TXT download fails, retain the MP4 and recover the existing result; do not generate again. Do not claim visual continuity or GPU verification from API/graph tests alone.
