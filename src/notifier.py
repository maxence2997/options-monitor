"""
Telegram 通知模組
═══════════════════════════════════════════════════════════════════
負責格式化並發送各類通知。

Chat 分離設計：
  TELEGRAM_CHAT_ID        → Bot 指令的回覆對象（你跟 Bot 的私聊）
  TELEGRAM_NOTIFY_CHAT_ID → cron 定時通知的目標（可以是群組或另一個 chat）

若未設定 TELEGRAM_NOTIFY_CHAT_ID，所有通知都會發到 TELEGRAM_CHAT_ID（向下相容）。
═══════════════════════════════════════════════════════════════════
"""
import requests
import os
from datetime import datetime, timezone
from typing import List
from strategy import Alert


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def _now_utc() -> str:
    """回傳目前 UTC 時間字串，格式：2026-03-16 18:30 UTC"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _weekday_zh(dt: datetime) -> str:
    """回傳中文星期"""
    names = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    return names[dt.weekday()]


def _get_notify_chat_id() -> str:
    """
    取得通知專用的 chat_id。
    優先用 TELEGRAM_NOTIFY_CHAT_ID，若未設定則 fallback 到 TELEGRAM_CHAT_ID。
    """
    return (
        os.environ.get("TELEGRAM_NOTIFY_CHAT_ID")
        or os.environ.get("TELEGRAM_CHAT_ID", "")
    )


def send_message(text: str, parse_mode: str = "HTML",
                 notify: bool = False) -> bool:
    """
    發送 Telegram 訊息。

    notify=False（預設）：發到 TELEGRAM_CHAT_ID（Bot 指令頻道）
    notify=True          ：發到 TELEGRAM_NOTIFY_CHAT_ID（通知頻道）
                           若未設定 NOTIFY_CHAT_ID 則 fallback 到 CHAT_ID
    """
    token   = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = _get_notify_chat_id() if notify else os.environ.get("TELEGRAM_CHAT_ID", "")

    if not token or not chat_id:
        print("[Telegram] 未設定 BOT_TOKEN 或 CHAT_ID，跳過通知")
        return False

    url  = TELEGRAM_API.format(token=token)
    data = {
        "chat_id":    chat_id,
        "text":       text,
        "parse_mode": parse_mode,
    }

    resp = requests.post(url, json=data, timeout=10)
    if resp.status_code == 200:
        print(f"[Telegram] 訊息發送成功（chat={chat_id}）")
        return True
    else:
        print(f"[Telegram] 發送失敗: {resp.status_code} {resp.text}")
        return False


def format_alert(alert: Alert, price_data: dict | None = None) -> str:
    """
    將單一 Alert 格式化成 Telegram 訊息。
    每種 alert_type 有獨立的版面，加上觸發時間、持倉 ID、現價、Strike 距離、DTE。

    price_data（選填）：若傳入，顯示現價 & Strike 距離 % & DTE
    """
    now = _now_utc()

    level_emoji = {
        "ACTION":  "🔴",
        "WARNING": "🟡",
        "INFO":    "🟢",
    }.get(alert.level, "⚪")

    # ── 共用 header ──────────────────────────────────────────────────
    header = (
        f"{level_emoji} <b>{alert.symbol} — {alert.strategy}</b>\n"
        f"⏰ {now} | ID: {alert.position_id}\n"
    )

    # ── 價格細節（若有傳入 price_data）──────────────────────────────
    price_line = ""
    if price_data:
        stock_price  = price_data.get("stock_price", 0)
        distance_pct = price_data.get("distance_pct", 0)
        dte          = price_data.get("dte", 0)
        price_line = (
            f"現價: <b>${stock_price:.2f}</b> | "
            f"距 Strike: <b>{distance_pct:.1f}%</b> | "
            f"DTE: <b>{dte}天</b>\n"
        )

    # ── 各類型獨立格式 ───────────────────────────────────────────────
    if alert.alert_type == "TAKE_PROFIT":
        body = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>獲利達標，建議平倉</b>\n"
            f"{price_line}"
            f"{alert.message}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 {alert.action}"
        )

    elif alert.alert_type == "STOP_LOSS":
        body = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🛑 <b>停損觸發，立刻處理</b>\n"
            f"{price_line}"
            f"{alert.message}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 {alert.action}"
        )

    elif alert.alert_type == "DTE_WARNING":
        body = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ <b>期權快到期</b>\n"
            f"{price_line}"
            f"{alert.message}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 {alert.action}"
        )

    elif alert.alert_type == "ASSIGNMENT_RISK":
        body = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>Assignment 風險警告</b>\n"
            f"{price_line}"
            f"{alert.message}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 {alert.action}"
        )

    elif alert.alert_type == "IC_BREACH":
        body = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ <b>Iron Condor 翼突破</b>\n"
            f"{price_line}"
            f"{alert.message}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 {alert.action}"
        )

    else:
        body = (
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"{alert.message}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👉 {alert.action}"
        )

    return header + body


def send_alerts(alerts: List[Alert],
                price_data_map: dict[str, dict] | None = None) -> None:
    """
    批量發送 Alert 通知。
    - ACTION 等級優先發送
    - 每則獨立發送，格式清晰不混雜
    - price_data_map: { position_id → price_data }，用於顯示現價細節
    """
    if not alerts:
        return

    sorted_alerts = sorted(alerts, key=lambda a: (0 if a.level == "ACTION" else 1))

    for alert in sorted_alerts:
        price_data = (price_data_map or {}).get(str(alert.position_id))
        msg = format_alert(alert, price_data)
        send_message(msg, notify=True)


def send_daily_summary(positions_data: list, total_pnl: float,
                       initial_capital: float) -> None:
    """發送每日收盤總結 → 通知頻道"""
    now = datetime.now(timezone.utc)
    date_str    = now.strftime("%Y-%m-%d")
    weekday_str = _weekday_zh(now)
    time_str    = now.strftime("%H:%M UTC")

    total_pnl_pct = total_pnl / initial_capital * 100
    pnl_emoji     = "📈" if total_pnl >= 0 else "📉"

    header = (
        f"📊 <b>每日收盤總結</b>\n"
        f"交易日：{date_str}（{weekday_str}）\n"
        f"結算時間：{time_str}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} <b>帳戶總 P&L：${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)</b>\n"
        f"💰 初始資金：${initial_capital:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
    )

    rows = []
    for p in positions_data:
        pos      = p["position"]
        prices   = p["prices"]
        symbol   = pos["SYMBOL"]
        strategy = pos["STRATEGY"]
        pnl_usd  = prices["pnl_usd"]
        pnl_pct  = prices["pnl_pct"]
        dte      = prices["dte"]

        # 📈 獲利 / 📉 虧損
        emoji = "📈" if pnl_usd >= 0 else "📉"
        rows.append(
            f"{emoji} <b>{symbol}</b> [{strategy}]\n"
            f"   P&L: <b>${pnl_usd:+,.0f} ({pnl_pct:+.1f}%)</b> | "
            f"DTE: {dte}天 | 現價: ${prices['stock_price']:.2f}"
        )

    body = "\n".join(rows) if rows else "📭 目前無開放持倉"

    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 系統監控中，異常將立即通知"
    )

    send_message(header + body + footer, notify=True)


def send_startup_message(position_count: int) -> None:
    """發送系統啟動訊息 → 通知頻道"""
    send_message(
        f"🤖 <b>期權監控系統啟動</b>\n"
        f"⏰ {_now_utc()}\n"
        f"正在監控 {position_count} 個持倉...",
        notify=True,
    )


def send_error_message(error: str) -> None:
    """發送錯誤通知 → 通知頻道"""
    send_message(
        f"⚠️ <b>監控系統錯誤</b>\n"
        f"⏰ {_now_utc()}\n"
        f"{error}",
        notify=True,
    )
