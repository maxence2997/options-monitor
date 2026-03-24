# 🤖 期權模擬競賽監控系統

自動監控 SPY Iron Condor + NVDA Wheel + QQQ Bull Call Spread 策略，
透過 Telegram Bot 管理持倉，每 30 分鐘自動發送監控通知。

---

## 架構總覽

```
你傳指令給 Telegram Bot（/add /list /close /assign）
        ↓
Railway Bot Server（Go + Gin，24hr 在線）
        ↓ 讀寫
GitHub Gist（positions.json，輕量資料庫）
        ↑ 讀取
GitHub Actions cron（每 30 分鐘 / 每日收盤）
        ↓
yfinance 抓價格 → 判斷策略規則 → Telegram 通知
```

### Telegram Chat 分離設計

| 環境變數 | 用途 |
|---------|------|
| `TELEGRAM_CHAT_ID` | Bot 指令回覆對象（你跟 Bot 的私聊） |
| `TELEGRAM_NOTIFY_CHAT_ID` | cron 定時通知目標（群組或另一個 chat） |

若未設定 `TELEGRAM_NOTIFY_CHAT_ID`，所有通知都會發到 `TELEGRAM_CHAT_ID`（向下相容）。

---

## 一、前置準備

### 1. 建立 GitHub Gist（當資料庫）

1. 前往 [gist.github.com](https://gist.github.com)
2. 建立一個新的 **Secret Gist**
   - Filename：`positions.json`
   - Content：貼上以下初始內容
     ```json
     {
       "positions": [],
       "next_id": 1,
       "last_update": ""
     }
     ```
3. 從 Gist URL 取得 **GIST_ID**
   - URL 格式：`https://gist.github.com/你的帳號/`**`abc123def456`**
   - 最後那段就是 GIST_ID

### 2. 建立 GitHub Personal Access Token

1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token，勾選 **`gist`** 權限
3. 複製 token 存好（只會顯示一次），這就是 **GIST_TOKEN**

### 3. 建立 Telegram Bot

1. 在 Telegram 搜尋 `@BotFather`，傳送 `/newbot`
2. 依指示建立 bot，取得 **TELEGRAM_BOT_TOKEN**
3. 對你的 bot 傳一則任意訊息
4. 開啟以下網址，在 JSON 中找 `result[0].message.chat.id`，這就是 **TELEGRAM_CHAT_ID**
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```

### 4. 取得通知頻道的 Chat ID（選用）

若想把定時通知和 Bot 指令分開：
- 建立一個 Telegram 群組或頻道
- 將 Bot 加入該群組/頻道
- 用同樣的 getUpdates 方式取得群組的 **TELEGRAM_NOTIFY_CHAT_ID**
- 群組的 chat_id 通常是負數（例：`-1001234567890`）

---

## 二、GitHub Actions 設定

前往 GitHub repo → **Settings → Secrets and variables → Actions**，新增以下 Secret：

| Secret 名稱 | 說明 | 必填 |
|------------|------|------|
| `TELEGRAM_BOT_TOKEN` | Telegram Bot Token | ✅ |
| `TELEGRAM_CHAT_ID` | Bot 指令 chat ID | ✅ |
| `TELEGRAM_NOTIFY_CHAT_ID` | 通知專用 chat ID | ⬜ 選填 |
| `GIST_ID` | GitHub Gist ID | ✅ |
| `GIST_TOKEN` | GitHub Personal Access Token（gist 權限） | ✅ |

確保 Actions 頁籤已啟用：Settings → Actions → Allow all actions

---

## 三、Railway Bot Server 部署

1. 前往 [railway.app](https://railway.app)，用 GitHub 登入
2. New Project → Deploy from GitHub repo → 選此 repo
3. Builder 選 **Dockerfile**
4. Dockerfile Path 設為 `/bot/Dockerfile`
5. Root Directory 設為 `bot`
6. Watch Paths 設為 `/bot/**`
7. 新增以下環境變數：

| 變數名稱 | 說明 |
|---------|------|
| `TELEGRAM_BOT_TOKEN` | 同上 |
| `TELEGRAM_CHAT_ID` | 同上 |
| `GIST_ID` | 同上 |
| `GIST_TOKEN` | 同上 |
| `GITHUB_TOKEN` | PAT（需要 workflow 權限，供 /trigger 指令使用） |
| `GITHUB_REPO` | `maxence2997/options-monitor` |

8. 部署完成後，取得公開 URL（建議綁定自己的 domain）

### 向 Telegram 註冊 Webhook

```
https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://<YOUR_DOMAIN>/webhook/<TELEGRAM_BOT_TOKEN>
```

成功會回傳：`{"ok":true,"result":true,"description":"Webhook was set"}`

---

## 四、Telegram Bot 指令說明

| 指令 | 說明 |
|------|------|
| `/help` | 顯示完整指令說明與範例 |
| `/example <策略>` | 取得該策略的 JSON 填寫模板 |
| `/add {json}` | 新增持倉（貼上修改後的 JSON） |
| `/list` | 列出所有 OPEN 持倉 |
| `/close <id>` | 將持倉標記為 CLOSED |
| `/assign <id>` | 標記被 Assign，自動提示開 CC |
| `/pnl` | 查看持倉損益快照 |
| `/trigger daily` | 手動觸發每日收盤總結 |
| `/trigger intraday` | 手動觸發盤中監控 |

### 支援的策略名稱（用於 /example）

| 輸入 | 策略 |
|------|------|
| `wheel_csp` | NVDA 賣 Put（Wheel 第一步） |
| `wheel_cc` | NVDA 賣 Call（Assign 後） |
| `iron_condor` | SPY Iron Condor |
| `bull_call` | QQQ Bull Call Spread |
| `hedge` | SPY OTM Put 黑天鵝對沖 |

### 新增持倉流程

```
1. 傳 /example iron_condor
2. Bot 回傳 JSON 模板（含 /add 前綴）
3. 複製整段，修改數字（strike、expiry、premium 等）
4. 直接貼回 Telegram 傳送
5. Bot 確認新增成功，下次 cron 開始監控
```

---

## 五、自動通知說明

| 通知類型 | 觸發條件 | 頻率 | 發送目標 |
|---------|---------|------|---------|
| 📊 每日收盤總結 | 每交易日 20:15 UTC（台灣 04:15，夏令） | 每天 | 通知頻道 |
| 🎯 獲利達標 | P&L ≥ 設定目標 % | 盤中每 30 分鐘 | 通知頻道 |
| 🛑 停損警告 | 虧損 ≥ 停損門檻 % | 盤中每 30 分鐘 | 通知頻道 |
| ⏰ 快到期提醒 | DTE ≤ 7 天 | 盤中每 30 分鐘 | 通知頻道 |
| ⚠️ Assignment 風險 | 股價距 Strike ≤ 5% | 盤中每 30 分鐘 | 通知頻道 |
| ⚠️ IC 翼突破 | 股價突破 Short Strike | 盤中每 30 分鐘 | 通知頻道 |

盤中監控時段：13:00–21:00 UTC（涵蓋夏令/冬令兩個時段）

---

## 六、策略 SOP 快速參考

### Wheel（NVDA）

```
開倉 CSP：
  Strike = 現價 × 88%，DTE = 21-30 天，15 張

收到「獲利 50%」通知 → Moomoo 買回平倉 → /close <id> → 開下一輪

到期未被 Assign → 重複開 CSP

被 Assign → Moomoo 接股票 → /assign <id>
         → Bot 自動提示 CC 參數
         → 開 CC（Strike = 成本 × 105%，DTE = 14-21 天）
         → /add 登記新的 CC 持倉
```

### Iron Condor（SPY）

```
每月第一個交易日開倉（30-45 DTE）：
  Put Short  = 現價 × 94%
  Put Long   = 現價 × 91%
  Call Short = 現價 × 106%（short_call_strike）
  Call Long  = 現價 × 109%（long_call_strike）
  20 張

收到「獲利 50%」→ 整組平倉，等下月
收到「停損 200%」→ 整組平倉
DTE ≤ 7 天且有獲利 → 平倉，不冒 Gamma 風險
```

### Bull Call Spread（QQQ）

```
每 2 個月開倉（45-60 DTE），10 張：
  買 ATM Call（strike_sell）
  賣 +10% Call（strike_buy）
  premium_received 填負數（付出的成本）

獲利 100% → 平倉
虧損 100% → 平倉（最大虧損 = premium 本金）
```

---

## 七、競賽資訊

| 項目 | 內容 |
|------|------|
| 比賽期間 | 2026/03/17 - **2026/09/17** |
| 初始資金 | $1,000,000 |
| 平台 | Moomoo 富途（模擬盤） |
| GitHub Repo | https://github.com/maxence2997/options-monitor |
| Strategy 文件 | [STRATEGY.md](./STRATEGY.md) |

### 時間切換提醒

| 時段 | 美股交易時間（UTC） | 收盤總結 cron |
|------|-------------------|--------------|
| 夏令（3月第二週日 ~ 11月第一週日） | 13:30–20:00 | `15 20 * * 1-5` |
| 冬令（11月第一週日 ~ 3月第二週日） | 14:30–21:00 | `15 21 * * 1-5` |

> ⚠️ 2026/11/01 後需手動更新 `.github/workflows/` 中的 cron 時間（各 +1 小時）

---

## 八、本地測試

```bash
# Python 監控腳本
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="xxx"
export TELEGRAM_CHAT_ID="xxx"
export TELEGRAM_NOTIFY_CHAT_ID="xxx"
export GIST_ID="xxx"
export GIST_TOKEN="xxx"

python src/monitor.py --mode intraday  # 盤中測試
python src/monitor.py --mode daily     # 收盤總結測試

# Go Bot Server
cd bot
go mod tidy
go run ./cmd/main.go
```

---

## 九、費用估算

| 服務 | 費用 |
|------|------|
| GitHub Actions | 免費（public repo） |
| GitHub Gist | 免費 |
| yfinance | 免費 |
| Telegram Bot | 免費 |
| Railway | 免費額度內（約 $0） |
| **總計** | **$0 / 月** |
