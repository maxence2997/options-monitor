"""
WHEEL_CSP 策略監控規則
═══════════════════════════════════════════════════════════════════
NVDA 賣 Put（Wheel 第一步）

進場：Strike = 現價 × 88%，DTE 21-30 天，15 張
出場條件（系統監控）：
  ✅ 獲利達 50%  → ACTION：買回平倉，進下一輪
  ❌ 虧損達 300% → ACTION：停損平倉（NVDA 波動大，門檻放寬）
  ⏰ DTE ≤ 7 天  → WARNING：Gamma 風險提醒
  ⚠️ 股價距 Strike ≤ 5% → WARNING：Assignment 風險
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


class WheelCSPStrategy(BaseStrategy):

    def check(self, position: dict, price_data: dict) -> List[Alert]:
        alerts: List[Alert] = []

        profit_target = self._resolve(
            position, "PROFIT_TARGET_PCT",
            STRATEGY_PROFIT_TARGETS.get("WHEEL_CSP", DEFAULT_PROFIT_TARGET_PCT),
        )
        loss_limit = self._resolve(
            position, "LOSS_LIMIT_PCT",
            STRATEGY_LOSS_LIMITS.get("WHEEL_CSP", DEFAULT_LOSS_LIMIT_PCT),
        )

        # 1. 獲利達標 → 買回平倉，進下一輪 CSP
        if alert := self._check_take_profit(
            position, price_data, profit_target,
            action="Moomoo 買回平倉 → /close <id> → 開下一輪 CSP",
        ):
            alerts.append(alert)

        # 2. 停損觸發（NVDA 波動大，門檻 300%）
        if alert := self._check_stop_loss(
            position, price_data, loss_limit,
            action="Moomoo 市價買回平倉 → /close <id> → 本月暫停開新 CSP",
        ):
            alerts.append(alert)

        # 3. DTE ≤ 7 天：Gamma 風險
        if alert := self._check_dte(
            position, price_data, DTE_WARNING_DAYS,
            action_profit="平倉鎖利，避免 Gamma 風險，等機會開下一輪 CSP",
            action_loss="評估是否讓其到期；若 ITM 準備接股票（進入 CC Phase）",
        ):
            alerts.append(alert)

        # 4. Assignment 風險：股價靠近 Put Strike（距離 ≤ 5%）
        if alert := self._check_assignment_risk(
            position, price_data, ASSIGNMENT_RISK_PCT, option_type="put",
        ):
            alerts.append(alert)

        return alerts
