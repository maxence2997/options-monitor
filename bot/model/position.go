package model

import "time"

type Strategy string

const (
	StrategyWheelCSP      Strategy = "WHEEL_CSP"
	StrategyWheelCC       Strategy = "WHEEL_CC"
	StrategyIronCondor    Strategy = "IRON_CONDOR"
	StrategyBullCallSpread Strategy = "BULL_CALL_SPREAD"
	StrategyHedgePut      Strategy = "HEDGE_PUT"
)

type Status string

const (
	StatusOpen     Status = "OPEN"
	StatusClosed   Status = "CLOSED"
	StatusAssigned Status = "ASSIGNED"
)

type Position struct {
	ID               int      `json:"id"`
	Strategy         Strategy `json:"strategy"`
	Symbol           string   `json:"symbol"`
	Status           Status   `json:"status"`
	OpenDate         string   `json:"open_date"`
	Expiry           string   `json:"expiry"`
	Contracts        int      `json:"contracts"`
	StrikeSell       float64  `json:"strike_sell"`
	StrikeBuy        float64  `json:"strike_buy,omitempty"`
	PremiumReceived  float64  `json:"premium_received"`
	ProfitTargetPct  float64  `json:"profit_target_pct"`
	LossLimitPct     float64  `json:"loss_limit_pct"`
	Notes            string   `json:"notes,omitempty"`
	CreatedAt        time.Time `json:"created_at"`
}

type Store struct {
	Positions  []Position `json:"positions"`
	NextID     int        `json:"next_id"`
	LastUpdate string  `json:"last_update"`
}

// AddPositionRequest は /add コマンドで受け取る JSON
type AddPositionRequest struct {
	Strategy        Strategy `json:"strategy"`
	Symbol          string   `json:"symbol"`
	Expiry          string   `json:"expiry"`
	Contracts       int      `json:"contracts"`
	StrikeSell      float64  `json:"strike_sell"`
	StrikeBuy       float64  `json:"strike_buy,omitempty"`
	PremiumReceived float64  `json:"premium_received"`
	ProfitTargetPct float64  `json:"profit_target_pct,omitempty"`
	LossLimitPct    float64  `json:"loss_limit_pct,omitempty"`
	Notes           string   `json:"notes,omitempty"`
}

// DefaultLossLimit returns strategy-specific default loss limit
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
