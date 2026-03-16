package handlers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"

	"options-monitor/bot/model"
	"options-monitor/bot/store"
)

type CommandHandler struct {
	store *store.GistStore
}

func NewCommandHandler(s *store.GistStore) *CommandHandler {
	return &CommandHandler{store: s}
}

// Dispatch 分發指令
func (h *CommandHandler) Dispatch(text string) string {
	text = strings.TrimSpace(text)

	switch {
	case text == "/help":
		return h.handleHelp()
	case strings.HasPrefix(text, "/example"):
		return h.handleExample(text)
	case strings.HasPrefix(text, "/add"):
		return h.handleAdd(text)
	case text == "/list":
		return h.handleList()
	case strings.HasPrefix(text, "/close"):
		return h.handleClose(text)
	case strings.HasPrefix(text, "/assign"):
		return h.handleAssign(text)
	case text == "/pnl":
		return h.handlePnl()
	case strings.HasPrefix(text, "/trigger"):
		return h.handleTrigger(text)
	default:
		return "❓ 未知指令，輸入 /help 查看所有可用指令"
	}
}

// ── /help ────────────────────────────────────────────────────────────────────

func (h *CommandHandler) handleHelp() string {
	return `📖 <b>期權監控系統 — 指令說明</b>

━━━━━━━━━━━━━━━━━━━━
<b>📋 持倉管理</b>

<b>/add {json}</b>
新增一筆持倉。先用 /example 取得模板，修改後貼上。
範例：<code>/add {"strategy":"WHEEL_CSP",...}</code>

<b>/list</b>
列出所有 OPEN 狀態的持倉及其基本資訊。

<b>/close &lt;id&gt;</b>
將指定持倉標記為 CLOSED（已平倉）。
範例：<code>/close 3</code>

<b>/assign &lt;id&gt;</b>
將 CSP 持倉標記為 ASSIGNED（被 Assign 接股票）。
系統會自動提示你下一步開 Covered Call。
範例：<code>/assign 2</code>

<b>/pnl</b>
顯示目前各持倉的損益快照（下次 cron 執行後更新）。

━━━━━━━━━━━━━━━━━━━━
<b>📝 模板取得</b>

<b>/example &lt;策略&gt;</b>
取得該策略的 JSON 填寫模板，複製後修改數字即可。

支援的策略名稱：
  <code>wheel_csp</code>     → NVDA 賣 Put（Wheel 第一步）
  <code>wheel_cc</code>      → NVDA 賣 Call（Assign 後）
  <code>iron_condor</code>   → SPY Iron Condor
  <code>bull_call</code>     → QQQ Bull Call Spread
  <code>hedge</code>         → SPY OTM Put 對沖

範例：<code>/example iron_condor</code>

━━━━━━━━━━━━━━━━━━━━
<b>🚀 手動觸發監控</b>

<b>/trigger daily</b>
立即執行每日收盤總結，發送到通知頻道。

<b>/trigger intraday</b>
立即執行盤中監控，有異常才會發通知。

━━━━━━━━━━━━━━━━━━━━
<b>⚙️ 自動監控時間</b>（夏令 UTC）

  📊 收盤結算：每日 20:15 UTC（台灣 04:15）
  📡 開盤後 1h：每日 14:30 UTC（台灣 22:30）
  📡 收盤前 1h：每日 19:00 UTC（台灣 03:00）

觸發條件：
  🎯 獲利達到目標 % → 建議平倉
  🛑 虧損超過門檻 % → 停損警告
  ⏰ DTE ≤ 7 天 → 到期提醒
  ⚠️ 股價逼近 Strike → Assignment 風險`
}

// ── /trigger ──────────────────────────────────────────────────────────────────

func (h *CommandHandler) handleTrigger(text string) string {
	parts := strings.Fields(text)
	if len(parts) < 2 {
		return "❓ 請指定模式，例如：\n<code>/trigger daily</code>\n<code>/trigger intraday</code>"
	}

	mode := strings.ToLower(parts[1])
	var workflowFile string
	var modeName string

	switch mode {
	case "daily":
		workflowFile = "daily_summary.yml"
		modeName     = "每日收盤總結"
	case "intraday":
		workflowFile = "intraday_monitor.yml"
		modeName     = "盤中監控"
	default:
		return "❓ 未知模式，可用：<code>daily</code>、<code>intraday</code>"
	}

	token := os.Getenv("GITHUB_TOKEN")
	repo  := os.Getenv("GITHUB_REPO")

	if token == "" || repo == "" {
		return "⚠️ 未設定 GITHUB_TOKEN 或 GITHUB_REPO 環境變數，無法觸發 workflow"
	}

	url  := fmt.Sprintf("https://api.github.com/repos/%s/actions/workflows/%s/dispatches", repo, workflowFile)
	body := []byte(`{"ref":"main"}`)

	req, err := http.NewRequest("POST", url, bytes.NewReader(body))
	if err != nil {
		return fmt.Sprintf("❌ 建立請求失敗：%v", err)
	}
	req.Header.Set("Authorization", "Bearer "+token)
	req.Header.Set("Accept", "application/vnd.github+json")
	req.Header.Set("Content-Type", "application/json")

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Sprintf("❌ 觸發失敗：%v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == 204 {
		return fmt.Sprintf(
			"✅ <b>已觸發 %s</b>\n\n"+
				"⏱ GitHub Actions 約 30-60 秒後執行\n"+
				"通知結果會發到通知頻道",
			modeName,
		)
	}

	b, _ := io.ReadAll(resp.Body)
	return fmt.Sprintf("❌ 觸發失敗（HTTP %d）：%s", resp.StatusCode, string(b))
}

// ── /example ─────────────────────────────────────────────────────────────────

func (h *CommandHandler) handleExample(text string) string {
	parts := strings.Fields(text)
	if len(parts) < 2 {
		return "❓ 請指定策略，例如：<code>/example iron_condor</code>\n\n可用：wheel_csp, wheel_cc, iron_condor, bull_call, hedge"
	}

	strategy := strings.ToLower(parts[1])
	today    := time.Now()
	expiry   := nextFriday(today.AddDate(0, 0, 30))

	var template interface{}
	var note string

	switch strategy {
	case "wheel_csp":
		template = map[string]interface{}{
			"strategy":          "WHEEL_CSP",
			"symbol":            "NVDA",
			"expiry":            expiry,
			"contracts":         15,
			"strike_sell":       158.00,
			"premium_received":  3.50,
			"profit_target_pct": 50,
			"loss_limit_pct":    300,
			"notes":             "",
		}
		note = "💡 <b>NVDA CSP 填寫提示</b>\n" +
			"• strike_sell = 現價 × 88%（例：現價 $180 → strike $158）\n" +
			"• premium_received = 實際成交的每股 premium\n" +
			"• expiry = 找 21-30 天後的週五到期日"

	case "wheel_cc":
		template = map[string]interface{}{
			"strategy":          "WHEEL_CC",
			"symbol":            "NVDA",
			"expiry":            expiry,
			"contracts":         15,
			"strike_sell":       195.00,
			"premium_received":  2.80,
			"profit_target_pct": 50,
			"loss_limit_pct":    200,
			"notes":             "assigned_cost=158.00",
		}
		note = "💡 <b>NVDA CC 填寫提示</b>\n" +
			"• strike_sell = 被 Assign 成本價 × 105%\n" +
			"• notes 填入 assigned_cost=你的成本價，方便追蹤"

	case "iron_condor":
		template = map[string]interface{}{
			"strategy":          "IRON_CONDOR",
			"symbol":            "SPY",
			"expiry":            nextFriday(today.AddDate(0, 0, 35)),
			"contracts":         20,
			"strike_sell":       622.00,
			"strike_buy":        602.00,
			"premium_received":  2.50,
			"profit_target_pct": 50,
			"loss_limit_pct":    200,
			"notes":             "call_short=702 | call_buy=722",
		}
		note = "💡 <b>SPY Iron Condor 填寫提示</b>\n" +
			"• strike_sell = Put Short（現價 × 94%）\n" +
			"• strike_buy  = Put Long（現價 × 91%）\n" +
			"• notes 必填 call_short 和 call_buy，系統監控用\n" +
			"• Call Short = 現價 × 106%，Call Long = 現價 × 109%"

	case "bull_call":
		template = map[string]interface{}{
			"strategy":          "BULL_CALL_SPREAD",
			"symbol":            "QQQ",
			"expiry":            nextFriday(today.AddDate(0, 0, 50)),
			"contracts":         10,
			"strike_sell":       595.00,
			"strike_buy":        655.00,
			"premium_received":  -3.20,
			"profit_target_pct": 100,
			"loss_limit_pct":    100,
			"notes":             "",
		}
		note = "💡 <b>QQQ Bull Call Spread 填寫提示</b>\n" +
			"• strike_sell = 買入的 Call（ATM 附近）\n" +
			"• strike_buy  = 賣出的 Call（+10% Strike）\n" +
			"• premium_received = <b>負數</b>（付出的成本，例 -3.20）\n" +
			"• 最大虧損 = premium 本金，最大獲利 = spread 寬度 - 成本"

	case "hedge":
		template = map[string]interface{}{
			"strategy":          "HEDGE_PUT",
			"symbol":            "SPY",
			"expiry":            nextFriday(today.AddDate(0, 3, 0)),
			"contracts":         5,
			"strike_sell":       563.00,
			"premium_received":  -1.80,
			"profit_target_pct": 200,
			"loss_limit_pct":    100,
			"notes":             "black_swan_hedge",
		}
		note = "💡 <b>SPY Hedge Put 填寫提示</b>\n" +
			"• strike_sell = 現價 × 85%（深度 OTM）\n" +
			"• premium_received = <b>負數</b>（付出的保費）\n" +
			"• 這筆買了就不用管，當保險費看待"

	default:
		return "❓ 未知策略，可用：<code>wheel_csp</code>, <code>wheel_cc</code>, <code>iron_condor</code>, <code>bull_call</code>, <code>hedge</code>"
	}

	jsonBytes, _ := json.MarshalIndent(template, "", "  ")
	return fmt.Sprintf("%s\n\n<b>複製以下 JSON，修改數字後用 /add 貼上：</b>\n\n<code>/add %s</code>",
		note, string(jsonBytes))
}

// ── /add ──────────────────────────────────────────────────────────────────────

func (h *CommandHandler) handleAdd(text string) string {
	jsonStr := strings.TrimPrefix(text, "/add")
	jsonStr  = strings.TrimSpace(jsonStr)

	if jsonStr == "" {
		return "❓ 請提供 JSON，例如：\n<code>/add {\"strategy\":\"WHEEL_CSP\",...}</code>\n\n先用 /example wheel_csp 取得模板"
	}

	var req model.AddPositionRequest
	if err := json.Unmarshal([]byte(jsonStr), &req); err != nil {
		return fmt.Sprintf("❌ JSON 格式錯誤：%v\n\n請檢查格式，或用 /example 重新取得模板", err)
	}

	if err := validateAddRequest(&req); err != nil {
		return fmt.Sprintf("❌ 驗證失敗：%v", err)
	}

	pos, err := h.store.AddPosition(&req)
	if err != nil {
		return fmt.Sprintf("❌ 儲存失敗：%v", err)
	}

	return fmt.Sprintf(
		"✅ <b>持倉已新增</b>\n\n"+
			"ID：%d\n"+
			"策略：%s\n"+
			"標的：%s\n"+
			"Strike：%.2f%s\n"+
			"到期日：%s\n"+
			"張數：%d\n"+
			"Premium：%.2f\n"+
			"獲利目標：%.0f%% | 停損：%.0f%%\n\n"+
			"📊 系統將在下次 cron 執行時開始監控此持倉",
		pos.ID, pos.Strategy, pos.Symbol,
		pos.StrikeSell, strikeRangeStr(pos),
		pos.Expiry, pos.Contracts, pos.PremiumReceived,
		pos.ProfitTargetPct, pos.LossLimitPct,
	)
}

// ── /list ─────────────────────────────────────────────────────────────────────

func (h *CommandHandler) handleList() string {
	positions, err := h.store.ListOpen()
	if err != nil {
		return fmt.Sprintf("❌ 讀取失敗：%v", err)
	}

	if len(positions) == 0 {
		return "📭 目前沒有 OPEN 持倉\n\n用 /example 取得模板，/add 新增持倉"
	}

	var sb strings.Builder
	sb.WriteString(fmt.Sprintf("📋 <b>目前持倉（共 %d 筆）</b>\n", len(positions)))
	sb.WriteString("━━━━━━━━━━━━━━━━━━━━\n")

	for _, p := range positions {
		daysLeft   := daysUntil(p.Expiry)
		dteWarning := ""
		if daysLeft <= 7 {
			dteWarning = " ⏰"
		}

		fmt.Fprintf(&sb, "<b>[%d] %s %s</b>%s\n"+
			"  Strike: %.0f%s | 到期: %s（%d天）\n"+
			"  %d張 | Premium: %.2f | 目標: %.0f%% 停損: %.0f%%\n",
			p.ID, p.Symbol, p.Strategy, dteWarning,
			p.StrikeSell, strikeRangeStr(&p),
			p.Expiry, daysLeft,
			p.Contracts, p.PremiumReceived,
			p.ProfitTargetPct, p.LossLimitPct)
		if p.Notes != "" {
			sb.WriteString(fmt.Sprintf("  📝 %s\n", p.Notes))
		}
		sb.WriteString("\n")
	}

	sb.WriteString("指令：/close &lt;id&gt; 平倉 | /assign &lt;id&gt; 被 Assign")
	return sb.String()
}

// ── /close ────────────────────────────────────────────────────────────────────

func (h *CommandHandler) handleClose(text string) string {
	id, err := parseID(text, "/close")
	if err != nil {
		return err.Error()
	}

	pos, err := h.store.UpdateStatus(id, model.StatusClosed, "manually closed")
	if err != nil {
		return fmt.Sprintf("❌ %v", err)
	}

	return fmt.Sprintf(
		"✅ <b>持倉已平倉</b>\n\n"+
			"ID：%d | %s %s\n"+
			"Status → CLOSED\n\n"+
			"記得在 Moomoo 執行對應的買回操作 📱",
		pos.ID, pos.Symbol, pos.Strategy,
	)
}

// ── /assign ───────────────────────────────────────────────────────────────────

func (h *CommandHandler) handleAssign(text string) string {
	id, err := parseID(text, "/assign")
	if err != nil {
		return err.Error()
	}

	pos, err := h.store.UpdateStatus(id, model.StatusAssigned, "assigned - stock received")
	if err != nil {
		return fmt.Sprintf("❌ %v", err)
	}

	ccStrike := pos.StrikeSell * 1.05
	return fmt.Sprintf(
		"📌 <b>已標記為 ASSIGNED</b>\n\n"+
			"ID：%d | %s\n"+
			"被 Assign 成本：$%.2f/股\n\n"+
			"━━━━━━━━━━━━━━━━━━━━\n"+
			"<b>👉 下一步：開 Covered Call</b>\n\n"+
			"用 /example wheel_cc 取得模板，建議參數：\n"+
			"• strike_sell = <b>%.2f</b>（成本 × 105%%）\n"+
			"• DTE = 14-21 天後的週五\n"+
			"• contracts = %d（同等張數）\n\n"+
			"開好後記得 /add 登記！",
		pos.ID, pos.Symbol, pos.StrikeSell, ccStrike, pos.Contracts,
	)
}

// ── /pnl ──────────────────────────────────────────────────────────────────────

func (h *CommandHandler) handlePnl() string {
	positions, err := h.store.ListOpen()
	if err != nil {
		return fmt.Sprintf("❌ 讀取失敗：%v", err)
	}

	if len(positions) == 0 {
		return "📭 目前沒有 OPEN 持倉"
	}

	var sb strings.Builder
	sb.WriteString("💰 <b>持倉損益快照</b>\n")
	sb.WriteString("（數值由 cron 定時更新，非即時）\n")
	sb.WriteString("━━━━━━━━━━━━━━━━━━━━\n\n")

	for _, p := range positions {
		maxProfit := p.PremiumReceived * float64(p.Contracts) * 100
		sb.WriteString(fmt.Sprintf(
			"<b>[%d] %s %s</b>\n"+
				"  最大獲利：$%.0f | 到期：%s（%d天剩）\n\n",
			p.ID, p.Symbol, p.Strategy,
			maxProfit, p.Expiry, daysUntil(p.Expiry),
		))
	}

	sb.WriteString("📊 即時 P&L 由每日收盤通知提供")
	return sb.String()
}

// ── helpers ───────────────────────────────────────────────────────────────────

func validateAddRequest(req *model.AddPositionRequest) error {
	if !req.Strategy.IsValid() {
		return fmt.Errorf("strategy 無效：%q，可用值：WHEEL_CSP, WHEEL_CC, IRON_CONDOR, BULL_CALL_SPREAD, HEDGE_PUT", req.Strategy)
	}
	if req.Symbol == "" {
		return fmt.Errorf("symbol 不能為空")
	}
	if req.Expiry == "" {
		return fmt.Errorf("expiry 不能為空（格式：2026-04-17）")
	}
	if _, err := time.Parse("2006-01-02", req.Expiry); err != nil {
		return fmt.Errorf("expiry 格式錯誤，應為 YYYY-MM-DD")
	}
	if req.Contracts <= 0 {
		return fmt.Errorf("contracts 必須大於 0")
	}
	if req.StrikeSell <= 0 {
		return fmt.Errorf("strike_sell 必須大於 0")
	}
	if req.PremiumReceived == 0 {
		return fmt.Errorf("premium_received 不能為 0（買方策略填負數）")
	}
	return nil
}

func parseID(text, cmd string) (int, error) {
	parts := strings.Fields(text)
	if len(parts) < 2 {
		return 0, fmt.Errorf("❓ 請提供 ID，例如：<code>%s 3</code>", cmd)
	}
	var id int
	if _, err := fmt.Sscanf(parts[1], "%d", &id); err != nil {
		return 0, fmt.Errorf("❓ ID 格式錯誤，請輸入數字，例如：<code>%s 3</code>", cmd)
	}
	return id, nil
}

func strikeRangeStr(p *model.Position) string {
	if p.StrikeBuy > 0 {
		return fmt.Sprintf(" / %.0f", p.StrikeBuy)
	}
	return ""
}

func daysUntil(dateStr string) int {
	t, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		return 0
	}
	days := int(time.Until(t).Hours() / 24)
	if days < 0 {
		return 0
	}
	return days
}

func nextFriday(from time.Time) string {
	d := from
	for d.Weekday() != time.Friday {
		d = d.AddDate(0, 0, 1)
	}
	return d.Format("2006-01-02")
}
