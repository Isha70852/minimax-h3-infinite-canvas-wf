# 雪音畫布 Yukine Palette

[English](README.md) · [下載 Release](https://github.com/Isha70852/minimax-h3-infinite-canvas-wf/releases) · [給 AI 工具的操作說明（skill）](skills/h3-canvas-api/SKILL.md)

雪音畫布是一個在自己電腦上執行的「無限畫布」。把圖片、影片、聲音和文字放到畫布上，用線連起來，就能生成影片、圖片、音樂、語音，或讓參考角色照著影片動起來。

畫布本身不含 AI 模型，實際生成交給你選擇的服務：**RunningHub**（雲端）、**本機 ComfyUI**，或 **Google Colab**（免費／付費 GPU）。

## 可以做什麼

| 類型 | 功能 |
|---|---|
| 影片 | MiniMax H3：文字生影片、參考圖生影片、首尾幀、二採放大，以及接續上一段影片的「導演台」 |
| 動作遷移 | SCAIL-2：讓參考角色照著影片的動作動起來，或把影片裡的人換成你的角色 |
| 圖片 | MiniMax H3 Image 文生圖／多圖編輯、Z-Image Turbo、FLUX.2 klein 圖片編輯、MOSS Image、Anima |
| 音樂／語音 | YuE2 音樂、Qwen3 TTS、IndexTTS 2.5、Breeze TTS 2 |
| 自訂工作流 | 匯入自己的 ComfyUI API 工作流，選擇要在畫布上調整的欄位 |
| 輔助工具 | AI 提示詞助手、素材庫、素材檢視與 A/B 比較、裁切、抽取聲音、分鏡拼圖、群組 |

介面預設為牛皮紙配色，左上角的月亮／太陽按鈕可切換成原本的暗色配色（只改顏色，功能不變）。

## 快速開始（Windows）

**用 Release 版（最簡單）：** 下載並解壓 ZIP，先安裝 [Python 3.10 以上](https://www.python.org/)（勾選加入 PATH），再執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install-runtime.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

打開瀏覽器到 **http://127.0.0.1:8766**。之後雙擊 `啟動畫布.cmd` 就能啟動，不需要 Node.js。

**從原始碼安裝：** 另外需要 Node.js 20 以上。

```powershell
git clone https://github.com/Isha70852/minimax-h3-infinite-canvas-wf.git
cd minimax-h3-infinite-canvas-wf
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\start.ps1
```

更新前先關閉服務（Ctrl+C）並備份 `data/` 資料夾，你的專案和設定都在裡面。

## 連接生成服務

左側齒輪「連線設定 → 生成服務來源」可以新增多組來源並各自命名；每個節點都能選要用哪一組。

### RunningHub（雲端）
1. 把 `example_workflows/` 裡的工作流匯入你自己的 RunningHub 帳號。
2. 在設定填入你的 API Key，以及每個功能對應的工作流 ID。
3. 生成會使用你帳號的額度；Standard／Plus／Ultra 是要求的機型等級。

### 本機 ComfyUI
1. 自行安裝工作流需要的節點和模型，啟動 ComfyUI。
2. 在設定填入網址（預設 `http://127.0.0.1:8188`）。不需要工作流 ID，畫布會自己組好完整工作流送出。
3. 模型檔名要和你電腦上的一致（可在設定的「模型與 LoRA 檔名」修改）。

### Google Colab
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/Isha70852/minimax-h3-infinite-canvas-wf/blob/main/colab/Yukine_Palette_Colab.ipynb)

使用 `colab/Yukine_Palette_Colab.ipynb`，用法跟 RunningHub 一樣，但**不需要上傳任何工作流 JSON**：

1. **Cell 1**：勾選要用的功能，會自動勾好需要的模型；也可以改模型存放位置（例如 Google Drive）。
2. **Cell 2**：安裝 ComfyUI、所選功能的節點，以及 ComfyUI-Manager（可在 ComfyUI 網頁直接裝其他節點）。
3. **Cell 3**：下載模型（可重跑、可之後追加）。
4. **Cell 4**：啟動 ComfyUI。
5. **Cell 5**：建立安全連線，畫面會顯示 `H3_API_URL` 和 token，填進畫布的 Colab 來源即可。

所有節點（影片、圖片、音樂、TTS、動作遷移、自訂工作流）都能選 Colab。送出前畫布會先檢查 Colab 上有沒有需要的節點和模型。最後一格可以打開 ComfyUI 網頁介面，自己檢查範例或安裝套件。

> 舊版 `MiniMax_H3_MotionContext_Remote_20261102.ipynb` 仍保留手動生成介面；它的「匯入雙 JSON」已改成選用，不上傳也能讓畫布使用。

## 基本操作

1. 建立專案後，**雙擊空白處**（或右鍵）新增節點；把素材拖進畫布或從素材庫加入。
2. 把素材節點連到生成節點，填提示詞、調整參數，按「生成」。
3. 結果會出現在節點上，也會記在右側「專案生成內容」。執行中可以按「停止／取消」。

小技巧：
- **節點模板**：調好參數後可存成模板，之後新節點自動套用（只存參數，不存素材和文字）。
- **導演台**：要讓影片一段接一段，請在導演台按「生成此段」，它會把上一段影片當作畫面和聲音的延續。直接按影片節點的「生成影片」不會接續。
- **群組**：按住 Shift 多選節點，再按左側「群組」；可整組移動、排列、收合。
- **提示詞 `@`**：輸入 `@` 可插入已連接的素材標記。
- **Noise seed**：高級設定可固定 seed 重現結果；歷史紀錄可「沿用此 seed」。

## 功能說明

### 影片（MiniMax H3）
- 所有影片模式共用一個工作流；RunningHub 只需填一個「影片統一工作流 ID」（匯入 `MiniMax_H3_一採保留_二採Latent放大_無限畫布.json`）。
- 勾選「二採放大」可得到更高解析度；「同時保存一採影片」會兩個版本都留下。輸出為 24 fps。
- 圖片用途要對應模式：首幀接 first、尾幀接 last、參考圖接 reference。
- 上傳影片會自動轉成 24 fps，長度不限制，由各工作流自行裁切或分段。

### 圖片（MiniMax H3 Image）
- 在圖片生成節點的「功能」選 **MiniMax H3 Image 文生圖** 或 **圖片編輯（多參考圖）**。
- 圖片編輯最多可放 6 張參考圖：填好一張才會出現下一格；提示詞用 `<Picture 1>`、`<Picture 2>`… 指定是哪一張。
- 輸出比例可選「跟隨參考圖 1」或固定比例；畫素建議 4–16 MP，越大越慢、越吃顯存。
- 「高級功能」可加 LoRA、調 Steps／CFG 等。Text Encoder 與 H3 影片共用同一個檔案。

### 動作遷移／人物替換（SCAIL-2）
右鍵新增「動作遷移 / 人物替換」，連接一張**參考角色圖**和一段**動作影片**。

- **動作遷移**：保留參考圖背景，角色照影片動作動起來。
- **人物替換**：保留影片背景，把影片裡的人換成參考角色。
- **長度**：單段最多 81 幀；選「長影片」會自動分成多段接起來（最多 6 段），並保留原影片聲音。
- 參考圖預設「完整保留（補白邊）」，避免直式角色圖被裁掉頭。
- 「影片中要追蹤的人」描述影片裡的人（例如 `person`）；只換一個人時，把「最多追蹤人數」設為 1。
- **一次換多人**：把所有角色並排放在同一張參考圖裡，左到右的順序要對應影片中的人（先出現的排前面，同時出現的由左到右），「最多追蹤人數」設成人數，排序選 `left_to_right`。有剪接鏡頭的影片容易認錯人，建議用「起始幀」從所有人同時出現的地方開始。
- 預設是加速設定（6 步），一般不需要調整。

### 音樂與語音
- YuE2 可用歌詞生成音樂或翻唱；Qwen3、IndexTTS 2.5、Breeze TTS 2 可複製聲音或描述聲音。
- IndexTTS 2.5 可另外接一段「情感參考聲音」，情感權重使用 ComfyUI 官方的 Float 節點。
- Breeze TTS 2 的「缺少模型時自動下載」預設開啟，第一次執行會自動下載模型；若模型已放好可關閉。

### 自訂工作流
左側「工作流」可匯入 ComfyUI **API 格式** JSON：
1. 選分類並指定輸出節點。
2. 勾選要在畫布上調整的欄位（文字、數字、開關、選單、模型、seed、素材）。
3. 需要多張素材時使用「素材群組」，系統會依實際數量自動複製載入節點並接線。
4. 生成前可用「檢查映射／執行圖」確認結果。

更換 JSON 後節點編號可能改變，請重新確認映射。工作流與模型清單只存在本機。

### 素材檢視與比較
右側「專案生成內容」面板上方的「素材檢視」按鈕可瀏覽畫布生成的內容，也能加入電腦上的資料夾（不會複製或移動檔案）。點素材可查看提示詞和參數；選兩個圖片／影片可並排或拖曳比較。

## AI 提示詞模板

- **內建模板**放在 `backend/builtin_prompts/`，隨程式提供。
- **你自己的模板**存在 `data/prompts/`

## 讓 AI 工具操作畫布

在「設定 → 外部 AI 操作 API」開啟功能並複製權杖，再把 [skill](skills/h3-canvas-api/SKILL.md)、網址 `http://127.0.0.1:8766/api/automation/v1` 和權杖交給你信任的 AI 工具（例如 Claude Code、Codex）。它就能建立專案、上傳素材、寫提示詞並送出生成。

- 這個 API 不會給出你的服務金鑰，也不能執行系統指令。
- 只在本機使用，不要公開到網路上。
- 避免瀏覽器和 AI 同時編輯同一個專案。

## 資料與檔案位置

| 路徑 | 內容 |
|---|---|
| `src/`、`backend/` | 前端（React）與後端（FastAPI） |
| `workflows/` | 畫布實際使用的工作流與欄位對應 |
| `example_workflows/` | 可匯入 ComfyUI／RunningHub 的分享版工作流 |
| `colab/` | Google Colab notebook |
| `skills/` | 給 AI 工具的操作說明 |
| `data/` | **你的**專案、素材、設定、金鑰和模板（不要分享） |

### 進階：修改未開放的參數
想換掉介面沒有開放的模型或固定參數，可編輯 `workflows/` 裡對應的 JSON（先備份），保留節點編號和連線，改完重啟服務，再用預覽確認。各功能使用哪個 JSON 寫在 `workflows/*_registry.json`。`example_workflows/` 只是分享範例，修改它不會影響畫布。

## 授權與致謝

本專案程式碼採 [MIT License](LICENSE)。MIT 只涵蓋本專案程式碼，**不包含**模型、節點或生成內容；本專案也不散布任何模型權重。使用前請確認各模型的授權（部分為非商用）。第三方套件聲明見 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 與 `licenses/`。

**模型**（授權摘要，請以官方頁面為準）

| 模型 | 授權重點 |
|---|---|
| [MiniMax H3](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE)、[MiniMax H3 Image](https://huggingface.co/Comfy-Org/MiniMax-H3-Image) | 社群授權，有地區、商用、標示與使用限制（H3 Image 請以其模型卡為準） |
| [SCAIL-2](https://huggingface.co/Comfy-Org/SCAIL-2)（Wan 2.1 為基底）、[SAM 3.1](https://huggingface.co/Comfy-Org/sam3.1) | 依各模型卡授權 |
| [Z-Image Turbo](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)、[MOSS Image](https://openmoss.ai/MOSS-Image/)、[Qwen3-TTS](https://arxiv.org/abs/2601.15621) | Apache-2.0 |
| [FLUX.2 klein](https://help.bfl.ai/articles/7108141705-can-i-run-or-fine-tune-flux-2-klein-locally) | 4B 為 Apache-2.0；9B 為非商用 |
| [Anima](https://huggingface.co/circlestone-labs/Anima) | 非商用授權 |
| [YuE2](https://huggingface.co/m-a-p/YuE2-3B/blob/main/LICENSE) | 權重 CC BY-NC 4.0（非商用） |
| [Breeze TTS 2](https://huggingface.co/BreezeBlue/Breeze-TTS-2) | 程式碼 Apache-2.0；權重與輸出限研究／非商用 |
| [IndexTTS 2.5](https://huggingface.co/IndexTeam/IndexTTS-2.5) | Bilibili 模型使用協議 |
| 加速 LoRA、量化版、編碼器、VAE | 依各自上游授權 |

**感謝**

- **模型團隊**：MiniMax、SCAIL-2 與 Wan 團隊、Meta SAM、通義 Z-Image、Black Forest Labs、OpenMOSS、CircleStone Labs、M-A-P（YuE2）、Qwen、BreezeBlue、Bilibili IndexTeam。
- **ComfyUI 與 Comfy-Org**：核心引擎、官方節點與模型整理。
- **節點與模型作者**：
  [T8](https://github.com/T8mars/comfyui-minimax-h3-audio-T8)（H3 音訊節點、[IndexTTS 2.5 節點](https://github.com/T8mars/comfyui-indextts25-t8)、[4 步加速 LoRA](https://huggingface.co/t8star/minimax-h3-4step-turbo-loras-comfyui-exp)）、
  [Motion Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)、
  [Kijai / KJNodes](https://github.com/kijai/ComfyUI-KJNodes)、
  [VideoHelperSuite](https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite)、
  [lightx2v](https://huggingface.co/lightx2v/Minimax-h3-Turbo)、
  [LBH Latent Upscaler](https://github.com/LBH-123-AI/Comfyui_Minimax_h3_latent_Upscaler)、
  [Qwen-TTS 節點](https://github.com/flybirdxx/ComfyUI-Qwen-TTS)、
  [Breeze TTS 2 節點](https://github.com/Saganaki22/ComfyUI-Breeze-TTS-2)、
  [ListHelper](https://github.com/dseditor/ComfyUI-ListHelper)、
  [Goohai Tools](https://github.com/goohai/Goohaitools-comfyui)、
  [MieNodes](https://github.com/MieMieeeee/ComfyUI-MieNodes)、
  [Pika H3 Flex](https://huggingface.co/Pika-Labs/Pika-H3-Flex)。
- **服務與開源專案**：[RunningHub](https://www.runninghub.ai/)、React、Vite、XYFlow、FastAPI、Uvicorn、Lucide、Mediabunny。
