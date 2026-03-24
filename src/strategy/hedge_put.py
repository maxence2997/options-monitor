"""
HEDGE_PUT 策略監控規則
═══════════════════════════════════════════════════════════════════
SPY 黑天鵝保險（買方策略）

進場：每季 1 次，DTE 90 天
  買 OTM Put，Strike = 現價 × 85%（深度保護）
  premium_received 為負數（付出保費）

核心理念：這是保費，不是投機部位
  市場正常 → premium 慢慢歸零，屬預期內損失，不要急著出場
  市場崩盤 → Put 大幅獲利，此時考慮部分平倉對沖其他損失

出場條件（系統監控）：
  ✅ 獲利達 200%   → ACTION：黑天鵝發生，建議平倉兌現對沖獲利
  📋 虧損達 100%   → INFO：保費歸零，市場未崩盤，屬正常結果（不是停損！）
  ⏰ DTE ≤ 30 天   → WARNING：準備換下一季保險（早於一般策略的 7 天）
  📈 SPY 漲 +10%   → WARNING：Put 更深 OTM，保護力下降，考慮 Roll Up

⚠️ 重要：不發 ACTION 停損通知，避免誤操作賣掉保險
═══════════════════════════════════════════════════════════════════
"""
from typing import List, Optional

from .base import BaseStrategy, Alert
from config import (
    STRATEGY_PROFIT_TARGETS,
    DEFAULT_PROFIT_TARGET_PCT,
    HEDGE_DTE_ROLL_DAYS,
    HEDGE_ROLL_UP_PCT,
)


class HedgePutStrategy(BaseStrategy):

    def check(self, position: dict, price_data: dict) -> List[Alert]:
        alerts: List[Alert] = []

        profit_target = self._resolve(
            position, "PROFIT_TARGET_PCT",
            STRATEGY_PROFIT_TARGETS.get("HEDGE_PUT", DEFAULT_PROFIT_TARGET_PCT),
        )

        # 1. 獲利達標（黑天鵝發生）→ ACTION：建議平倉兌現對沖獲利
        if alert := self._check_take_profit(
            position, price_data, profit_target,
            action="市場大跌，Hedge Put 大幅獲利。Moomoo 賣出平倉 → /close <id>，對沖其他持倉損失",
        ):
            alerts.append(alert)

        # 2. 保費歸零（虧損 ≥ 100%）→ INFO，不是停損！市場正常才會這樣
        if alert := self._check_premium_expired(position, price_data):
            alerts.append(alert)

        # 3. DTE ≤ 30 天：準備換下一季（比一般策略早很多）
        if alert := self._check_dte_hedge(position, price_data):
            alerts.append(alert)

        # 4. SPY 大幅上漲（+10%）→ Put 更深 OTM，保護力下降，考慮 Roll Up
        if alert := self._check_roll_up(position, price_data):
            alerts.append(alert)

        return alerts

    # ── HEDGE_PUT 專用條件 ─────────────────────────────────────────────

    def _check_premium_expired(self, position: dict,
                                price_data: dict) -> Optional[Alert]:
        """
        保費歸零：pnl_pct <= -100%
        這是預期內的正常結果（市場沒崩），發 INFO 而非 ACTION 停損
        避免使用者看到通知後衝去平倉，砍掉自己的保險
        """
        pnl_pct = price_data["pnl_pct"]
        pnl_usd = price_data["pnl_usd"]
        dte     = price_data["dte"]
        if pnl_pct <= -100.0:
            return self._alert(
                "INFO", "HEDGE_EXPIRED", position,
                f"📋 Hedge Put 保費接近歸零（P&L: {pnl_pct:.1f}%, ${pnl_usd:+,.0f}）\n"
                f"DTE={dte}天 | 市場無崩盤跡象，此為預期內的保費支出\n"
                f"⚠️ 不建議提前平倉，這是你的黑天鵝保險",
                "繼續持有，讓其到期歸零，或等 DTE ≤ 30 天時換下一季",
            )
        return None

    def _check_dte_hedge(self, position: dict,
                          price_data: dict) -> Optional[Alert]:
        """
        DTE ≤ 30 天：提前準備換下一季保險
        比一般策略（7 天）早很多，因為要找好下季到期日和 Strike
        """
        dte     = price_data["dte"]
        pnl_pct = price_data["pnl_pct"]
        pnl_usd = price_data["pnl_usd"]
        if 0 < dte <= HEDGE_DTE_ROLL_DAYS:
            return self._alert(
                "WARNING", "HEDGE_ROLL_SEASON", position,
                f"⏰ Hedge Put 剩 {dte} 天到期，準備換下一季保險\n"
                f"目前 P&L: {pnl_pct:.1f}% (${pnl_usd:+,.0f})",
                f"買入新 SPY Put：Strike = 現價 × 85%，DTE = 90 天（下季）"
                f" → /add 登記新持倉。舊部位可讓其到期或一併平倉",
            )
        return None

    def _check_roll_up(self, position: dict,
                        price_data: dict) -> Optional[Alert]:
        """
        SPY 大幅上漲：Put 更深 OTM，保護力降低
        計算 stock_price 相對於 Strike 的漲幅
        漲幅 >= HEDGE_ROLL_UP_PCT（預設 10%）時發警告

        例：Strike $480，現價 $530 → 漲幅 (530-480)/480 = 10.4% → 觸發
        """
        stock_price = price_data["stock_price"]
        strike      = float(position["LONG_PUT_STRIKE"])
        symbol      = position["SYMBOL"]

        if strike <= 0:
            return None

        upside_pct = (stock_price - strike) / strike * 100
        if upside_pct >= HEDGE_ROLL_UP_PCT:
            return self._alert(
                "WARNING", "HEDGE_ROLL_UP", position,
                f"📈 {symbol} 已從 Strike ${strike:.0f} 上漲 {upside_pct:.1f}%\n"
                f"現價 ${stock_price:.2f}，Hedge Put 保護力降低（更深度 OTM）",
                f"考慮 Roll Up：平倉舊 Put → 改買 Strike = 現價 × 85% 的新 Put"
                f"（可在換季時一併處理）",
            )
        return None
