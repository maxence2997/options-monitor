"""
策略規則檢查模組
═══════════════════════════════════════════════════════════════════
根據 config.py 定義的門檻值，判斷每個持倉是否需要發通知。
「什麼情況該通知」的邏輯在這裡；「門檻數字是多少」在 config.py。
═══════════════════════════════════════════════════════════════════
"""
from dataclasses import dataclass
from typing import List, Optional

from config import (
    DEFAULT_PROFIT_TARGET_PCT,
    DEFAULT_LOSS_LIMIT_PCT,
    STRATEGY_PROFIT_TARGETS,
    STRATEGY_LOSS_LIMITS,
    DTE_WARNING_DAYS,
    ASSIGNMENT_RISK_PCT,
)


@dataclass
class Alert:
    """單一通知的資料結構"""
    level: str        # ACTION（需立即操作）/ WARNING（需注意）/ INFO（參考用）
    alert_type: str   # TAKE_PROFIT / STOP_LOSS / DTE_WARNING / ASSIGNMENT_RISK / IC_BREACH
    position_id: str
    symbol: str
    strategy: str
    message: str      # 發給 Telegram 的訊息內文
    action: str       # 建議你執行的具體操作


def _get_profit_target(position: dict, strategy: str) -> float:
    """
    取得此持倉的獲利目標 %。
    優先序：持倉自訂值 > 策略預設值 > 全域預設值
    （讓你可以針對單筆持倉個別設定不同目標）
    """
    custom = position.get("PROFIT_TARGET_PCT")
    if custom:
        return float(custom)
    return STRATEGY_PROFIT_TARGETS.get(strategy, DEFAULT_PROFIT_TARGET_PCT)


def _get_loss_limit(position: dict, strategy: str) -> float:
    """
    取得此持倉的停損門檻 %。
    優先序：持倉自訂值 > 策略預設值 > 全域預設值
    """
    custom = position.get("LOSS_LIMIT_PCT")
    if custom:
        return float(custom)
    return STRATEGY_LOSS_LIMITS.get(strategy, DEFAULT_LOSS_LIMIT_PCT)


def check_position(position: dict, price_data: dict) -> List[Alert]:
    """
    檢查單一持倉的所有監控條件，回傳需要通知的 Alert 列表。

    position  : 從 Gist 讀出的持倉 dict（key 為大寫，對應 monitor.py 的 sheet_pos）
    price_data: 由 pricing.py 計算出的即時數據 dict
    """
    alerts: List[Alert] = []

    pos_id       = str(position.get("ID", "?"))
    symbol       = position["SYMBOL"]
    strategy     = position["STRATEGY"].upper()
    pnl_pct      = price_data["pnl_pct"]
    pnl_usd      = price_data["pnl_usd"]
    dte          = price_data["dte"]
    distance_pct = price_data["distance_pct"]
    stock_price  = price_data["stock_price"]

    profit_target = _get_profit_target(position, strategy)
    loss_limit    = _get_loss_limit(position, strategy)

    # ── 1. 獲利達標 ──────────────────────────────────────────────────
    # 只對「賣方策略」觸發，買方策略（BULL_CALL_SPREAD）另有邏輯。
    # 賣方的 P&L% 是「已回收的 premium 佔原始收益的比例」。
    if strategy in ("WHEEL_CSP", "WHEEL_CC", "IRON_CONDOR") and pnl_pct >= profit_target:
        alerts.append(Alert(
            level="ACTION",
            alert_type="TAKE_PROFIT",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(
                f"🎯 獲利達標！P&L: +{pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                f"已達 {profit_target:.0f}% 目標，建議提前平倉收割"
            ),
            action=f"買回 {symbol} {strategy} 平倉，進入下一輪"
        ))

    # ── 2. 停損觸發 ──────────────────────────────────────────────────
    # 所有策略都監控，pnl_pct 為負值時才有意義。
    if pnl_pct <= -loss_limit:
        alerts.append(Alert(
            level="ACTION",
            alert_type="STOP_LOSS",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(
                f"🛑 停損觸發！P&L: {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                f"虧損超過門檻 {loss_limit:.0f}%，立刻平倉止損"
            ),
            action=f"立刻市價買回 {symbol} {strategy} 平倉"
        ))

    # ── 3. 接近到期 ──────────────────────────────────────────────────
    # DTE_WARNING_DAYS（預設 7 天）以內發警告。
    # 根據目前是獲利或虧損，給出不同的建議操作。
    if 0 < dte <= DTE_WARNING_DAYS:
        if pnl_pct > 0:
            msg    = (f"⏰ 期權快到期！DTE={dte}天，目前獲利 {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                      f"建議平倉鎖定獲利，避免 Gamma 風險")
            action = "平倉鎖利，避免最後幾天波動"
        else:
            msg    = (f"⏰ 期權快到期！DTE={dte}天，目前虧損 {pnl_pct:.1f}% (${pnl_usd:+,.0f})\n"
                      f"評估是否平倉或讓其到期")
            action = "評估到期結果，若 ITM 準備被 Assign"

        alerts.append(Alert(
            level="WARNING",
            alert_type="DTE_WARNING",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=msg,
            action=action,
        ))

    # ── 4. Assignment 風險（賣 Put）──────────────────────────────────
    # 股價從上方接近 Put Strike 時（distance_pct 為正且很小），
    # 代表快要被迫接股票，給你時間決定是否 Roll 展期。
    if strategy == "WHEEL_CSP" and 0 < distance_pct <= ASSIGNMENT_RISK_PCT:
        alerts.append(Alert(
            level="WARNING",
            alert_type="ASSIGNMENT_RISK",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(
                f"⚠️ Assignment 風險！{symbol} 現價 ${stock_price:.2f}，"
                f"距 Put Strike 僅 {distance_pct:.1f}%\n"
                f"股價繼續下跌可能被迫買進股票"
            ),
            action="確認現金是否充足，或考慮 Roll Down（展期至更低 Strike）"
        ))

    # ── 5. Assignment 風險（賣 Call）─────────────────────────────────
    # 股價從下方接近 Call Strike 時（distance_pct 為正且很小），
    # 代表持有的股票快要被以 Strike 價賣出。
    if strategy == "WHEEL_CC" and 0 < distance_pct <= ASSIGNMENT_RISK_PCT:
        alerts.append(Alert(
            level="WARNING",
            alert_type="ASSIGNMENT_RISK",
            position_id=pos_id,
            symbol=symbol,
            strategy=strategy,
            message=(
                f"⚠️ Call 被 Assign 風險！{symbol} 現價 ${stock_price:.2f}，"
                f"距 Call Strike 僅 {distance_pct:.1f}%\n"
                f"股票可能被以 Strike 價賣出"
            ),
            action="若不想賣出持股，考慮 Roll Up（展期至更高 Strike）"
        ))

    return alerts


def check_iron_condor_breach(position: dict, price_data: dict) -> Optional[Alert]:
    """
    專門檢查 Iron Condor 是否已突破任一翼（Put 側或 Call 側）。

    IC 的風險結構：
      Put Long  ---- Put Short ---- [安全區間] ---- Call Short ---- Call Long
      若股價跌破 Put Short 或漲過 Call Short，代表進入虧損區間。

    Notes 欄位格式範例：「call_short=702 | call_buy=722」
    Put 側的 Strike 直接存在 STRIKE_SELL（Put Short）。
    """
    if position["STRATEGY"].upper() != "IRON_CONDOR":
        return None

    stock_price = price_data["stock_price"]
    put_short   = float(position["STRIKE_SELL"])
    notes       = str(position.get("NOTES", ""))

    # 從 notes 解析 Call Short Strike
    call_short: Optional[float] = None
    for part in notes.split("|"):
        part = part.strip().lower()
        if part.startswith("call_short="):
            try:
                call_short = float(part.split("=")[1].strip())
            except ValueError:
                pass

    # Put 側突破：股價 < Put Short
    if stock_price < put_short:
        return Alert(
            level="WARNING",
            alert_type="IC_BREACH",
            position_id=str(position.get("ID", "?")),
            symbol=position["SYMBOL"],
            strategy="IRON_CONDOR",
            message=(
                f"⚠️ Iron Condor Put 側突破！\n"
                f"{position['SYMBOL']} 現價 ${stock_price:.2f} < Put Short ${put_short:.0f}\n"
                f"下行翼已被突破，考慮平倉或調整"
            ),
            action="評估是否整組平倉，或單獨平掉 Put Spread"
        )

    # Call 側突破：股價 > Call Short（只有在解析到 call_short 的情況下才檢查）
    if call_short and stock_price > call_short:
        return Alert(
            level="WARNING",
            alert_type="IC_BREACH",
            position_id=str(position.get("ID", "?")),
            symbol=position["SYMBOL"],
            strategy="IRON_CONDOR",
            message=(
                f"⚠️ Iron Condor Call 側突破！\n"
                f"{position['SYMBOL']} 現價 ${stock_price:.2f} > Call Short ${call_short:.0f}\n"
                f"上行翼已被突破，考慮平倉或調整"
            ),
            action="評估是否整組平倉，或單獨平掉 Call Spread"
        )

    return None
