"""
IRON_CONDOR 策略監控規則
═══════════════════════════════════════════════════════════════════
SPY Iron Condor（定義風險、穩定收 premium）

進場：每月第一個交易日，30-45 DTE，20 張
  Put Short  = 現價 × 94%  （PUT_STRIKE_SHORT）
  Put Long   = 現價 × 91%  （PUT_STRIKE_LONG）
  Call Short = 現價 × 106% （CALL_STRIKE_SHORT）
  Call Long  = 現價 × 109% （CALL_STRIKE_LONG）
  在 Moomoo 分兩筆下單，各自記錄 put_premium / call_premium

PnL 計算：
  pricing.py 分別抓 Put Spread + Call Spread 現值加總
  pnl_pct = (total_premium - 現值合計) / total_premium × 100%

出場條件（系統監控）：
  ✅ 獲利達 50%       → ACTION：整組平倉，等下月
  ❌ 虧損達 200%      → ACTION：整組平倉
  ⏰ DTE ≤ 7 天且獲利 → WARNING：提前平倉避免 Gamma 風險
  ⚠️ 翼突破（任一側） → WARNING：股價突破 Short Strike
═══════════════════════════════════════════════════════════════════
"""
from typing import List, Optional

from .base import BaseStrategy, Alert
from config import (
    STRATEGY_PROFIT_TARGETS,
    STRATEGY_LOSS_LIMITS,
    DEFAULT_PROFIT_TARGET_PCT,
    DEFAULT_LOSS_LIMIT_PCT,
    DTE_WARNING_DAYS,
    IC_BREACH_BUFFER_PCT,
)


class IronCondorStrategy(BaseStrategy):

    def check(self, position: dict, price_data: dict) -> List[Alert]:
        alerts: List[Alert] = []

        profit_target = self._resolve(
            position, "PROFIT_TARGET_PCT",
            STRATEGY_PROFIT_TARGETS.get("IRON_CONDOR", DEFAULT_PROFIT_TARGET_PCT),
        )
        loss_limit = self._resolve(
            position, "LOSS_LIMIT_PCT",
            STRATEGY_LOSS_LIMITS.get("IRON_CONDOR", DEFAULT_LOSS_LIMIT_PCT),
        )

        # 1. 獲利達標 → 整組平倉，等下月
        if alert := self._check_take_profit(
            position, price_data, profit_target,
            action="Moomoo 整組平倉（Put Spread + Call Spread）→ /close <id> → 等下月第一交易日開新 IC",
        ):
            alerts.append(alert)

        # 2. 停損觸發 → 整組平倉
        if alert := self._check_stop_loss(
            position, price_data, loss_limit,
            action="Moomoo 整組平倉 → /close <id> → 本月不再開新 IC",
        ):
            alerts.append(alert)

        # 3. DTE ≤ 7 天
        if alert := self._check_dte_ic(position, price_data):
            alerts.append(alert)

        # 4. 翼突破（從 price_data 直接讀，不用 parse notes）
        if alert := self._check_ic_breach(position, price_data):
            alerts.append(alert)

        return alerts

    # ── IC 專用 DTE 檢查 ──────────────────────────────────────────────
    def _check_dte_ic(self, position: dict, price_data: dict) -> Optional[Alert]:
        dte     = price_data["dte"]
        pnl_pct = price_data["pnl_pct"]
        pnl_usd = price_data["pnl_usd"]

        if not (0 < dte <= DTE_WARNING_DAYS):
            return None

        if pnl_pct > 0:
            return self._alert(
                "WARNING", "DTE_WARNING", position,
                f"⏰ IC 快到期！DTE={dte}天，目前獲利 {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                f"建議整組平倉鎖利，Gamma 風險在最後幾天急劇上升",
                "Moomoo 整組平倉 → /close <id>，不要賭最後幾天",
            )
        else:
            return self._alert(
                "WARNING", "DTE_WARNING", position,
                f"⏰ IC 快到期！DTE={dte}天，目前虧損 {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                f"若雙側皆 OTM，可考慮讓其到期歸零",
                "確認 SPY 價格仍在 Put Short ~ Call Short 之間，若超出則考慮平倉",
            )

    # ── IC 翼突破檢查 ─────────────────────────────────────────────────
    def _check_ic_breach(self, position: dict, price_data: dict) -> Optional[Alert]:
        """
        直接從 position 的正式欄位讀 Strike，不再 parse notes 字串。
        pricing.py 額外回傳的 put_spread_current / call_spread_current
        可用來判斷哪一側虧損更重，但目前只做方向警告即可。
        """
        stock_price       = price_data["stock_price"]
        put_strike_short  = float(position["PUT_STRIKE_SHORT"])
        call_strike_short = float(position["CALL_STRIKE_SHORT"])
        symbol            = position["SYMBOL"]

        # Put 側突破（扣除緩衝）
        if stock_price < put_strike_short * (1 - IC_BREACH_BUFFER_PCT / 100):
            return self._alert(
                "WARNING", "IC_BREACH", position,
                f"⚠️ Iron Condor Put 側突破！\n"
                f"{symbol} 現價 ${stock_price:.2f} < Put Short ${put_strike_short:.0f}\n"
                f"下行翼已被突破，進入虧損區間",
                "評估是否整組平倉，或單獨平掉 Put Spread（保留 Call Spread）",
            )

        # Call 側突破（扣除緩衝）
        if stock_price > call_strike_short * (1 + IC_BREACH_BUFFER_PCT / 100):
            return self._alert(
                "WARNING", "IC_BREACH", position,
                f"⚠️ Iron Condor Call 側突破！\n"
                f"{symbol} 現價 ${stock_price:.2f} > Call Short ${call_strike_short:.0f}\n"
                f"上行翼已被突破，進入虧損區間",
                "評估是否整組平倉，或單獨平掉 Call Spread（保留 Put Spread）",
            )

        return None
