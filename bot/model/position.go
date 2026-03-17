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

type Position struct {
	ID              int      `json:"id"`
	Strategy        Strategy `json:"strategy"`
	Symbol          string   `json:"symbol"`
	Status          Status   `json:"status"`
	OpenDate        string   `json:"open_date"`
	Expiry          string   `json:"expiry"`
	Contracts       int      `json:"contracts"`
	Notes           string   `json:"notes,omitempty"`
	CreatedAt       time.Time `json:"created_at"`

	// ── 非 IC 策略（WHEEL_CSP / WHEEL_CC / BULL_CALL_SPREAD / HEDGE_PUT）──
	// IRON_CONDOR 不使用這三個欄位
	StrikeSell      float64 `json:"strike_sell,omitempty"`
	StrikeBuy       float64 `json:"strike_buy,omitempty"`
	PremiumReceived float64 `json:"premium_received,omitempty"`

	// ── IC 專用欄位 ───────────────────────────────────────────────────────
	// 兩筆單分開記錄，PnL 計算更精確
	PutStrikeShort  float64 `json:"put_strike_short,omitempty"`
	PutStrikeLong   float64 `json:"put_strike_long,omitempty"`
	PutPremium      float64 `json:"put_premium,omitempty"`
	CallStrikeShort float64 `json:"call_strike_short,omitempty"`
	CallStrikeLong  float64 `json:"call_strike_long,omitempty"`
	CallPremium     float64 `json:"call_premium,omitempty"`

	// ── 共用設定 ──────────────────────────────────────────────────────────
	ProfitTargetPct float64 `json:"profit_target_pct"`
	LossLimitPct    float64 `json:"loss_limit_pct"`
}

// TotalPremium 回傳此持倉的總 premium（IC 加總兩側，其他直接回傳）
func (p *Position) TotalPremium() float64 {
	if p.Strategy == StrategyIronCondor {
		return p.PutPremium + p.CallPremium
	}
	return p.PremiumReceived
}

// ── AddPositionRequest ────────────────────────────────────────────────────────

type AddPositionRequest struct {
	Strategy  Strategy `json:"strategy"`
	Symbol    string   `json:"symbol"`
	Expiry    string   `json:"expiry"`
	Contracts int      `json:"contracts"`
	Notes     string   `json:"notes,omitempty"`

	// 非 IC 策略
	StrikeSell      float64 `json:"strike_sell,omitempty"`
	StrikeBuy       float64 `json:"strike_buy,omitempty"`
	PremiumReceived float64 `json:"premium_received,omitempty"`

	// IC 專用
	PutStrikeShort  float64 `json:"put_strike_short,omitempty"`
	PutStrikeLong   float64 `json:"put_strike_long,omitempty"`
	PutPremium      float64 `json:"put_premium,omitempty"`
	CallStrikeShort float64 `json:"call_strike_short,omitempty"`
	CallStrikeLong  float64 `json:"call_strike_long,omitempty"`
	CallPremium     float64 `json:"call_premium,omitempty"`

	// 共用設定
	ProfitTargetPct float64 `json:"profit_target_pct,omitempty"`
	LossLimitPct    float64 `json:"loss_limit_pct,omitempty"`
}

// TotalPremium 同上，用於 AddPositionRequest
func (r *AddPositionRequest) TotalPremium() float64 {
	if r.Strategy == StrategyIronCondor {
		return r.PutPremium + r.CallPremium
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
