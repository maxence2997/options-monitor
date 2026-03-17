"""
策略基底模組
═══════════════════════════════════════════════════════════════════
Alert dataclass：所有通知的統一資料結構
BaseStrategy：抽象基底，提供共用條件檢查 helper
子類別只需實作 check()，並呼叫需要的 helper 組合條件
═══════════════════════════════════════════════════════════════════
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Alert:
    """單一通知的資料結構"""
    level: str        # ACTION（需立即操作）/ WARNING（需注意）/ INFO（參考用）
    alert_type: str   # 見各 helper 的 alert_type 常數
    position_id: str
    symbol: str
    strategy: str
    message: str      # 發給 Telegram 的訊息內文
    action: str       # 建議執行的具體操作


class BaseStrategy(ABC):

    @abstractmethod
    def check(self, position: dict, price_data: dict) -> List[Alert]:
        """
        檢查單一持倉的所有監控條件，回傳需要通知的 Alert 列表。

        position  : monitor.py 組裝的 sheet_pos dict（key 為大寫）
        price_data: pricing.py 計算出的即時數據 dict
        """
        ...

    # ── 內部 factory ──────────────────────────────────────────────────
    def _alert(self, level: str, alert_type: str, position: dict,
               message: str, action: str) -> Alert:
        return Alert(
            level=level,
            alert_type=alert_type,
            position_id=str(position.get("ID", "?")),
            symbol=position["SYMBOL"],
            strategy=position["STRATEGY"],
            message=message,
            action=action,
        )

    def _resolve(self, position: dict, key: str, default: float) -> float:
        """持倉自訂值優先；未設定則用傳入的 default（來自 config）"""
        val = position.get(key)
        return float(val) if val else default

    # ── 共用條件 helper ───────────────────────────────────────────────

    def _check_take_profit(self, position: dict, price_data: dict,
                           profit_target_pct: float,
                           action: Optional[str] = None) -> Optional[Alert]:
        """獲利達標：pnl_pct >= profit_target_pct → ACTION"""
        pnl_pct = price_data["pnl_pct"]
        pnl_usd = price_data["pnl_usd"]
        symbol  = position["SYMBOL"]
        strategy = position["STRATEGY"]
        if pnl_pct >= profit_target_pct:
            return self._alert(
                "ACTION", "TAKE_PROFIT", position,
                f"🎯 獲利達標！P&L: +{pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                f"已達 {profit_target_pct:.0f}% 目標，建議提前平倉收割",
                action or f"買回 {symbol} {strategy} 平倉，進入下一輪",
            )
        return None

    def _check_stop_loss(self, position: dict, price_data: dict,
                         loss_limit_pct: float,
                         action: Optional[str] = None) -> Optional[Alert]:
        """停損觸發：pnl_pct <= -loss_limit_pct → ACTION"""
        pnl_pct  = price_data["pnl_pct"]
        pnl_usd  = price_data["pnl_usd"]
        symbol   = position["SYMBOL"]
        strategy = position["STRATEGY"]
        if pnl_pct <= -loss_limit_pct:
            return self._alert(
                "ACTION", "STOP_LOSS", position,
                f"🛑 停損觸發！P&L: {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                f"虧損超過門檻 {loss_limit_pct:.0f}%，立刻平倉止損",
                action or f"立刻市價買回 {symbol} {strategy} 平倉",
            )
        return None

    def _check_dte(self, position: dict, price_data: dict,
                   dte_threshold: int,
                   action_profit: Optional[str] = None,
                   action_loss: Optional[str] = None) -> Optional[Alert]:
        """
        到期日警告：0 < DTE <= dte_threshold → WARNING
        獲利/虧損時給不同訊息，呼叫端可覆蓋 action 文字
        """
        dte     = price_data["dte"]
        pnl_pct = price_data["pnl_pct"]
        pnl_usd = price_data["pnl_usd"]
        if 0 < dte <= dte_threshold:
            if pnl_pct > 0:
                msg    = (f"⏰ 期權快到期！DTE={dte}天，目前獲利 {pnl_pct:.1f}% "
                          f"(${pnl_usd:+,.0f})\n建議平倉鎖定獲利，避免 Gamma 風險")
                action = action_profit or "平倉鎖利，避免最後幾天波動"
            else:
                msg    = (f"⏰ 期權快到期！DTE={dte}天，目前虧損 {pnl_pct:.1f}% "
                          f"(${pnl_usd:+,.0f})\n評估是否平倉或讓其到期")
                action = action_loss or "評估到期損益，決定是否平倉"
            return self._alert("WARNING", "DTE_WARNING", position, msg, action)
        return None

    def _check_assignment_risk(self, position: dict, price_data: dict,
                               risk_pct: float,
                               option_type: str = "put") -> Optional[Alert]:
        """
        Assignment 風險：0 < distance_pct <= risk_pct → WARNING
        distance_pct 由 pricing.py 依策略計算（靠近 Strike 時為正小值）
        """
        stock_price  = price_data["stock_price"]
        distance_pct = price_data["distance_pct"]
        symbol       = position["SYMBOL"]
        if 0 < distance_pct <= risk_pct:
            if option_type == "put":
                return self._alert(
                    "WARNING", "ASSIGNMENT_RISK", position,
                    f"⚠️ Assignment 風險！{symbol} 現價 ${stock_price:.2f}，"
                    f"距 Put Strike 僅 {distance_pct:.1f}%\n"
                    f"股價繼續下跌可能被迫買進股票",
                    "確認現金是否充足，或考慮 Roll Down（展期至更低 Strike）",
                )
            else:
                return self._alert(
                    "WARNING", "ASSIGNMENT_RISK", position,
                    f"⚠️ Call 被 Assign 風險！{symbol} 現價 ${stock_price:.2f}，"
                    f"距 Call Strike 僅 {distance_pct:.1f}%\n"
                    f"股票可能被以 Strike 價賣出",
                    "若不想賣出持股，考慮 Roll Up（展期至更高 Strike）",
                )
        return None
