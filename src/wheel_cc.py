"""
WHEEL_CC 策略監控規則
═══════════════════════════════════════════════════════════════════
NVDA Covered Call（被 Assign 後，持有 1500 股）

進場：Strike = 被 Assign 成本 × 105%，DTE 14-21 天，15 張
出場條件（系統監控）：
  ✅ 獲利達 50%  → ACTION：買回平倉，重開下一輪 CC
  ❌ 虧損達 200% → ACTION：停損平倉（股價大跌超預期）
  ⏰ DTE ≤ 7 天  → WARNING：Gamma 風險提醒
  ⚠️ 股價距 Call Strike ≤ 5% → WARNING：股票即將被 Assign（賣出）
═══════════════════════════════════════════════════════════════════
"""
from typing import List

from .base import BaseStrategy, Alert
from config import (
    STRATEGY_PROFIT_TARGETS,
    STRATEGY_LOSS_LIMITS,
    DEFAULT_PROFIT_TARGET_PCT,
    DEFAULT_LOSS_LIMIT_PCT,
    DTE_WARNING_DAYS,
    ASSIGNMENT_RISK_PCT,
)


class WheelCCStrategy(BaseStrategy):

    def check(self, position: dict, price_data: dict) -> List[Alert]:
        alerts: List[Alert] = []

        profit_target = self._resolve(
            position, "PROFIT_TARGET_PCT",
            STRATEGY_PROFIT_TARGETS.get("WHEEL_CC", DEFAULT_PROFIT_TARGET_PCT),
        )
        loss_limit = self._resolve(
            position, "LOSS_LIMIT_PCT",
            STRATEGY_LOSS_LIMITS.get("WHEEL_CC", DEFAULT_LOSS_LIMIT_PCT),
        )

        # 1. 獲利達標 → 買回平倉，重開下一輪 CC
        if alert := self._check_take_profit(
            position, price_data, profit_target,
            action="Moomoo 買回平倉 → /close <id> → 重開下一輪 CC（Strike = 成本 × 105%）",
        ):
            alerts.append(alert)

        # 2. 停損觸發（股價大漲，CC 虧損超過門檻）
        if alert := self._check_stop_loss(
            position, price_data, loss_limit,
            action="Moomoo 市價買回平倉 → /close <id> → 評估是否繼續持股或重開 CC",
        ):
            alerts.append(alert)

        # 3. DTE ≤ 7 天：Gamma 風險
        if alert := self._check_dte(
            position, price_data, DTE_WARNING_DAYS,
            action_profit="平倉鎖利，重開新一輪 CC（Strike = 成本 × 105%，DTE 14-21 天）",
            action_loss="評估讓其到期；若 OTM 到期歸零則繼續持股，重開下一輪 CC",
        ):
            alerts.append(alert)

        # 4. Call 被 Assign 風險：股價逼近 Call Strike（股票即將被賣出）
        if alert := self._check_assignment_risk(
            position, price_data, ASSIGNMENT_RISK_PCT, option_type="call",
        ):
            alerts.append(alert)

        return alerts
