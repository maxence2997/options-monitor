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
from datetime import datetime
from typing import List
from strategy import Alert


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


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
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
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


def format_alert(alert: Alert) -> str:
    """將單一 Alert 格式化成 Telegram 訊息"""
    level_emoji = {
        "ACTION":  "🔴",
        "WARNING": "🟡",
        "INFO":    "🟢",
    }.get(alert.level, "⚪")

    return (
        f"{level_emoji} <b>[{alert.alert_type}] {alert.symbol} - {alert.strategy}</b>\n"
        f"{alert.message}\n"
        f"<b>👉 建議操作：</b>{alert.action}"
    )


def send_alerts(alerts: List[Alert]) -> None:
    """
    批量發送 Alert 通知（ACTION 優先，每個獨立發送）。
    cron 觸發的通知 → 發到通知頻道（notify=True）
    """
    if not alerts:
        return

    sorted_alerts = sorted(alerts, key=lambda a: (0 if a.level == "ACTION" else 1))

    for alert in sorted_alerts:
        msg = format_alert(alert)
        send_message(msg, notify=True)


def send_daily_summary(positions_data: list, total_pnl: float,
                       initial_capital: float) -> None:
    """發送每日收盤總結 → 通知頻道"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    total_pnl_pct = total_pnl / initial_capital * 100
    pnl_emoji = "📈" if total_pnl >= 0 else "📉"

    header = (
        f"📊 <b>每日收盤總結</b> {now}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{pnl_emoji} <b>帳戶總 P&L：${total_pnl:+,.2f} ({total_pnl_pct:+.2f}%)</b>\n"
        f"💰 初始資金：$1,000,000\n"
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

        emoji = "✅" if pnl_usd >= 0 else "❌"
        rows.append(
            f"{emoji} <b>{symbol}</b> [{strategy}]\n"
            f"   P&L: ${pnl_usd:+,.0f} ({pnl_pct:+.1f}%) | DTE: {dte}天 | "
            f"現價: ${prices['stock_price']:.2f}"
        )

    body   = "\n".join(rows) if rows else "（目前無開放持倉）"
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 系統自動監控中，有異常會立即通知"
    )

    send_message(header + body + footer, notify=True)


def send_startup_message(position_count: int) -> None:
    """發送系統啟動訊息 → 通知頻道"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    send_message(
        f"🤖 <b>期權監控系統啟動</b> {now}\n"
        f"正在監控 {position_count} 個持倉...",
        notify=True,
    )


def send_error_message(error: str) -> None:
    """發送錯誤通知 → 通知頻道（錯誤不管哪個頻道都要看到）"""
    send_message(f"⚠️ <b>監控系統錯誤</b>\n{error}", notify=True)
