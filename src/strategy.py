"""
策略規則檢查模組
根據機械化規則判斷每個持倉需要什麼行動
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Alert:
    level: str          # INFO / WARNING / ACTION
    alert_type: str     # DAILY_SUMMARY / DTE_WARNING / TAKE_PROFIT / STOP_LOSS / ASSIGNMENT_RISK
    position_id: str
    symbol: str
    strategy: str
    message: str
    action: str         # 建議操作


DEFAULT_PROFIT_TARGET = 50.0   # 賺到 50% premium → 平倉
DEFAULT_LOSS_LIMIT    = 200.0  # 虧損超過 200% premium → 停損

# NVDA 波動大，停損門檻放寬
STRATEGY_LOSS_LIMITS = {
    "WHEEL_CSP":       300.0,
    "WHEEL_CC":        200.0,
    "IRON_CONDOR":     200.0,
    "BULL_CALL_SPREAD":100.0,  # 買方，虧完就是虧完
    "HEDGE_PUT":       100.0,
}

DTE_WARNING_DAYS     = 7    # DTE ≤ 7 天 → 提醒準備處理
ASSIGNMENT_RISK_PCT  = 5.0  # 股價距 Strike ≤ 5% → 有被 Assign 風險


def check_position(position: dict, price_data: dict) -> List[Alert]:
    """
    檢查單一持倉，回傳需要通知的 Alert 列表
    """
    alerts = []
    pos_id   = str(position.get("ID", "?"))
    symbol   = position["SYMBOL"]
    strategy = position["STRATEGY"].upper()
    
    pnl_pct      = price_data["pnl_pct"]
    dte          = price_data["dte"]
    distance_pct = price_data["distance_pct"]
    pnl_usd      = price_data["pnl_usd"]
    stock_price  = price_data["stock_price"]

    profit_target = float(position.get("PROFIT_TARGET_PCT") or DEFAULT_PROFIT_TARGET)
    loss_limit    = float(position.get("LOSS_LIMIT_PCT") or
                         STRATEGY_LOSS_LIMITS.get(strategy, DEFAULT_LOSS_LIMIT))

    # ── 1. 獲利達標 ──────────────────────────────────────────────
    if strategy in ("WHEEL_CSP", "WHEEL_CC", "IRON_CONDOR") and pnl_pct >= profit_target:
        alerts.append(Alert(
            level="ACTION",
            alert_type="TAKE_PROFIT",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(f"🎯 獲利達標！P&L: +{pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                     f"已達 {profit_target:.0f}% 目標，建議提前平倉收割"),
            action=f"買回 {symbol} {strategy} 平倉，進入下一輪"
        ))

    # ── 2. 停損觸發 ──────────────────────────────────────────────
    if pnl_pct <= -loss_limit:
        alerts.append(Alert(
            level="ACTION",
            alert_type="STOP_LOSS",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(f"🛑 停損觸發！P&L: {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                     f"虧損超過門檻 {loss_limit:.0f}%，立刻平倉止損"),
            action=f"立刻市價買回 {symbol} {strategy} 平倉"
        ))

    # ── 3. 接近到期 ──────────────────────────────────────────────
    if 0 < dte <= DTE_WARNING_DAYS:
        if pnl_pct > 0:
            msg = (f"⏰ 期權快到期！DTE={dte}天，目前獲利 {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                   f"建議平倉鎖定獲利，避免 Gamma 風險")
            action = "平倉鎖利，避免最後幾天波動"
        else:
            msg = (f"⏰ 期權快到期！DTE={dte}天，目前虧損 {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                   f"評估是否平倉或讓其到期")
            action = "評估到期結果，若 ITM 準備被 Assign"
        
        alerts.append(Alert(
            level="WARNING",
            alert_type="DTE_WARNING",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=msg,
            action=action
        ))

    # ── 4. Assignment 風險（只對賣方 Put/Call）──────────────────
    if strategy in ("WHEEL_CSP",) and 0 < distance_pct <= ASSIGNMENT_RISK_PCT:
        alerts.append(Alert(
            level="WARNING",
            alert_type="ASSIGNMENT_RISK",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(f"⚠️ Assignment 風險！{symbol} 現價 ${stock_price:.2f}，"
                     f"距 Put Strike 僅 {distance_pct:.1f}%\n"
                     f"股價繼續下跌可能被迫買進股票"),
            action=f"確認現金是否充足，或考慮 Roll Down（展期）"
        ))

    if strategy in ("WHEEL_CC",) and 0 < distance_pct <= ASSIGNMENT_RISK_PCT:
        alerts.append(Alert(
            level="WARNING",
            alert_type="ASSIGNMENT_RISK",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(f"⚠️ Call 被 Assign 風險！{symbol} 現價 ${stock_price:.2f}，"
                     f"距 Call Strike 僅 {distance_pct:.1f}%\n"
                     f"股票可能被以 Strike 價賣出"),
            action=f"若不想賣出持股，考慮 Roll Up（展期至更高 Strike）"
        ))

    return alerts


def check_iron_condor_breach(position: dict, price_data: dict) -> Optional[Alert]:
    """專門檢查 Iron Condor 是否已突破任一翼"""
    if position["STRATEGY"].upper() != "IRON_CONDOR":
        return None
    
    stock_price = price_data["stock_price"]
    strike_sell = float(position["STRIKE_SELL"])  # Put Short Strike
    notes = str(position.get("NOTES", ""))
    
    # Notes 格式: "call_short=XXX"（Iron Condor 的 Call Short Strike）
    call_short = None
    for part in notes.split("|"):
        if "call_short=" in part.lower():
            try:
                call_short = float(part.lower().split("call_short=")[1].strip())
            except:
                pass
    
    if stock_price < strike_sell:
        return Alert(
            level="WARNING",
            alert_type="IC_BREACH",
            position_id=str(position.get("ID", "?")),
            symbol=position["SYMBOL"],
            strategy="IRON_CONDOR",
            message=(f"⚠️ Iron Condor Put 側突破！\n"
                     f"{position['SYMBOL']} 現價 ${stock_price:.2f} < Put Short ${strike_sell:.0f}\n"
                     f"下行翼已被突破，考慮平倉或調整"),
            action="評估是否整組平倉，或單獨平掉 Put Spread"
        )
    
    if call_short and stock_price > call_short:
        return Alert(
            level="WARNING",
            alert_type="IC_BREACH",
            position_id=str(position.get("ID", "?")),
            symbol=position["SYMBOL"],
            strategy="IRON_CONDOR",
            message=(f"⚠️ Iron Condor Call 側突破！\n"
                     f"{position['SYMBOL']} 現價 ${stock_price:.2f} > Call Short ${call_short:.0f}\n"
                     f"上行翼已被突破，考慮平倉或調整"),
            action="評估是否整組平倉，或單獨平掉 Call Spread"
        )
    
    return None
