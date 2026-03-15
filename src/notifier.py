"""
Telegram 通知模組
負責格式化並發送各類通知
"""
import requests
import os
from datetime import datetime
from typing import List
from strategy import Alert


TELEGRAM_API = "https://api.telegram.org/bot{token}/sendMessage"


def send_message(text: str, parse_mode: str = "HTML") -> bool:
    """發送 Telegram 訊息"""
    token   = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
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
        print(f"[Telegram] 訊息發送成功")
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
    """批量發送 Alert 通知（ACTION 優先，每個獨立發送）"""
    if not alerts:
        return
    
    # ACTION 等級優先發送
    sorted_alerts = sorted(alerts, key=lambda a: (0 if a.level == "ACTION" else 1))
    
    for alert in sorted_alerts:
        msg = format_alert(alert)
        send_message(msg)


def send_daily_summary(positions_data: list, total_pnl: float,
                       initial_capital: float) -> None:
    """發送每日收盤總結"""
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
        pos    = p["position"]
        prices = p["prices"]
        strategy = pos["STRATEGY"]
        symbol   = pos["SYMBOL"]
        pnl_usd  = prices["pnl_usd"]
        pnl_pct  = prices["pnl_pct"]
        dte      = prices["dte"]
        
        emoji = "✅" if pnl_usd >= 0 else "❌"
        rows.append(
            f"{emoji} <b>{symbol}</b> [{strategy}]\n"
            f"   P&L: ${pnl_usd:+,.0f} ({pnl_pct:+.1f}%) | DTE: {dte}天 | "
            f"現價: ${prices['stock_price']:.2f}"
        )
    
    body = "\n".join(rows) if rows else "（目前無開放持倉）"
    
    footer = (
        f"\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 系統自動監控中，有異常會立即通知"
    )
    
    send_message(header + body + footer)


def send_startup_message(position_count: int) -> None:
    """發送系統啟動訊息"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    send_message(
        f"🤖 <b>期權監控系統啟動</b> {now}\n"
        f"正在監控 {position_count} 個持倉..."
    )


def send_error_message(error: str) -> None:
    """發送錯誤通知"""
    send_message(f"⚠️ <b>監控系統錯誤</b>\n{error}")
