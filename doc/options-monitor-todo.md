# 🎯 美股期權模擬競賽 — 任務清單

> 比賽期間：2026/03/17 - 2026/09/17（約 26 週）
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

## ✅ Phase 0｜系統環境建立（已完成）

- [x] Telegram Bot 建立，取得 TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
- [x] 通知群組建立，Bot 已加入（options-monitor Group）
- [x] GitHub Gist 建立（positions.json），取得 GIST_ID
- [x] GitHub PAT 建立（gist 權限），取得 GIST_TOKEN
- [x] GitHub Secrets 設定完成（BOT_TOKEN / CHAT_ID / GIST_ID / GIST_TOKEN）
- [x] Railway 部署成功（Root Directory=bot）
- [x] Telegram Webhook 設定完成
- [x] `/help` 指令驗證正常
- [x] daily workflow 手動觸發測試成功（收到通知）
- [x] cron 時間修正為 20:15 UTC（收盤後 15 分）

---

## 🔲 Phase 0｜待完成項目

### 立即處理（今天）

- [ ] **推送以下三個更新檔案到 repo**（修正無持倉格式 + 新增 /trigger 功能）：
  ```
  src/monitor.py          ← 無持倉時的 daily 通知改為含日期時間格式
  bot/handlers/commands.go ← 新增 /trigger 指令、更新 /help 說明
  bot/cmd/main.go         ← 新增 GITHUB_TOKEN / GITHUB_REPO 環境變數警告
  ```
  推送後 Railway 會自動重新部署（約 2-3 分鐘）

- [ ] **取得通知群組的 TELEGRAM_NOTIFY_CHAT_ID**
  ```
  步驟：
  1. 先暫時移除 Webhook：
     https://api.telegram.org/bot<TOKEN>/deleteWebhook
  2. 在群組傳一則訊息
  3. 用瀏覽器開啟：
     https://api.telegram.org/bot<TOKEN>/getUpdates
  4. 找 result[].message.chat.id（群組 ID 為負數，例：-1001234567890）
  5. 重新設定 Webhook：
     https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://<URL>/webhook/<TOKEN>
  ```
  > 如果 getUpdates 沒有群組訊息，先確認 Bot 有群組的訊息讀取權限（Bot Settings → Allow Groups）

- [ ] **Railway 新增兩個環境變數**（/trigger 指令需要）：
  ```
  GITHUB_TOKEN  ← 需要 workflow 權限的 PAT（現有的 GIST_TOKEN 只有 gist 權限，需另建）
  GITHUB_REPO   ← maxence2997/options-monitor
  ```
  > 建立新 PAT 時勾選：repo → Actions（workflow 觸發權限）

- [ ] **GitHub Secrets 新增 TELEGRAM_NOTIFY_CHAT_ID**（取得後補上）

---

## ✅ Phase 1｜本週（3/16 週一）：第一筆交易

### 前置確認

- [ ] 登入 Moomoo 模擬帳戶
- [ ] 確認期權交易權限等級（需要 Level 3+ 才能賣 Spread）

### 第一筆：SPY Iron Condor（週一開盤後）

> 計算方式：取當天開盤後 SPY 現價重新計算

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

- [ ] 查看**通知頻道**有無未處理 ACTION 通知
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
- [ ] **9/1 後**：到期日 > 9/17 的期權全部提前平倉

---

## 🚀 Bot 指令速查

| 指令 | 說明 |
|------|------|
| `/help` | 完整指令說明 |
| `/example <策略>` | 取得 JSON 填寫模板 |
| `/add {json}` | 新增持倉 |
| `/list` | 列出所有 OPEN 持倉 |
| `/close <id>` | 標記已平倉 |
| `/assign <id>` | 標記被 Assign，提示開 CC |
| `/pnl` | 損益快照 |
| `/trigger daily` | 手動觸發每日收盤總結 |
| `/trigger intraday` | 手動觸發盤中監控 |

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

## ⚠️ 注意事項

### 冬令時間切換（2026/11/01 後）

需更新兩個 workflow 的 cron 時間（各 +1 小時）：

`.github/workflows/daily_summary.yml`
```
# 改為：
- cron: "15 21 * * 1-5"
```

`.github/workflows/intraday_monitor.yml`
```
# 改為：
- cron: "30 15 * * 1-5"
- cron: "0 20 * * 1-5"
```

---

## 🔑 重要參數記錄

```
Telegram Bot Token        : ______________________________
Telegram Chat ID（指令）  : ______________________________
Telegram Chat ID（通知）  : ______________________________（取得後補上）
GitHub Gist ID            : ______________________________
Railway URL               : options-monitor-bot.maxence2997.cc
GitHub Repo               : https://github.com/maxence2997/options-monitor

首次 SPY IC 開倉日        : 2026-03-16（週一）
首次 NVDA CSP 開倉日      : GTC 後（預計 2026-03-20）
Hedge Put 到期日          : 2026-06-19
```

---

_最後更新：2026-03-16_
