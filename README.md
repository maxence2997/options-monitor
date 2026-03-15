# 🤖 期權模擬競賽監控系統

自動監控 SPY/QQQ Iron Condor + NVDA Wheel 策略，每天發 Telegram 通知。

---

## 架構總覽

```
Google Sheet（你填持倉）
       ↓
GitHub Actions（cron 定時觸發）
       ↓
Python 腳本（yfinance 抓價格 + 判斷策略規則）
       ↓
Telegram Bot（通知你該做什麼）
       ↓
Google Sheet（自動回填即時數據）
```

---

## 一、Google Sheet 設定

### 1. 建立試算表，新增三個工作表

#### 工作表一：`Positions`（主要操作頁面）

| 欄位              | 說明                   | 範例                                                              |
| ----------------- | ---------------------- | ----------------------------------------------------------------- |
| ID                | 自訂流水號             | 1, 2, 3...                                                        |
| STRATEGY          | 策略類型               | WHEEL_CSP / WHEEL_CC / IRON_CONDOR / BULL_CALL_SPREAD / HEDGE_PUT |
| SYMBOL            | 標的                   | SPY / QQQ / NVDA                                                  |
| STATUS            | 狀態                   | OPEN（你填）/ CLOSED / ASSIGNED（系統會更新）                     |
| OPEN_DATE         | 開倉日期               | 2025-03-17                                                        |
| EXPIRY            | 到期日                 | 2025-04-18                                                        |
| DTE               | 剩餘天數               | ← 系統自動填                                                      |
| CONTRACTS         | 張數                   | 1                                                                 |
| STRIKE_SELL       | 賣出 Strike            | 480（CSP/CC 的 short strike；IC 填 Put Short）                    |
| STRIKE_BUY        | 買入 Strike            | 460（Spread 的保護腳；單腳策略留空）                              |
| PREMIUM_RECEIVED  | 收到的 premium（每股） | 3.50（CSP/CC/IC 為正；買方策略填負數 -2.00）                      |
| PREMIUM_CURRENT   | 現值                   | ← 系統自動填                                                      |
| PNL_USD           | P&L 金額               | ← 系統自動填                                                      |
| PNL_PCT           | P&L %                  | ← 系統自動填                                                      |
| PROFIT_TARGET_PCT | 獲利目標 %             | 50（預設值，可自訂）                                              |
| LOSS_LIMIT_PCT    | 停損 %                 | 200（預設；NVDA CSP 建議填 300）                                  |
| STOCK_PRICE       | 標的現價               | ← 系統自動填                                                      |
| DISTANCE_PCT      | 距 Strike 距離 %       | ← 系統自動填                                                      |
| NOTES             | 備注                   | IC 請加上 call_short=520（Call Short Strike）                     |
| LAST_UPDATED      | 最後更新               | ← 系統自動填                                                      |

> ⚠️ **Iron Condor 特別說明**：  
> STRIKE_SELL = Put Short，STRIKE_BUY = Put Long  
> Call 側的兩個 Strike 填在 NOTES，格式：`call_short=520 | call_buy=535`

---

#### 工作表二：`Settings`

兩欄：KEY、VALUE

| KEY               | VALUE      | 說明       |
| ----------------- | ---------- | ---------- |
| INITIAL_CAPITAL   | 1000000    | 初始資金   |
| COMPETITION_START | 2025-03-17 | 比賽開始日 |
| COMPETITION_END   | 2025-09-15 | 比賽結束日 |

---

#### 工作表三：`Log`（系統自動寫入，你只需觀看）

欄位：TIMESTAMP、TYPE、SYMBOL、STRATEGY、MESSAGE

---

### 2. 開放 Google Sheet API 存取

1. 前往 [Google Cloud Console](https://console.cloud.google.com)
2. 建立新專案（或使用現有）
3. 啟用 **Google Sheets API** 和 **Google Drive API**
4. 建立服務帳戶（Service Account）
   - IAM & Admin → Service Accounts → Create
   - 角色選 Editor
5. 下載 JSON 金鑰（Actions → Manage keys → Add key → JSON）
6. 將服務帳戶 email 加入試算表的共用對象（編輯者權限）

---

## 二、Telegram Bot 設定

1. 在 Telegram 搜尋 `@BotFather`
2. 傳送 `/newbot`，依指示建立 bot，取得 **BOT_TOKEN**
3. 對你的 bot 傳一則訊息
4. 開啟 `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
5. 找到 `chat.id`，這就是你的 **CHAT_ID**

---

## 三、GitHub 設定

### 1. Fork/Clone 此 repo

```bash
git clone https://github.com/你的帳號/options-monitor.git
cd options-monitor
```

### 2. 設定 Secrets

前往 GitHub repo → Settings → Secrets and variables → Actions → New repository secret

| Secret 名稱               | 值                                    |
| ------------------------- | ------------------------------------- |
| `TELEGRAM_BOT_TOKEN`      | 你的 Telegram Bot Token               |
| `TELEGRAM_CHAT_ID`        | 你的 Telegram Chat ID                 |
| `GOOGLE_CREDENTIALS_JSON` | 服務帳戶 JSON 金鑰（完整內容，含 {}） |
| `GOOGLE_SHEET_ID`         | 試算表 URL 中間的那串 ID              |

> 📌 Google Sheet ID 範例：  
> URL: `https://docs.google.com/spreadsheets/d/`**`1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms`**`/edit`  
> ID 就是中間粗體那段

### 3. 啟用 GitHub Actions

確保 repo 的 Actions 頁籤是啟用狀態（Settings → Actions → Allow all actions）

---

## 四、通知時機說明

| 通知類型           | 觸發條件                     | 頻率       |
| ------------------ | ---------------------------- | ---------- |
| 📊 每日收盤總結    | 每個交易日收盤後 4:15 PM EST | 每天       |
| ⏰ 快到期提醒      | DTE ≤ 7 天                   | 盤中監控時 |
| 🎯 獲利達標        | P&L ≥ 設定目標%              | 盤中監控時 |
| 🛑 停損警告        | 虧損 ≥ 停損門檻%             | 盤中監控時 |
| ⚠️ Assignment 風險 | 股價距 Strike ≤ 5%           | 盤中監控時 |
| ⚠️ IC 翼突破       | 股價突破 Short Strike        | 盤中監控時 |

---

## 五、策略 SOP 快速參考

### Wheel（NVDA）

```
1. 開倉 CSP：
   - Strike = 現價 × 88%
   - DTE = 21-30 天
   - 最多 2 張
   - 填入 Sheet（STATUS=OPEN, STRATEGY=WHEEL_CSP）

2. 收到通知「獲利 50%」→ 買回平倉，立刻開下一輪

3. 到期未被 Assign → 下一輪 CSP

4. 被 Assign（股票入帳）→ 改開 CC：
   - Status 改 ASSIGNED，新增一筆 WHEEL_CC
   - Strike = 成本價 × 105%，DTE = 14-21 天
```

### Iron Condor（SPY）

```
1. 每月第一個交易日開倉：
   - Put Short = 現價 × 94%
   - Put Long  = 現價 × 91%
   - Call Short = 現價 × 106%
   - Call Long  = 現價 × 109%
   - DTE = 30-45 天
   - NOTES 填入 call_short=XXX

2. 收到通知「獲利 50%」→ 整組平倉，等下月

3. 收到通知「停損」→ 整組平倉

4. DTE ≤ 7 天且有獲利 → 平倉，不冒 Gamma 風險
```

### Bull Call Spread（QQQ，方向性押注）

```
1. 每 2 個月開倉一次：
   - 買 ATM Call（STRIKE_SELL）
   - 賣 OTM +10% Call（STRIKE_BUY）
   - PREMIUM_RECEIVED 填負數（你付出的錢，例 -3.50）
   - DTE = 45-60 天

2. 收到通知「獲利 100%」→ 平倉
3. 收到通知「停損 100%」→ 平倉（最多虧 premium）
```

---

## 六、本地測試

```bash
# 安裝依賴
pip install -r requirements.txt

# 設定環境變數（或建立 .env 檔）
export TELEGRAM_BOT_TOKEN="xxx"
export TELEGRAM_CHAT_ID="xxx"
export GOOGLE_CREDENTIALS_JSON='{"type": "service_account", ...}'
export GOOGLE_SHEET_ID="xxx"

# 執行盤中監控（測試用）
python src/monitor.py --mode intraday

# 執行每日總結
python src/monitor.py --mode daily
```

---

## 七、費用估算

| 服務              | 費用                       |
| ----------------- | -------------------------- |
| GitHub Actions    | 免費（public repo 無上限） |
| Google Sheets API | 免費                       |
| yfinance          | 免費                       |
| Telegram Bot      | 免費                       |
| **總計**          | **$0 / 月**                |
# options-monitor
