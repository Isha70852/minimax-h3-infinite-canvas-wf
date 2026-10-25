# Motion Context API contract

Base URL: `H3_API_URL`. Every data endpoint requires `Authorization: Bearer H3_API_TOKEN`.
Protocol: `h3-motion-context-1`.

| Method | Path | Result |
|---|---|---|
| GET | `/health` | protocol, applied defaults, node commits and Sol kernel availability |
| GET | `/models` | models, text_encoders, vaes, loras, samplers, schedulers |
| POST | `/generate` | multipart form → HTTP 202 `{id,status}` |
| GET | `/jobs/{id}` | queued / preparing / running / submission_unknown / completed / failed, seed string, timestamps, actual output, error |
| GET | `/result/{id}` | Completed MP4; 409 until completed |
| GET | `/info/{id}` | Authoritative UTF-8 TXT containing JSON generation record; 409 until completed |
| GET | `/workflow/{id}` | Exact ComfyUI API graph for this runtime |

`/generate` form fields:

- `prompt`: exact prompt text, required.
- `settings`: JSON object, default `{}`. Unknown keys are rejected. Values not supplied inherit applied Colab Cell 3 settings.
- `images`, `videos`, `audios`: repeated file fields, independently ordered.
- `previous`: one separate MP4 file, only when `motion_context=true`.

The client infers `motion_context=true` from `--previous`. Direct HTTP callers must set it explicitly.
Limits: 9 images × 50MiB, 3 videos × 1GiB, 3 audios × 256MiB, one previous × 1GiB.
The Colab runtime also needs enough disk/RAM for uploads and model weights; uploads are not persistent across resets.

## Settings and CLI

JSON keys use underscores. CLI uses corresponding `--hyphenated-name` flags. Boolean flags have `--no-...` forms.

| Settings | Default | Notes |
|---|---|---|
| mode | ref2va | ref2va, t2va, i2va, fl2va, l2va |
| duration | 10.0 | pre-trim seconds, H3 grid at 24fps; long requests can exceed available memory |
| width, height | 1152, 640 | positive multiples of 32 |
| seed | empty string | empty=random each request; decimal string 0..2^64−1 |
| steps, sampler, scheduler | 8, euler, beta | validated against live nodes |
| model | minimax_h3_ref2va_pruned_int8_convrot.safetensors | exact installed filename |
| text_encoder | qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors | exact installed filename |
| video_vae | minimax_h3_video_vae_int8_convrot.safetensors | exact installed filename |
| audio_vae | minimax_h3_audio_vae_fp32.safetensors | exact installed filename |
| loras | [] | ordered array of `{name,strength}`; CLI --loras-file / --no-lora |
| shift_enabled, shift_video, shift_audio | true, 6, 3 | independent from the LoRA switch |
| kitchen_attention, sol_attention | true, true | independent switches |
| sol_tau, sol_start, sol_end | 1.3, 0.2, 1.0 | Sol threshold and active fraction of schedule |
| sol_dense_blocks | empty string | e.g. `0,1,47-49` |
| sol_min_tokens, sol_extra_tokens, sol_verbose | 12288, 256, true | short sequences may remain dense |
| low_vram | false | enables both KJ model patches |
| head_chunks, ff_chunks, seq_threshold | 4, 2, 4096 | head 1–56, FF 1–64, threshold 256–262144 |
| motion_context | false | previous required iff true |
| context_length, audio_context_length | 22, 24 | video 5/22/39/56; audio 0–240, 0 follows video |
| previous_start, previous_end | 0.0, null | seconds selecting interval; end null means full file end |
| ref_image_size | match | match / max |
| reference_video_policy | official_2_to_15s | official_2_to_15s / model_minimum |
| crf, prefix | 19, H3 | H.264 quality; filename prefix |

`--settings-file` loads a UTF-8 JSON object. CLI flags override that file. It supports explicit `null` to reset the end time:

```json
{"previous_start":0,"previous_end":null,"motion_context":false}
```

Independent requests must not contain a previous file; previous-range settings are reset to 0/null when context is off. Continuation is Ref2VA / T2VA / L2VA only.
No automatic asset inheritance: upload every reference and previous file needed for each request.

## Job recovery

```powershell
python <skill>/scripts/h3_client.py status JOB_ID
python <skill>/scripts/h3_client.py resume JOB_ID --output-dir "C:\AI\outputs" --prefix "scene"
```

`generate --submit-only` prints the ID and returns. Otherwise the client waits up to `--wait-timeout` seconds (21600 default); `--poll-interval` defaults to 5 seconds. Upload timeout is independently `--upload-timeout` (1800 seconds).
Timeout/disconnection does not cancel GPU work. The server's single worker keeps monitoring a submitted ComfyUI prompt and does not start the next job until it finishes. If ComfyUI is terminated without writing history, the job can remain running; inspect Colab logs and restart the runtime after deciding to abandon that work.
API re-execution preserves same-engine jobs, but engine/runtime restart loses in-memory job state. Files remain under `/content/ComfyUI/output/h3_remote` until the runtime is discarded; copy important outputs to Drive or download them.
If the server's own ComfyUI submission connection fails, status is `submission_unknown` and the serial worker pauses permanently: ComfyUI may have accepted it. Inspect its queue/log before deciding to reset the runtime. Neither API nor client retries GPU submission automatically.

Output filenames contain prefix, local timestamp, seed, and short job ID. MP4 and TXT share the same stem. The client never replaces an existing file. `resume` downloads the existing output under a new timestamp; it does not regenerate.

TXT includes applied settings, original prompt, actual conditioning prompt, ordered source names, selected previous interval, processed previous-tail path, generated frame count, actual output metadata and repository commits. It does not contain the API token or HF token.
