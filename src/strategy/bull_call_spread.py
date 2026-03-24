"""
BULL_CALL_SPREAD 策略監控規則
═══════════════════════════════════════════════════════════════════
QQQ 方向性押注（買方策略）

進場：每 2 個月 1 次，DTE 45-60 天，10 張
  買 ATM Call（LONG_CALL_STRIKE）
  賣 +10% Call（SHORT_CALL_STRIKE）
  premium_received 為負數（付出成本）

最大損益：
  最大獲利 = Spread 寬度 - premium 成本（翻倍即出）
  最大虧損 = premium 成本（100% 歸零）

出場條件（系統監控）：
  ✅ 獲利達 100% → ACTION：Spread 翻倍，平倉鎖利
  ❌ 虧損達 100% → ACTION：premium 歸零，停損
  ⏰ DTE ≤ 7 天  → WARNING：評估剩餘時間價值

注意：此策略為買方，pnl_pct > 0 代表獲利，無 Assignment 風險
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
)


class BullCallSpreadStrategy(BaseStrategy):

    def check(self, position: dict, price_data: dict) -> List[Alert]:
        alerts: List[Alert] = []

        profit_target = self._resolve(
            position, "PROFIT_TARGET_PCT",
            STRATEGY_PROFIT_TARGETS.get("BULL_CALL_SPREAD", DEFAULT_PROFIT_TARGET_PCT),
        )
        loss_limit = self._resolve(
            position, "LOSS_LIMIT_PCT",
            STRATEGY_LOSS_LIMITS.get("BULL_CALL_SPREAD", DEFAULT_LOSS_LIMIT_PCT),
        )

        # 1. 獲利達標（翻倍）→ 平倉鎖利
        if alert := self._check_take_profit(
            position, price_data, profit_target,
            action="Moomoo 賣出 Call Spread 平倉 → /close <id>，恭喜方向押對！",
        ):
            alerts.append(alert)

        # 2. 停損（premium 歸零，最大虧損已到）→ 平倉止損
        if alert := self._check_stop_loss(
            position, price_data, loss_limit,
            action="Moomoo 賣出 Call Spread 平倉 → /close <id>，已達最大虧損，不再惡化",
        ):
            alerts.append(alert)

        # 3. DTE ≤ 7 天：提醒評估時間價值
        if alert := self._check_dte(
            position, price_data, DTE_WARNING_DAYS,
            action_profit="Spread 接近到期且有獲利，建議平倉鎖利避免最後幾天波動",
            action_loss="剩餘時間價值極低，評估是否提前認賠或等到期歸零",
        ):
            alerts.append(alert)

        return alerts
