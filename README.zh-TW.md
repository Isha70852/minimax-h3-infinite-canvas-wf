# MiniMax H3 無限畫布 · Wizard Forest Studio

[English](README.md) · [下載 Release](https://github.com/Isha70852/minimax-h3-infinite-canvas-wf/releases) · [API skill](skills/h3-canvas-api/SKILL.md)

本機執行的無限畫布，整合圖片、影片、音樂、語音及提示詞撰寫，支援 **RunningHub 與本機 ComfyUI**。不包含模型權重或生成引擎。

## 自訂 API 工作流（本機設定）

左側「工作流」可匯入 ComfyUI **API 格式** JSON。這是工作流設定介面，不是另一個節點編輯器；原本內建影片、圖片、音樂與 TTS 不受影響。

1. 選分類（影片／圖片／音樂／TTS／3D，或新增分類），指定真正的輸出節點。
2. 選擇要曝露的常數欄位：文字、數字、開關、選單、模型檔名、seed，或素材載入節點的檔名欄位。其他值沿用 JSON。文字可連接文字節點。
3. 多素材使用「素材群組」：指定載入節點、檔名欄位、輸出 slot、接收節點、帶 `{index}` 的輸入名稱、起始索引及最大數量。系統依實際數量複製載入節點並接線，不受範例原有連線數限制。H3 Ref2V 可配置圖片 9、影片 3、聲音 3；輸入名稱及 slot 必須依該節點實際定義填寫，不能把圖片規則直接套到音訊或影片。
4. 引用標記可明訂為 `<Picture {index}>`、`<Video {index}>`、`<Audio {index}>`。例如圖片群組名「圖片」，文字中的 `@圖片2` 會換成第二張實際輸入的標記。不同媒體各自編號；不需要標記的模型留空即可。生成前使用「檢查映射／執行圖」。
5. 模式可指定各輸出 slot 的 bypass 去向，或重新連接／斷開指定輸入。不可僅刪除節點而保留懸空接線；只有輸出所需分支會提交。必填素材所在分支仍有效時，不能直接留空。
6. 「模型庫」維護 UNet、VAE、CLIP、LoRA 等實際檔名供下拉選擇；不下載模型，也不保證遠端已安裝。多個 LoRA 需在原圖保留對應節點，分別曝露名稱及強度。
7. 每組 RunningHub 來源分別填入對應工作流 ID；ComfyUI 直接提交編譯後 API graph。Colab 僅允許影片分類，需目前支援 `/canvas` 原生圖橋接的 notebook，且服務端已安裝此圖需要的節點／模型。
8. 在自訂生成節點存成帶標籤的模板，可在管理面板設為該工作流預設模板。模板保存參數與提供者，不保存素材或文字節點連線。

**節點編號改變會影響參數／接線映射。** 替換 JSON 後必須重新確認映射；儲存產生新版本，既有畫布節點與歷史任務固定原版，不會自動轉換。分類名稱不代表服務端必然支援；3D 目前提供標準檔案輸出下載，不提供 3D 預覽或任意自訂節點協議。API JSON 無法可靠推導所有型別、可選輸入或輸出 slot；請以節點文件和服務端定義核對。工作流、模型庫、模板儲存在本機 data 資料庫，不自動加入分享包。

外部 AI API 同樣支援 `/custom-workflows`、`/custom-workflows/inspect`、`/custom-workflows/{id}/versions/{version}`、`/custom-workflows/models/library`、`/custom-workflows/presets`；完整路由與型別見啟用後的 `/api/automation/v1/schema` 以及 [操作 skill](skills/h3-canvas-api/SKILL.md)。

H3 Ref2V 缺少載入節點時，可在素材群組按「H3 參考聲音」或「H3 參考影片」自動補齊。聲音使用 LoadAudio；影片使用 LoadVideo → GetVideoComponents，逐份複製完整鏈，影格與選用原音維持相同索引。原音不占獨立 Audio 引用編號。新增後儲存為新版本；既有畫布節點需選用新版本的模板或重新建立節點。

## 功能

- 畫布拖曳／縮放、小地圖、節點調整大小、素材連線及生成歷史。
- MiniMax H3 文生影片、參考生影片、首尾影格，以及以先前 MP4 畫面／聲音延續的導演台。
- MOSS Image、FLUX.2 klein 圖片編輯、Z-Image Turbo、Anima；YuE2 音樂、Qwen3 TTS、IndexTTS 2.5、Breeze TTS 2。
- 跨專案共用資產、專案素材、回收區、預覽、圖片／影音裁切、抽取聲音、標記 Panel 的分鏡圖拼接。
- 串流 AI 提示詞助手，可引用前段 AI 或手動內容，選擇／修改模板。
- 可開關並使用權杖的外部操作 API，讓 AI 編程工具查詢功能、上傳素材、調整參數及逐段生成。

## Windows 快速啟動

**下載 Release ZIP：**解壓到可寫入的資料夾，安裝 Python 3.10 以上並加入 PATH，執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

開啟 **http://127.0.0.1:8766**。安裝完成後也可雙擊 `啟動畫布.cmd`。Release 已附建置好的前端，執行不需要 Node.js。

**從原始碼安裝：**準備 Python 3.10+、Node.js 20 LTS 或更新版本：

```powershell
git clone https://github.com/Isha70852/minimax-h3-infinite-canvas-wf.git
cd minimax-h3-infinite-canvas-wf
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

套件裝在本資料夾的 `.venv`、`node_modules`，快取也留在本地。更新前 Ctrl+C 關閉服務，備份 `data/`，不要用他人的 data 覆寫。

## 連接生成引擎與操作

**RunningHub：**將 `example_workflows/` 的公開工作流匯入自己的帳號，處理缺少的模型／節點，於設定填入自己的 API Key 和工作流 ID。一般影片、MP4 motion context、各圖片與音訊功能分別設定 ID。公開檔案不含私人 ID 或金鑰。Standard／Plus／Ultra 代表要求使用的機型；生成會消耗服務額度。

**本機 ComfyUI：**另行安裝工作流需要的模型及自訂節點，啟動後填寫網址（預設 `http://127.0.0.1:8188`）。本機不需要工作流 ID，畫布直接提交 API JSON 並處理素材上傳及結果。模型檔名須與伺服器一致。

新增專案後，雙擊空白畫布建立節點、上傳並連接素材，選擇功能、撰寫提示詞、調整參數後提交。設定可調整新影片節點的預設值、AI 來源／模型／模板。公開工作流的提示詞及素材輸入刻意留空，請先選擇自己的內容。

使用導演台逐段生成，後段會上傳前段 MP4 作為畫面與聲音上下文，不需要 latent。每段提示詞與素材可不同；裁掉重疊畫格後片長可能較短。最終影片拼接是另外的編輯步驟。

## 讓外部 AI 操作

在「設定 → 外部 AI 操作 API」啟用並複製一次性顯示的權杖，把 [skill](skills/h3-canvas-api/SKILL.md)、本機網址及權杖交給你授權的 AI 工具。網址：`http://127.0.0.1:8766/api/automation/v1`；請求帶 `Authorization: Bearer TOKEN`。

可查詢模型功能／參數結構、建立或修改專案、上傳圖片／影片／聲音、撰寫提示詞、提交生成及取得結果，亦可逐段使用 motion context。接口不提供服務金鑰或系統命令執行。關閉後拒絕新請求，已提交任務不會取消。避免瀏覽器和 API 同時編輯同一專案，完成後重新載入。原本網頁使用的內部 API 與此開關獨立；保持 localhost，不要直接作為公開多人服務。

## 檔案位置

| 路徑 | 用途 |
|---|---|
| `src/`、`backend/` | React/Vite 前端及 FastAPI 後端 |
| `workflow_template.json`、`workflows/` | 已清理的執行模板及參數／節點映射，修改時須保持對應 |
| `example_workflows/` | 分享用 UI/API 工作流，節點編號可與執行模板不同 |
| `skills/h3-canvas-api/` | 無限畫布操作 skill |
| `colab/`、`skills/minimax-h3-remote-skill/` | **獨立**的 Google Colab H3 工具與操作 skill，並非畫布後端 |
| `data/` | 本機 SQLite、設定、專案、素材、生成結果及認證資訊，不可公開 |

Colab 文件可在 Google Colab 開啟，依筆記本設定執行環境與認證，再使用對應 remote skill；不會自動接入無限畫布。


## 節點模板與導演台

在影片、圖片、音樂或 TTS 節點調好參數後，展開「節點模板」儲存名稱與標籤，可將任一模板設為該分類預設。從左側選單的「模板」可管理模板。新節點優先套用預設模板，既有節點可手動選取；不保存素材或劇情文字。僅儲存在本機 data。

**延續影片必須從導演台按「生成此段」。直接按影片節點的「生成影片」不會自動接續前段。** AI 透過 API 提交 motion context 時會自動建立／更新導演台；重新載入專案即可查看。

## Noise seed 與 AI 提示詞檔案

影片節點的高級功能可填寫 **Noise seed**；選擇 `randomize` 每次隨機，或選 `fixed` 並填入 seed 以重用。生成結果、歷史與導演台顯示此次實際 seed，可按「沿用此 Noise seed」或套用歷史版本。API 使用 `spec.noise_seed` 十進位字串（0–18446744073709551615），回傳 `seed` 亦為字串，避免 JavaScript 大整數精度損失。相同 seed 不保證不同模型、參數或環境的結果一致。RH 幣只適用 RunningHub；本機 ComfyUI 不需回傳用量欄位，本機顯示的是包含排隊及儲存的任務總耗時。

AI 撰寫提示詞模板分兩處：**內建模板**隨程式提供，位於 `backend/builtin_prompts/`（H3、圖片、音樂、TTS 範例），唯讀。**你的模板**只存在本機 `data/prompts/`：每個 UTF-8 `.md`／`.txt` 檔為一個模板，檔名（不含副檔名）為顯示名稱，全文為模板內容。`data/` 不會進 Git 也不會打包，所以個人模板永遠不必再從 commit 移除。這些與生成工作流、節點參數模板不同。

在 AI 撰寫設定新增／編輯後按「儲存設定與模板」，會寫入 `data/prompts/`。修改內建模板會建立同名個人覆寫，改回原文即恢復內建；刪除或改名內建模板只會隱藏（記錄於 `data/prompts/.hidden.json`）。覆寫與刪除前的內容備份在 `data/prompts/.trash/`。也可直接編輯 `data/prompts/` 內的檔案，重新開啟設定即可讀取；若外部檔案已變更，儲存會要求重新載入。首次啟動時，舊的專案根目錄 `prompts/` 中與內建不同的檔案會一次性複製到 `data/prompts/`；該資料夾現在已被 Git 忽略。若要把新模板公開給所有使用者，請放進 `backend/builtin_prompts/`。

## 進階：修改未開放的模型與參數

1. 先備份要編輯的 JSON。所有影片模式共用 `workflows/video_unified.json`，由 `workflows/video_registry.json` 指定。舊 `workflow_template.json` 與 `video_motion_mp4.json` 保留為歷史檔案，不再作為目前影片執行圖。
2. 圖片／音訊請先查看 `workflows/image_registry.json`、`workflows/audio_registry.json`，找到功能的 `template`；未指定 template 的音訊使用對應 `<功能 ID>.json`。修改執行 JSON 中載入節點的實際 text encoder／VAE 檔名或其他固定輸入；服務端必須已安裝相容模型與節點。`example_workflows/` 只是分享範例，修改它不會影響畫布執行。
3. 保留節點 ID、class_type、連線及輸入型別。介面／API 已開放的參數會在編譯時覆寫 JSON 預設值，應從介面或節點模板設定；FLUX encoder 的自動配對由 image registry 的 `model_clip` 控制，也需同步調整。
4. 若換工作流導致節點 ID 或輸入名稱改變，更新對應 registry 映射（影片另有 `video_registry.json`）；新增可調欄位可能需要同步修改 schema、編譯器和介面。只換現有固定載入節點的檔名通常不需改程式。
5. 修改後重啟服務。先用 `/workflow/preview` 檢查實際產生的工作流，再自行決定是否提交付費生成；預覽不證明遠端模型存在。RunningHub 仍需設定工作流 ID，本機 ComfyUI 不需要。應用程式會提交編譯後的圖，因此未被編譯器覆寫的固定輸入會採用你修改的執行 JSON。

## 授權與致謝

本專案程式碼採既有 [MIT License](LICENSE)，不會把模型、節點、依賴或生成內容重新授權為 MIT。以下依 2026-10-25 查閱的官方資料摘要，仍應核對實際權重版本與服務條款；本專案不散布模型權重。依賴聲明見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 與 `licenses/`。

感謝各模型團隊、ComfyUI 與自訂節點作者、RunningHub，以及前端與影音開源社群。

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

特別感謝：

- [KJ / ComfyUI-KJNodes](https://github.com/kijai/ComfyUI-KJNodes)
- [T8 / comfyui-minimax-h3-audio-T8](https://github.com/T8mars/comfyui-minimax-h3-audio-T8)
- [Motion Context / ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)

## 新版一採／二採統一工作流

請將 `example_workflows/MiniMax_H3_一採保留_二採Latent放大_無限畫布.json` 匯入 RunningHub，將其 ID 填入設定中的「影片統一工作流 ID」。一般影片、motion context、二採、motion context＋二採都使用這一個 ID，舊的獨立 motion ID 不再使用。本機 ComfyUI 需安裝對應 T8 節點及模型，但不需工作流 ID。

- 影片高級功能勾選「二採放大」，`scale_by` 預設 2，其餘含一採排程沿用提供的工作流。可展開二採完整參數自行覆寫。兩個輸出皆為 **24 fps**。
- 勾選「同時保存一採影片」會保留兩種影片，取消只保存二採，一採仍會在內部執行。結果名稱標示一採／二採，素材另有 `generation_pass: first/second` 及 `output_node_id` 供 API 判斷。
- 導演台按「生成此段」才會延續前段。預設優先使用前段最近成功任務的一採，沒有則用二採；可從來源選單指定影片。沒有前段時會跳過兩個 trim。
- `audio_mode` 預設 `native`；`lock_source`、`remix_source` 需另外選擇 drive audio 聲音素材，或連接聲音節點至專用輸入，不會自動占用參考聲音編號。一、二採共用相同素材。圖片用途需指定：首幀 I2VA 接 first、尾幀 L2VA 接 last、首尾 FL2VA 接 first＋last、參考 Ref2VA 接 reference；不符合模式會在送出前提示。
- 每個影片節點可覆寫 RunningHub 的 Standard／Plus／Ultra 機型，或沿用全域設定；不影響本機 ComfyUI。二採高解析度需要較大顯存。
- 節點名稱可直接編輯；提示詞的 `@` 選單從已連接的素材中挑選，在游標位置插入。影片放大會沿用預覽的靜音狀態。
- 發布包只包含 `backend/builtin_prompts/` 的內建模板；`data/prompts/` 的個人模板永遠不會打包。

AI 操縱端請重新讀取 `/catalog`，依 Generation schema 設定 `seed_mode`、`audio_mode`、`drive_audio_asset_id`、`two_pass`、`save_first_pass`、`two_pass_parameters`、`instance_type`。二採預設值由 `/catalog.config.video_two_pass_parameters` 提供，接法請參考隨附 skill。

## 本機素材檢視與比較

左上「素材檢視」開啟完整分頁。畫布生成的圖片、影片、音樂會自動列入；可輸入資料夾路徑，或按「選擇」瀏覽本機磁碟，再按「加入」。包含子資料夾，檔案不會被複製或搬動；移除來源也不會刪檔。新增檔案後按「重新掃描」。來源路徑與縮圖快取分別保存在本機 SQLite 與 `data/archive-thumbnails/`，不包含於分享包。

點選素材可預覽、複製提示詞、查看參數和原始紀錄。支援畫布任務紀錄、Colab 同名 TXT 的 `PROMPT BEGIN/END`、ComfyUI 媒體內嵌 prompt/workflow、PNG 的 WebUI parameters 與 JPEG/WebP EXIF UserComment，以及音樂檔的媒體標籤。不同來源分開顯示，不自動覆蓋衝突值；未保存的生成資訊無法還原。ComfyUI 參數來自靜態接線分析，不是重新執行工作流。若電腦有 ffprobe，會顯示更完整的串流資訊；沒有時使用既有 ffmpeg 讀取標籤。瀏覽器無法播放的編碼仍可查看可讀取的參數。

檢視分頁可選兩個圖片／影片後按「比較」；畫布左側也有 **A/B** 按鈕，從目前專案選擇。可切換並排、直桿拖曳及交換左右。影片使用靜音同步播放與共同時間軸，以較短影片為限；這是預覽同步，非逐影格校準。不同尺寸維持比例並補空白，不會裁切原檔。

素材檢視入口位於右側「專案生成內容」上方，預設顯示目前專案素材，可切換全部專案；外部資料夾獨立於專案範圍。畫布新增選單也能建立「圖片／影片比較」節點，將兩個來源接到 A、B 即可並排或直桿比較。影片聲音可選 A、B、兩者或靜音。首／尾幀模式使用對應圖片框，自動設定用途；聲音、影片另行加入，送出仍使用標準 Picture／Audio／Video 編號。

### 畫布操作與播放
- 按住 Shift 多選未分組節點，再按左側「群組」。拖曳群組標題可整組移動；「排列」將成員排成網格，「收合／展開」保留原本相對位置，「解散」保留節點與連線。不支援巢狀群組。
- 左側連線開關只隱藏連線，不移除引用。執行中的節點帶有淡藍光暈。
- 節點名稱在 Enter 或離開欄位時儲存，Escape 取消此次編輯。新增選單超出可用高度時可捲動。
- 設定中的全域播放音量立即套用現有與新增播放器，保存在此瀏覽器；各播放器靜音狀態仍獨立。
- 生成結果、素材與專案列表分批顯示，可按「載入更多」；畫布運行狀態仍持續更新。
- AI 與人可同時查看、播放，但不建議同時編輯同一專案。Automation PUT 有 If-Match 檢查，網頁存檔仍是整份畫布更新，沒有完整多人協作合併。
- ChatGPT OAuth 訂閱生圖尚未提供：官方 Sign in with ChatGPT plan usage 預覽限制明列 image generation 不支援，不能將 Codex 內建生圖視為此應用可直接呼叫的訂閱 API。參見 https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations 。

### Colab 影片提供者（20261102）

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Isha70852/minimax-h3-infinite-canvas-wf/blob/main/colab/MiniMax_H3_MotionContext_Remote_20261102.ipynb)

兩份檔案分別是 ComfyUI 視覺工作流與 API graph，不是二選一。請從 `example_workflows/` 下載，GitHub 開啟檔案後按 Download raw file：

- [MiniMax_H3_一採保留_二採Latent放大_無限畫布.json](example_workflows/MiniMax_H3_一採保留_二採Latent放大_無限畫布.json)
- [MiniMax_H3_一採保留_二採Latent放大_無限畫布_api.json](example_workflows/MiniMax_H3_一採保留_二採Latent放大_無限畫布_api.json)

此版本發布後，上方按鈕即可從公開 GitHub 直接開啟 Colab。倉庫中須保留 notebook 與兩份 JSON；不必另外保留私人 Google Drive 副本。若想保留個人修改，可選「檔案 → 在雲端硬碟中儲存副本」。每位使用者使用自己的執行階段，不會共用你的執行階段或 token。

1. 使用 `colab/MiniMax_H3_MotionContext_Remote_20261102.ipynb`，完成安裝、啟動 ComfyUI，於「匯入原版 JSON 並建立無限畫布 API」格上傳下列**兩份 JSON（缺一不可）**。執行該格及 Cell 7；若沿用已執行的 runtime，更新 notebook 後也要重跑這兩格。
2. 畫布設定填入 Cell 7 的 **H3_API_URL** 與 **H3_API_TOKEN**，儲存。不是「公開 ComfyUI 網頁」的 tunnel URL。Token 僅留在本機後端，可在設定移除。
3. 影片節點或影片預設參數選擇「Colab · 影片」。沿用現有影片工作流、所有參數與素材接線；由畫布編譯完整圖後呼叫 `/prompt`，不是限制一張圖／一段影片的 `/canvas/generate`。一採、二採和導演台 Motion Context 均走相同流程。圖片、音樂與 TTS 提供者不變。
4. 提交前透過 `/object_info` 檢查節點與模型檔名；在影片模型、LoRA 設定填入 Colab 實際安裝名稱。未曝露的 VAE、encoder 仍依 `workflows/video_unified.json`，需要時依進階修改說明調整。不自動替換模型或下載缺少的模型。
5. 圖片／影片／聲音分別上傳 `/upload/image`、`/canvas/upload/video`、`/upload/audio`；輪詢 `/history/{prompt_id}`，透過帶認證的 `/view` 保存輸出。Notebook 新增的 `/object_info`、`/upload/audio`、`/view` 繼承全域 Bearer 認證。沒有 WebSocket 百分比推播，也沒有 RH 幣欄位；顯示狀態與畫布實測耗時。
6. Colab runtime／tunnel 中斷時原工作可能仍在執行，先確認遠端狀態，不要直接重送。新任務使用設定中的新 URL；既有任務保留提交時 URL。此整合已做本機模擬檢查，未代表已驗證 Colab GPU 實跑。

連接線顯示開關會記住此瀏覽器上次狀態。群組展開和收合都可拖曳邊框控制點調整尺寸，兩種尺寸分開儲存；收合尺寸不覆蓋展開尺寸，子節點相對位置不變。

舊版橋接若沒有 `/object_info`，改用 `/health` 與端點清單確認，再由 ComfyUI 驗證提交的工作流。沒有 `/view` 時，一採／二採改從 `/canvas/result/{prompt_id}/{first|upscaled}` 下載。聲音參考仍需要更新後的 `/upload/audio` 端點。

### 多組生成來源與取消
設定中的「生成服務來源」可新增及命名 ComfyUI、RunningHub、Colab 連線。原本三組連線保留為預設，舊模板不需修改。節點模板可儲存指定來源；節點也可手動改選。舊版 20261102 Colab 僅支援影片；Universal notebook 支援所有節點。每組 RunningHub 有自己的金鑰、規格與可收合的工作流 ID；相同 ID 合併顯示，勾選「拆開編輯各功能」可分別修改。來源與金鑰只存本機，分享模板的來源 ID 必須改選收件者自己的來源。執行中來源不可刪除或更換連線／金鑰。

生成中的影片、圖片、音樂、TTS 與導演台段落提供「停止／取消」。提交中的取消會等取得遠端任務 ID 後送出，避免遺失遠端任務；正在完成的結果可能先回傳。ComfyUI 使用指定任務的 queue delete / interrupt，請使用支援 prompt_id 的新版 ComfyUI；RunningHub 使用官方取消 API，不保證退還已產生的用量。Colab 需更新原版 JSON／畫布 API 儲存格並重跑 Cell 7，才能提供 `/canvas/cancel/{prompt_id}`；舊橋接不支援時顯示失敗原因並繼續追蹤原任務，不假裝已停止。

### 手動 Sigma 採樣
影片高級設定可選 BasicScheduler（原本預設）或 ManualSigmas。一採的 ManualSigmas #358 直接接 SamplerCustomAdvanced #125 的 sigmas；手動模式的一採 Steps／Scheduler 不生效，預設序列為 `1.0, 0.972973, 0.923077, 0.8, 0.571429, 0.333333, 0.0`（6 個區間）。支援模板及導演台，二採精修規劃器保持原設定。服務端須有 ManualSigmas 節點（新版 ComfyUI 或對應 KJNodes 版本）。
分享 JSON 已附可選的 ManualSigmas，預設仍接 BasicScheduler；直接在 ComfyUI 網頁使用時可將 #358 接到 #125 的 sigmas。畫布提交時會自動切換並排除未使用節點。RunningHub 建議更新已上傳的工作流為新版 example_workflows 中的 JSON；若新建工作流，記得更新來源的 ID。Colab 請重新匯入對應兩份 JSON。

Colab v0.5.1：移除 Cell 3-b 的模型預設覆寫。Cell 5 後的「⑥ 匯入雙 JSON」格不檢查 UNet／LoRA；其他模型與節點診斷僅警告，實際生成由 ComfyUI 驗證。原本 Cell 6 手動面板保留。取消、聲音上傳及輸出下載端點由 Cell 7 統一註冊；更新匯入格後，請貼上／執行完整新版 Cell 7。取消失敗僅顯示「取消失敗」。

## 動作遷移／人物替換（SCAIL-2）

右鍵新增「動作遷移 / 人物替換」節點，連接**參考人物圖片**、**動作來源影片**與（選用）文字節點。

- 模式：**動作遷移**保留參考圖背景；**人物替換**保留影片背景（SCAIL `replacement_mode`）。
- 長度：**單段**最多 81 幀；**長影片**自動分段接續——每段 81 幀、步進 76 幀，以前段最後 5 幀為錨點，去除重疊並做色彩校正後合併，保留原影片聲音。依官方 *Character Replacement (SCAIL-2 Extend)* blueprint 的做法在同一張 API 圖內展開，不需要 Mie loop 節點；段數上限 6（上傳影片仍限 15 秒）。
- 預設為加速版：Distill LoRA 0.8、6 步、CFG 1、shift 5；寬高 32 的倍數。高級設定可調模型、步數、LoRA 強度、pose 強度／區間、SAM3 門檻、最多人物、排序與人物索引。
- 可存成節點模板（分類「動作遷移」），支援 ComfyUI、RunningHub（來源設定的工作流 ID 新增「SCAIL-2 動作遷移」欄位）與 Colab。
- 節點：ComfyUI 官方 `WanSCAILToVideo`、`SCAIL2ColoredMask`、`SAM3_VideoTrack`、`ColorTransfer`、`BatchImagesNode`，加 VideoHelperSuite 讀寫影片。需新版 ComfyUI。
- 模型（Comfy-Org 官方 HF）：`wan2.1_14B_SCAIL_2_int8_convrot`、`wan2.1_SCAIL_2_DPO_lora_bf16`、`umt5_xxl_fp8_e4m3fn_scaled`、`clip_vision_h`、`Wan2_1_VAE_bf16`、`sam3.1_multiplex_fp16`；加速 LoRA `lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16`（官方 blueprint 指向 Kijai/WanVideo_comfy）。
- 範例：`example_workflows/motion_scail2_single_無限畫布.json`（已移除 bypass 的慢速路徑與開關，KJ 節點換成官方節點）、`motion_scail2_single_無限畫布_api.json`、`motion_scail2_extend_無限畫布_api.json`（3 段長影片）、`motion_scail2_loop_MieNodes_無限畫布.json`（原 Mie loop 版，僅供 ComfyUI 手動使用，需要 ComfyUI-MieNodes 與 KJNodes）。

## Colab Universal 遠端運算（20261112）

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Isha70852/minimax-h3-infinite-canvas-wf/blob/main/colab/H3_Canvas_Universal_Colab_20261112.ipynb)

`colab/H3_Canvas_Universal_Colab_20261112.ipynb` 讓 Colab 像 RunningHub 一樣被畫布呼叫：畫布在本機組裝完整 API 圖，Colab 只負責執行。**不需要上傳任何 JSON**，素材由畫布前端上傳。

1. Cell 1 勾選功能（H3 影片、動作遷移、圖片、YuE2、Qwen3／IndexTTS／Breeze TTS），自動預勾畫布預設模型，可個別增減；可改模型根目錄（例如 Google Drive）或單一模型的資料夾，外部資料夾自動寫入 `extra_model_paths.yaml`。模型來源優先使用 Comfy-Org 官方 Hugging Face，並放進 ComfyUI 對應類別資料夾（diffusion_models、text_encoders、vae、loras、clip_vision、checkpoints、audio_encoders、latent_upscale_models、TTS）。
2. Cell 2 只安裝所選功能需要的節點；Cell 3 下載所選模型（可重跑、可追加）；Cell 4 啟動 ComfyUI 並列出缺少的節點。
3. Cell 5 建立 Bearer token API 與 HTTPS tunnel；在畫布「生成服務來源」的 Colab 填入 `H3_API_URL` 與 token。所有節點（影片、圖片、音樂、TTS、動作遷移、自訂工作流）都可選 Colab。
4. 提交前畫布會用 `/object_info` 檢查節點與模型檔名，缺模型會直接提示。

舊的 20261102 notebook 保留手動生成介面；其「⑥ 匯入雙 JSON」改為選用（預設不上傳），畫布照常透過 `/prompt` 送出。
