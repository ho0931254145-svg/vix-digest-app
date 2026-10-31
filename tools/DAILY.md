# VIX 日報每日更新程序

這個 repo 同時是 GitHub Pages 網站（https://ho0931254145-svg.github.io/vix-digest-app/）。
`src/page.html` 是日報原始檔，`index.html` 是用 `tools/build_snapshot.py` 把字型內嵌後的成品，push 到 main 後約一分鐘網站就會更新。
`tools/` 與 `src/` 由 `_config.yml` 排除，不會出現在網站上。

## 步驟

在 repo 根目錄執行。任何一步失敗就停下來回報，**不要 push 半成品**。

1. 環境：`pip install -q fonttools`（build_snapshot.py 需要），確認在 main 且已 `git pull`。
2. 資料：
   ```bash
   python3 -I tools/daily_data.py src/page.html
   ```
   - 結束碼 3 = 沒有新交易日（週末、美國假日），**到此結束，不 commit**，回報「無新收盤」。
   - 成功時會更新 `PX`、`DATA`、`QD`、`OV` 四個資料物件，並印出指數收盤、ETF 與個股漲跌排行。這些物件只能用腳本改，不要手動編輯。
   - `src/rows.json` 是暫存檔，不要 commit。
3. 文字：依當天研究結果改寫 `src/page.html` 中所有跟日期有關的文字（下一節列出位置）。
4. 檢查：`python3 -I tools/check_page.py src/page.html`，必須顯示 `page checks passed`。
5. 建置：`python3 -I tools/build_snapshot.py src/page.html index.html`
6. 上線：
   ```bash
   git add src/page.html index.html
   git commit -m "daily update <最新交易日 YYYY-MM-DD>"
   git push origin main
   ```
7. 驗證：等 1～3 分鐘，以下 7 個網址都要回 200，且首頁內容含最新日期（加 `?v=<commit>` 避開 CDN 快取）：
   ```bash
   for f in "" manifest.webmanifest sw.js icon-192.png icon-512.png icon-maskable-512.png apple-touch-icon.png; do
     curl -s -o /dev/null -w "%{http_code} /$f\n" "https://ho0931254145-svg.github.io/vix-digest-app/$f"
   done
   curl -s "https://ho0931254145-svg.github.io/vix-digest-app/?v=$(git rev-parse --short HEAD)" | grep -c "<最新日期 M/D> 收盤"
   ```

## 要改寫的文字

日報是「最近兩個交易日」滾動格式：原本的「前一日、最新日」改成「原最新日、新的最新日」。例如 10/29、10/30 → 10/30、11/2。

| 位置 | 內容 |
|---|---|
| `.appbar` | 最新日期、VIX、做多評分、建議倉位 |
| `.eyebrow .live` | `YYYY-MM-DD 收盤` |
| 首頁導言 | 「A 是 M/D–M/D 大盤…」的兩個日期 |
| 指數卡片（`.vixcell` 與其後四格） | VIX、S&P 500、NASDAQ、道瓊、Russell 2000 收盤與漲跌，VIX 後面接狀態標籤 |
| `.verdict` | 期限結構（VIX3M − VIX）、做多評分「前值 → 新值」、建議倉位「前值 → 新值」 |
| `p.note`（顏色慣例那段） | 台北更新日期、以哪天收盤為準、各數值的資料來源 |
| 近一年走勢圖標題、日期查詢說明 | 一年區間、哪些日期暫用 Yahoo 收盤 |
| 研究邏輯流程（序） | VIX 四層檢查的數值、輸出的評分與倉位 |
| 綜合結論 | 日期、倉位與理由、三個開關的狀態 |
| A-1 最近兩日大盤 | 兩日收盤與漲跌表（含本週、本月欄）、兩日重點、盤後、下一個交易日與本週行事曆 |
| A-2 VIX 研判總覽 | 標題日期、指標表（兩日值與判讀）、評分調整理由 |
| A-3 最近一年走勢 | 區間、一年統計表（起點、終點、漲跌、最高與最低收盤）、說明段落 |
| A-4 強勢族群 | 日期、強勢與走弱名單（用 daily_data.py 印出的漲跌） |
| B ETF 分析 | 類股排行、主題、風格與市值、跨資產四張表的日期與數字，配置結論 |
| C 年度表 2026 列 | 「2026 至 M/D」的年內漲幅、VIX 最新值、年均值 |
| 資料來源 | 當天實際用到的來源與日期 |

規則：

- 漲用 `class="up"`（紅）、跌用 `class="down"`（綠），負號用 `−`（U+2212），千分位逗號、百分比兩位小數，跟現有寫法一致。
- 做多評分與建議倉位用當天研究第 0-8 節的結論；倉位 = 評分 × 10%。前值取頁面上原本的新值。
- 只改文字與表格內容，不改 HTML 結構、class、`<script>` 與 `<style>`。
- 查不到的數字寫「未取得」，並在資料來源註明，不要估計後當成實際值。
- 每檔漲跌以 Yahoo Finance 收盤（新交易日對前一交易日）計算；指數收盤以 daily_data.py 抓到的值為準。

## 本機手動上線

`deploy.sh`（只在本機，不在 repo）會先 `git pull`，再用 `tools/unsnapshot.py` 從新的 index.html 還原 `src/page.html`，兩個一起 commit，所以手動上線的內容隔天會被排程沿用，不會被蓋掉。
