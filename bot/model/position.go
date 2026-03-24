package model

import "time"

type Strategy string

const (
	StrategyWheelCSP       Strategy = "WHEEL_CSP"
	StrategyWheelCC        Strategy = "WHEEL_CC"
	StrategyIronCondor     Strategy = "IRON_CONDOR"
	StrategyBullCallSpread Strategy = "BULL_CALL_SPREAD"
	StrategyHedgePut       Strategy = "HEDGE_PUT"
)

type Status string

const (
	StatusOpen     Status = "OPEN"
	StatusClosed   Status = "CLOSED"
	StatusAssigned Status = "ASSIGNED"
)

// Store 是 Gist 裡 positions.json 的頂層結構
type Store struct {
	Positions  []Position `json:"positions"`
	NextID     int        `json:"next_id"`
	LastUpdate string     `json:"last_update"`
}

// Position 代表一筆持倉記錄
type Position struct {
	ID        int      `json:"id"`
	Strategy  Strategy `json:"strategy"`
	Symbol    string   `json:"symbol"`
	Status    Status   `json:"status"`
	OpenDate  string   `json:"open_date"`
	Expiry    string   `json:"expiry"`
	Contracts int      `json:"contracts"`
	Notes     string   `json:"notes,omitempty"`
	CreatedAt time.Time `json:"created_at"`

	// ── Strike 欄位（統一命名：short/long + put/call + strike）──────────
	// 各策略共用，依 Strategy 決定哪些欄位有值
	ShortPutStrike  float64 `json:"short_put_strike,omitempty"`  // WHEEL_CSP, IC
	LongPutStrike   float64 `json:"long_put_strike,omitempty"`   // HEDGE_PUT, IC
	ShortCallStrike float64 `json:"short_call_strike,omitempty"` // WHEEL_CC, IC, BCS
	LongCallStrike  float64 `json:"long_call_strike,omitempty"`  // IC, BCS

	// ── Premium ──────────────────────────────────────────────────────────
	PremiumReceived  float64 `json:"premium_received,omitempty"`       // 非 IC 策略
	ShortPutPremium  float64 `json:"short_put_premium,omitempty"`      // IC 賣出 Put 收到
	LongPutPremium   float64 `json:"long_put_premium,omitempty"`       // IC 買入 Put 付出
	ShortCallPremium float64 `json:"short_call_premium,omitempty"`     // IC 賣出 Call 收到
	LongCallPremium  float64 `json:"long_call_premium,omitempty"`      // IC 買入 Call 付出

	// ── 共用設定 ──────────────────────────────────────────────────────────
	ProfitTargetPct float64 `json:"profit_target_pct"`
	LossLimitPct    float64 `json:"loss_limit_pct"`
}

// TotalPremium 回傳此持倉的淨 premium（net = 賣出收入 - 買入成本）
// IC：(short_put_premium - long_put_premium) + (short_call_premium - long_call_premium)
// 其他：premium_received
func (p *Position) TotalPremium() float64 {
	if p.Strategy == StrategyIronCondor {
		return (p.ShortPutPremium - p.LongPutPremium) + (p.ShortCallPremium - p.LongCallPremium)
	}
	return p.PremiumReceived
}

// GrossPremium 回傳賣出腳合計（顯示用，不作為 PnL 基準）
func (p *Position) GrossPremium() float64 {
	if p.Strategy == StrategyIronCondor {
		return p.ShortPutPremium + p.ShortCallPremium
	}
	return p.PremiumReceived
}

// MainStrike 回傳單腿策略的主要 Strike（供顯示用）
func (p *Position) MainStrike() float64 {
	switch p.Strategy {
	case StrategyWheelCSP:
		return p.ShortPutStrike
	case StrategyWheelCC:
		return p.ShortCallStrike
	case StrategyHedgePut:
		return p.LongPutStrike
	default:
		return 0
	}
}

// ── AddPositionRequest ────────────────────────────────────────────────────────

// AddPositionRequest 對應 /add 指令傳入的 JSON
type AddPositionRequest struct {
	Strategy  Strategy `json:"strategy"`
	Symbol    string   `json:"symbol"`
	Expiry    string   `json:"expiry"`
	Contracts int      `json:"contracts"`
	Notes     string   `json:"notes,omitempty"`

	// Strike 欄位（統一命名）
	ShortPutStrike  float64 `json:"short_put_strike,omitempty"`
	LongPutStrike   float64 `json:"long_put_strike,omitempty"`
	ShortCallStrike float64 `json:"short_call_strike,omitempty"`
	LongCallStrike  float64 `json:"long_call_strike,omitempty"`

	// Premium
	PremiumReceived  float64 `json:"premium_received,omitempty"`
	ShortPutPremium  float64 `json:"short_put_premium,omitempty"`
	LongPutPremium   float64 `json:"long_put_premium,omitempty"`
	ShortCallPremium float64 `json:"short_call_premium,omitempty"`
	LongCallPremium  float64 `json:"long_call_premium,omitempty"`

	// 共用設定（選填，未填則用策略預設值）
	ProfitTargetPct float64 `json:"profit_target_pct,omitempty"`
	LossLimitPct    float64 `json:"loss_limit_pct,omitempty"`
}

// TotalPremium 同 Position.TotalPremium，用於 request 階段（net premium）
func (r *AddPositionRequest) TotalPremium() float64 {
	if r.Strategy == StrategyIronCondor {
		return (r.ShortPutPremium - r.LongPutPremium) + (r.ShortCallPremium - r.LongCallPremium)
	}
	return r.PremiumReceived
}

func (r *AddPositionRequest) DefaultLossLimit() float64 {
	if r.LossLimitPct > 0 {
		return r.LossLimitPct
	}
	switch r.Strategy {
	case StrategyWheelCSP:
		return 300.0
	case StrategyBullCallSpread, StrategyHedgePut:
		return 100.0
	default:
		return 200.0
	}
}

func (r *AddPositionRequest) DefaultProfitTarget() float64 {
	if r.ProfitTargetPct > 0 {
		return r.ProfitTargetPct
	}
	switch r.Strategy {
	case StrategyBullCallSpread:
		return 100.0
	case StrategyHedgePut:
		return 200.0
	default:
		return 50.0
	}
}

func (s Strategy) IsValid() bool {
	switch s {
	case StrategyWheelCSP, StrategyWheelCC, StrategyIronCondor,
		StrategyBullCallSpread, StrategyHedgePut:
		return true
	}
	return false
}
