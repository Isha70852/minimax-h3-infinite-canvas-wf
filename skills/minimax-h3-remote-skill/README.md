# MiniMax H3 Remote skill

AI 入口是 [SKILL.md](SKILL.md)，完整參數與 API 是 [references/api.md](references/api.md)。
本資料夾可整份安裝到 AI 工具的 skills 目錄。需求：Python 3.10 以上。

```powershell
python -m pip install -r requirements.txt
$env:H3_API_URL="https://本次網址.trycloudflare.com"
$h3SecureToken = Read-Host "H3 API token" -AsSecureString
$env:H3_API_TOKEN = [System.Net.NetworkCredential]::new('', $h3SecureToken).Password
python scripts\h3_client.py health
```

先在 Colab 執行交付的 [MiniMax_H3_MotionContext_Remote_20261025.ipynb](../../colab/MiniMax_H3_MotionContext_Remote_20261025.ipynb) Cells 1–5、7，使用同一組 token。
環境變數須存在於啟動 AI 的程序；另一個終端的新設定不會自動傳到已開啟的桌面程序。

使用者可要求獨立生成、接續任一指定 MP4，或接續影片某個時間區間的結尾。
獨立生成用 `--no-motion-context`；接續用 `--previous`，區間用 `--previous-start` 與 `--previous-end`。
Ref2VA 的 `--video` 是參考素材，和前段 `--previous` 是不同角色。不要自動選擇上一個結果作前段。
未指定參數繼承 Colab 已套用設定；LoRA 串接保持使用者順序。

正常生成會下載成對 MP4/TXT。工作中斷後用 `status JOB_ID` 查詢，`resume JOB_ID --output-dir ...` 下載既有結果。
連線逾時不代表 GPU 已停止，不要直接重送生成。模型下載／自訂權重由 Colab 模型設定與下載格處理。
