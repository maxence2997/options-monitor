# 🎯 美股期權模擬競賽 — 任務清單

> 比賽期間：2026/03/17 - 2026/09/15（約 26 週）
> 初始資金：$1,000,000
> 平台：Moomoo 富途（模擬盤）
> 策略：SPY Iron Condor + NVDA Wheel + QQQ Bull Call Spread + Hedge Put

---

## 📌 策略速查

| 策略             | 標的 | 資金佔用  | 張數  | 操作頻率       |
| ---------------- | ---- | --------- | ----- | -------------- |
| Iron Condor      | SPY  | ~$35,000  | 20 張 | 每月 1 次      |
| Wheel CSP → CC   | NVDA | ~$237,000 | 15 張 | 每月 1-2 次    |
| Bull Call Spread | QQQ  | ~$30,000  | 10 張 | 每 2 個月 1 次 |
| Hedge Put        | SPY  | ~$15,000  | 5 張  | 每季 1 次      |
| 現金保留         | —    | ~$683,000 | —     | 保留彈藥       |

---

## ✅ Phase 0｜今晚：系統環境建立

### Telegram Bot

- [x] 搜尋 `@BotFather`，輸入 `/newbot` 建立 Bot
- [x] 記錄 `TELEGRAM_BOT_TOKEN`
- [x] 對 Bot 發一則訊息，再用瀏覽器開啟以下網址取得 `TELEGRAM_CHAT_ID`：
  ```
  https://api.telegram.org/bot<TOKEN>/getUpdates
  ```
  在回傳的 JSON 中找 `result[0].message.chat.id`，即為你的 Chat ID

### GitHub Gist（資料庫）

- [x] 前往 [gist.github.com](https://gist.github.com)，建立新的 **Secret Gist**
  - Filename：`positions.json`
  - Content：
    ```json
    {
      "positions": [],
      "next_id": 1,
      "last_update": ""
    }
    ```
- [x] 從 URL 複製 **GIST_ID**（URL 最後那段英數字）

### GitHub Personal Access Token

- [x] GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
- [x] Generate new token，勾選 `gist` 權限
- [x] 複製並記錄 **GIST_TOKEN**（只會顯示一次）

### GitHub Secrets 設定

- [x] 前往 repo → Settings → Secrets and variables → Actions
- [x] 新增以下 4 個 Secret：
  ```
  TELEGRAM_BOT_TOKEN  ← Telegram Bot Token
  TELEGRAM_CHAT_ID    ← 你的 Chat ID
  GIST_ID             ← Gist ID
  GIST_TOKEN          ← Personal Access Token
  ```

### requirements.txt 修正

- [x] 移除 `gspread==6.1.2` 和 `google-auth==2.29.0`，並且更新 `yfinance` 和 `pandas` 版本
- [x] 確認最終內容：
  ```
  yfinance==1.2.0
  requests==2.32.3
  pandas==3.0.1
  ```

### Railway Bot Server 部署

- [x] 前往 [railway.app](https://railway.app)，用 GitHub 登入
- [x] New Project → Deploy from GitHub repo → 選 `options-monitor`
- [x] 設定 **Root Directory** 為 `bot`
- [x] 新增環境變數（同 GitHub Secrets 的 4 個）
- [x] 等待部署完成，記錄 Railway 提供的公開 URL

### 向 Telegram 註冊 Webhook

- [x] 在瀏覽器開啟以下網址（替換 `<TOKEN>` 和 `<RAILWAY_URL>`）：
  ```
  https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<RAILWAY_URL>/webhook/<TOKEN>
  ```
- [x] 確認回傳 `{"ok":true,...,"description":"Webhook was set"}`

### 驗證系統運作

- [x] 對 Bot 傳 `/help`，確認收到指令說明
- [x] 傳 `/example iron_condor`，確認收到 JSON 模板
- [x] GitHub Actions → `盤中即時監控` → `Run workflow` 手動觸發
- [x] 確認 Actions 執行成功（綠色勾勾）
- [x] 確認 Telegram 收到監控訊息

---

## ✅ Phase 1｜本週（3/16 週一）：第一筆交易

### 前置確認

- [ ] 登入 Moomoo 模擬帳戶
- [ ] 確認期權交易權限等級（需要 Level 3+ 才能賣 Spread）

### 第一筆：SPY Iron Condor（週一開盤後）

> 參考價：SPY $662（實際下單用當天開盤後價格重新計算）

```
Put Short  = 當日 SPY 現價 × 94%
Put Long   = 當日 SPY 現價 × 91%
Call Short = 當日 SPY 現價 × 106%
Call Long  = 當日 SPY 現價 × 109%
到期日     = 2026-04-17（約 32 DTE）
張數       = 20 張
```

- [ ] Moomoo：SPY → 期權 → 4/17 到期 → Sell Put Spread 20 張
- [ ] Moomoo：SPY → 期權 → 4/17 到期 → Sell Call Spread 20 張
- [ ] 記錄實際成交 premium
- [ ] 傳 `/example iron_condor` → 修改數字 → `/add` 登記

### 第二筆：Hedge Put（同日）

```
買入 5 張 SPY Put
Strike = 當日 SPY 現價 × 85%
到期日 = 2026-06-19
```

- [ ] Moomoo：SPY → 期權 → 6/19 到期 → Buy Put 5 張
- [ ] 傳 `/example hedge` → 修改數字 → `/add` 登記

---

## ✅ Phase 2｜3/20 週五：NVDA GTC 結束後評估

> GTC 大會：3/16 - 3/19，Jensen Huang Keynote 預計 3/17 晚上

- [ ] 查看 NVDA 3/20 開盤價，判斷情境：
  - **大漲（+8%）**：等 3-5 天回落再開 CSP
  - **下跌（-5%）**：IV Crush，直接開 CSP
  - **平盤（±3%）**：正常開 CSP

```
Strike = GTC 後 NVDA 現價 × 88%
到期日 = 開倉日後第 21-30 天的週五
張數   = 15 張
```

- [ ] Moomoo：NVDA → 期權 → 選到期日 → Sell Put 15 張
- [ ] 傳 `/example wheel_csp` → 修改數字 → `/add` 登記

---

## ✅ Phase 3｜每月例行操作

### 每月第一個交易日

- [ ] 查看 Telegram 有無未處理 ACTION 通知
- [ ] 上月 IC 到期/獲利 → 開新一輪 IC，`/add` 登記
- [ ] NVDA CSP 到期/獲利 → 開新一輪 CSP，`/add` 登記
- [ ] 已平倉部位執行 `/close <id>`

### 每兩個月（首次約 5 月中）

- [ ] 評估開 QQQ Bull Call Spread
- [ ] 傳 `/example bull_call` → 開倉後 `/add` 登記

### NVDA 被 Assign 時

- [ ] Moomoo 確認 1500 股已入帳
- [ ] 傳 `/assign <id>` → Bot 自動提示 CC 參數
- [ ] 照提示開 Covered Call（Strike = 成本 × 105%，DTE = 14-21 天）
- [ ] 傳 `/example wheel_cc` → 開倉後 `/add` 登記

---

## ✅ Phase 4｜競賽最後 6 週（8 月初）

- [ ] 打聽同事排名，評估位置
- [ ] 落後 → 增加 QQQ Bull Call Spread 張數（進攻）
- [ ] 領先 → 縮小部位（守成）
- [ ] **9/1 後**：到期日 > 9/15 的期權全部提前平倉

---

## 📋 收到通知的處理 SOP

| 通知               | 處理方式                                         |
| ------------------ | ------------------------------------------------ |
| 🎯 獲利達標        | Moomoo 買回平倉 → `/close <id>` → 開下一輪       |
| 🛑 停損觸發        | Moomoo 市價買回 → `/close <id>` → 這個月不開新倉 |
| ⏰ DTE ≤ 7 天      | 有獲利就平倉；OTM 快到期可讓其歸零               |
| ⚠️ Assignment 風險 | 確認現金充足，或考慮 Roll 展期                   |
| 📊 每日收盤總結    | 看一眼確認無異常，不用操作                       |

---

## 🔑 重要參數記錄

```
Telegram Bot Token    : ______________________________
Telegram Chat ID      : ______________________________
GitHub Gist ID        : ______________________________
Railway URL           : ______________________________
GitHub Repo           : https://github.com/maxence2997/options-monitor

首次 SPY IC 開倉日    : 2026-03-16
首次 NVDA CSP 開倉日  : GTC 後（預計 2026-03-20）
Hedge Put 到期日      : 2026-06-19
```

---

_最後更新：2026-03-15_
