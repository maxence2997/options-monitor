# 🎯 美股期權模擬競賽 — 任務清單

> 比賽期間：2026/03/17 - 2026/09/15（約 26 週）  
> 初始資金：$1,000,000  
> 平台：Moomoo 富途（模擬盤）  
> 策略：SPY Iron Condor + NVDA Wheel + QQQ Bull Call Spread + Hedge Put

---

## 📌 策略速查

| 策略 | 標的 | 資金佔用 | 張數 | 操作頻率 |
|------|------|---------|------|---------|
| Iron Condor | SPY | ~$35,000 | 20 張 | 每月 1 次 |
| Wheel CSP → CC | NVDA | ~$237,000 | 15 張 | 每月 1-2 次 |
| Bull Call Spread | QQQ | ~$30,000 | 10 張 | 每 2 個月 1 次 |
| Hedge Put | SPY | ~$15,000 | 5 張 | 每季 1 次 |
| 現金保留 | — | ~$683,000 | — | 保留彈藥 |

---

## ✅ Phase 0｜今晚：系統環境建立

### Telegram Bot 設定
- [X] 在 Telegram 搜尋 `@BotFather`，輸入 `/newbot` 建立 Bot
- [X] 記錄 `BOT_TOKEN`（格式：`123456789:ABCdef...`）
- [X] 對自己的 Bot 發一則任意訊息
- [X] 開啟 `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`，找到 `chat.id` 並記錄

### Google Sheet 建立
- [ ] 新建 Google 試算表，命名為 `期權監控系統`
- [ ] 建立工作表一：`Positions`，第一行填入以下欄位名稱（順序不能錯）：
  ```
  ID, STRATEGY, SYMBOL, STATUS, OPEN_DATE, EXPIRY, DTE,
  CONTRACTS, STRIKE_SELL, STRIKE_BUY, PREMIUM_RECEIVED,
  PREMIUM_CURRENT, PNL_USD, PNL_PCT, PROFIT_TARGET_PCT,
  LOSS_LIMIT_PCT, STOCK_PRICE, DISTANCE_PCT, NOTES, LAST_UPDATED
  ```
- [ ] 建立工作表二：`Settings`，填入以下內容：
  ```
  KEY               VALUE
  INITIAL_CAPITAL   1000000
  COMPETITION_START 2026-03-17
  COMPETITION_END   2026-09-15
  ```
- [ ] 建立工作表三：`Log`，第一行填入：
  ```
  TIMESTAMP, TYPE, SYMBOL, STRATEGY, MESSAGE
  ```
- [ ] 從網址列複製試算表 ID（URL 中間那段）並記錄

### Google Cloud Service Account
- [ ] 前往 [Google Cloud Console](https://console.cloud.google.com)，建立新專案
- [ ] 啟用 `Google Sheets API`
- [ ] 啟用 `Google Drive API`
- [ ] 建立 Service Account：IAM & Admin → Service Accounts → Create
  - 角色選 `Editor`
- [ ] 下載 JSON 金鑰：Actions → Manage keys → Add key → JSON
- [ ] 將 Service Account 的 email 加入試算表共用（編輯者權限）

### GitHub Repo 建立
- [ ] 建立新的 **Public** GitHub Repo，命名 `options-monitor`
- [ ] 將提供的程式碼上傳（`src/` 資料夾 + `.github/workflows/` + `requirements.txt`）
- [ ] 前往 Settings → Secrets and variables → Actions，新增以下 4 個 Secret：
  ```
  TELEGRAM_BOT_TOKEN       ← Telegram Bot Token
  TELEGRAM_CHAT_ID         ← 你的 Chat ID
  GOOGLE_CREDENTIALS_JSON  ← JSON 金鑰完整內容（含大括號）
  GOOGLE_SHEET_ID          ← 試算表 ID
  ```

### 驗證系統運作
- [ ] 前往 GitHub Actions → `盤中即時監控` → `Run workflow`（手動觸發）
- [ ] 確認執行成功（綠色勾勾）
- [ ] 確認 Telegram 收到啟動訊息
- [ ] 確認 Google Sheet 的 `Log` 工作表有寫入記錄

---

## ✅ Phase 1｜本週（3/16 週一）：第一筆交易

### 前置確認
- [ ] 登入 Moomoo 模擬帳戶
- [ ] 確認期權交易權限等級（需要 Level 3 以上才能賣 Spread）
  - 路徑：帳戶設定 → 期權交易權限
  - 若不夠，申請升級至 Level 3/4

### 第一筆：SPY Iron Condor（週一開盤後）

> 參考價：SPY $662（實際下單用當天開盤後的價格重新計算）

計算公式：
```
Put Short  = 當日 SPY 現價 × 94%
Put Long   = 當日 SPY 現價 × 91%
Call Short = 當日 SPY 現價 × 106%
Call Long  = 當日 SPY 現價 × 109%
到期日     = 2026-04-17（約 32 DTE）
張數       = 20 張
```

下單步驟（Moomoo）：
- [ ] 搜尋 SPY → 期權 → 期權鏈 → 選 4/17 到期
- [ ] 下第一筆：Sell Put Spread（賣 Put Short，買 Put Long），20 張，限價單
- [ ] 下第二筆：Sell Call Spread（賣 Call Short，買 Call Long），20 張，限價單
- [ ] 記錄實際成交的 premium 金額（每股）
- [ ] 填入 Google Sheet `Positions` 工作表（兩筆，IC Put 側和 Call 側分別填，或合併一筆填 NOTES）

### 第二筆：Hedge Put（同日）

> 作為黑天鵝保險，買完不用管

```
買入 5 張 SPY Put
Strike = 當日 SPY 現價 × 85%
到期日 = 2026-06-19（約 96 DTE）
```

- [ ] Moomoo：搜尋 SPY → 期權 → 6/19 到期 → Buy Put
- [ ] 記錄成交 premium，填入 Google Sheet（STRATEGY = HEDGE_PUT）

---

## ✅ Phase 2｜3/20 週五：NVDA GTC 結束後評估

> GTC 大會：3/16 - 3/19，Jensen Huang Keynote 預計 3/17 晚上

### GTC 後決策框架
- [ ] 查看 NVDA 3/20 開盤價
- [ ] 判斷情境：
  - **大漲（+8% 以上）**：等 3-5 天回落穩定後再開 CSP
  - **下跌（-5% 以上）**：IV Crush，premium 降低，但 Strike 也降低，可以開
  - **平盤（±3%）**：正常按計畫開 CSP

### NVDA CSP 開倉（GTC 後）

計算公式：
```
Strike = GTC 後 NVDA 現價 × 88%
到期日 = 開倉日後第 21-30 天（找週五到期）
張數   = 15 張
```

- [ ] 確認 NVDA 現價，計算 Strike
- [ ] Moomoo：搜尋 NVDA → 期權 → 選到期日 → Sell Put，15 張，限價單
- [ ] 記錄實際成交 premium，填入 Google Sheet（STRATEGY = WHEEL_CSP）

---

## ✅ Phase 3｜每月例行操作

### 每月第一個交易日（週一）
- [ ] 查看 Telegram 有無未處理的 ACTION 通知
- [ ] 若上月 IC 已獲利 50% 或到期 → 開新一輪 SPY Iron Condor
- [ ] 若 NVDA CSP 到期/獲利平倉 → 開新一輪 CSP（或轉 CC）
- [ ] 更新 Google Sheet 中已平倉部位的 STATUS 為 CLOSED

### 每兩個月（首次約 5 月中）
- [ ] 評估是否開 QQQ Bull Call Spread（方向性押注）
  ```
  買 10 張 QQQ Call（ATM 附近）
  賣 10 張 QQQ Call（+10% Strike）
  到期日 45-60 DTE
  PREMIUM_RECEIVED 填負數（付出的成本）
  ```

### NVDA 被 Assign 時（必讀）
- [ ] 確認股票已入帳（100 股 × 15 張 = 1500 股）
- [ ] 將原 CSP 那筆 STATUS 改為 `ASSIGNED`
- [ ] 立刻新增一筆 WHEEL_CC：
  ```
  Strike = 買入成本（被 Assign 的 Strike） × 105%
  到期日 = 14-21 DTE
  張數   = 同等股票數量（15 張）
  ```

---

## ✅ Phase 4｜競賽最後 6 週（8 月初開始）

> 這個階段是競賽決勝期，策略需要調整

- [ ] 8 月初評估目前排名（向同事打聽）
- [ ] 若落後明顯：考慮增加 QQQ Bull Call Spread 張數（進攻）
- [ ] 若領先：縮小部位，確保不大虧就好（守成）
- [ ] 9/1 後所有到期日 > 9/15 的期權考慮提前平倉，避免比賽結束時 OTM 歸零

---

## 📋 機械化操作 SOP 速查

### 收到 Telegram 通知後的處理

| 通知類型 | 處理方式 |
|---------|---------|
| 🎯 獲利達標 (50%) | 馬上登入 Moomoo，買回平倉，開下一輪 |
| 🛑 停損觸發 | 馬上登入 Moomoo，市價買回平倉，這個月不再開新倉 |
| ⏰ DTE ≤ 7 天 | 若有獲利就平倉；若 OTM 快到期可以等自然歸零 |
| ⚠️ Assignment 風險 | 確認現金充足，或考慮 Roll（展期） |
| 📊 每日收盤總結 | 看一眼確認無異常，不用操作 |

### 展期（Roll）操作說明

當期權快到期但想繼續持有部位時：
```
1. 買回當前合約（平倉）
2. 賣出新合約（相同或調整的 Strike，更遠的到期日）
3. Google Sheet：舊的 STATUS 改 CLOSED，新增一筆新合約
```

---

## 🔑 重要參數記錄（請自行填入）

```
Telegram Bot Token    : ______________________________
Telegram Chat ID      : ______________________________
Google Sheet ID       : ______________________________
GitHub Repo URL       : ______________________________

首次 SPY IC 開倉日    : 2026-03-16
首次 NVDA CSP 開倉日  : GTC 後（預計 2026-03-20）
Hedge Put 到期日      : 2026-06-19
```

---

*最後更新：2026-03-15*
