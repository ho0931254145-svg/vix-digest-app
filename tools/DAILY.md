# VIX 日報 App 每日更新程序

這個 repo 同時是 GitHub Pages 網站（https://ho0931254145-svg.github.io/vix-digest-app/）。
App 的內容是**日報網頁的鏡像**：排程「每日強勢族群與 VIX 和四大指數研究」每個美股交易日約台北 07:45 重新發佈
https://claude.ai/artifact/BvJ5h6vb55n3F6DiYRqLWo ，這裡把它轉成 App 用的 index.html 再上線。不要自己改寫日報內容。

- `src/page.html`：日報原始檔（與 artifact 相同）
- `index.html`：`tools/build_snapshot.py` 把字型內嵌後的成品，push 到 main 後約一分鐘網站更新
- `tools/`、`src/` 由 `_config.yml` 排除，不會出現在網站上

## 步驟

在 repo 根目錄執行。任何一步失敗就停下來回報，**不要 push 半成品**。

1. 環境：`pip install -q fonttools`，確認在 main 且已 `git pull`。
2. 讀取日報：用 Artifact 工具的 `read`，`url` 填 `https://claude.ai/artifact/BvJ5h6vb55n3F6DiYRqLWo`、`path` 填 `index.html`，記下存檔路徑。
3. 鏡像：`python3 -I tools/mirror.py <存檔路徑>`
   - 結束碼 0：`src/page.html` 已更新且通過檢查，往下做。
   - 結束碼 3：App 已經是最新，**到此結束，不 commit**。
   - 結束碼 4：日報網頁還沒更新到最新交易日。等 5 分鐘後回到第 2 步重新讀取，最多重試 9 次（約 45 分鐘）；仍是 4 就不上線，回報「日報網頁未更新，App 未上線」。
   - 其他：不上線，回報錯誤訊息。
4. 建置：`python3 -I tools/build_snapshot.py src/page.html index.html`
5. 上線：
   ```bash
   git add src/page.html index.html
   git commit -m "daily update <日報日期 YYYY-MM-DD>"
   git push origin main
   ```
6. 驗證：等 1～3 分鐘，以下 7 個網址都要回 200，且首頁含日報日期（加 `?v=<commit>` 避開 CDN 快取）：
   ```bash
   for f in "" manifest.webmanifest sw.js icon-192.png icon-512.png icon-maskable-512.png apple-touch-icon.png; do
     curl -s -o /dev/null -w "%{http_code} /$f\n" "https://ho0931254145-svg.github.io/vix-digest-app/$f"
   done
   curl -s "https://ho0931254145-svg.github.io/vix-digest-app/?v=$(git rev-parse --short HEAD)" | grep -c "<日報日期 M/D> 收盤"
   ```

## 工具

| 檔案 | 用途 |
|---|---|
| `mirror.py` | 檢查 artifact 是否涵蓋最新已收盤交易日，是的話寫入 `src/page.html` |
| `check_page.py` | 資料物件能解析、日期一致、標題日期等於資料日期、字型連結與 PWA 設定都在 |
| `build_snapshot.py` | `src/page.html` → `index.html`（字型子集化後內嵌，離線可用） |
| `unsnapshot.py` | `index.html` → `src/page.html`，本機 `deploy.sh` 手動上線時用來同步原始檔 |
| `update_data.py` | 把新的指數收盤併入 `DATA`、`QD`、`OV`（日報排程的工具，App 流程不用） |

## 本機手動上線

`deploy.sh`（只在本機，不在 repo）會先 `git pull`，再用 `tools/unsnapshot.py` 從新的 index.html 還原 `src/page.html`，兩個一起 commit。
