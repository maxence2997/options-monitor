"""
期權監控主程式（Gist 版）
執行方式：python monitor.py [--mode daily|intraday]
"""
import sys
import os
import argparse
import traceback
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

from gist_store import load_positions, save_positions
from pricing    import get_position_current_value
from strategy   import check_position, check_iron_condor_breach
from notifier   import (send_alerts, send_daily_summary,
                        send_startup_message, send_error_message)


def run_monitor(mode: str = "intraday"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 開始執行監控 (mode={mode})")

    positions = load_positions()
    print(f"找到 {len(positions)} 個 OPEN 持倉")

    if not positions:
        if mode == "daily":
            from notifier import send_message
            send_message("📊 <b>每日收盤總結</b>\n目前無開放持倉")
        return

    if mode == "daily":
        send_startup_message(len(positions))

    initial_capital = float(os.environ.get("INITIAL_CAPITAL", 1_000_000))

    all_alerts      = []
    positions_data  = []
    price_updates   = []
    total_pnl       = 0.0

    for pos in positions:
        symbol   = pos["symbol"]
        strategy = pos["strategy"]
        pos_id   = pos.get("id", "?")

        try:
            print(f"  處理 [{pos_id}] {symbol} {strategy}...")

            prices = get_position_current_value({
                "SYMBOL":           symbol,
                "STRATEGY":         strategy,
                "EXPIRY":           pos["expiry"],
                "CONTRACTS":        pos["contracts"],
                "STRIKE_SELL":      pos["strike_sell"],
                "STRIKE_BUY":       pos.get("strike_buy", 0),
                "PREMIUM_RECEIVED": pos["premium_received"],
            })

            total_pnl += prices["pnl_usd"]

            price_updates.append({
                "id":              pos_id,
                "premium_current": prices["premium_current"],
                "pnl_usd":         prices["pnl_usd"],
                "pnl_pct":         prices["pnl_pct"],
                "stock_price":     prices["stock_price"],
                "distance_pct":    prices["distance_pct"],
                "dte":             prices["dte"],
            })

            sheet_pos = {
                "SYMBOL":            symbol,
                "STRATEGY":          strategy,
                "PROFIT_TARGET_PCT": pos.get("profit_target_pct", 50),
                "LOSS_LIMIT_PCT":    pos.get("loss_limit_pct", 200),
                "NOTES":             pos.get("notes", ""),
                "ID":                pos_id,
                "CONTRACTS":         pos["contracts"],
                "STRIKE_SELL":       pos["strike_sell"],
            }

            alerts = check_position(sheet_pos, prices)
            ic_alert = check_iron_condor_breach(sheet_pos, prices)
            if ic_alert:
                alerts.append(ic_alert)

            all_alerts.extend(alerts)
            positions_data.append({"position": sheet_pos, "prices": prices})

            print(f"    P&L: ${prices['pnl_usd']:+,.0f} ({prices['pnl_pct']:+.1f}%), "
                  f"DTE={prices['dte']}, Alerts={len(alerts)}")

        except Exception as e:
            err_msg = f"處理 [{pos_id}] {symbol} {strategy} 時發生錯誤: {e}"
            print(f"  ❌ {err_msg}")
            traceback.print_exc()

    if price_updates:
        try:
            save_positions(price_updates)
            print(f"已回寫 {len(price_updates)} 筆價格更新到 Gist")
        except Exception as e:
            print(f"⚠️  Gist 回寫失敗：{e}")

    if all_alerts:
        print(f"發送 {len(all_alerts)} 個通知...")
        send_alerts(all_alerts)

    if mode == "daily":
        send_daily_summary(positions_data, total_pnl, initial_capital)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] 監控完成，總 P&L: ${total_pnl:+,.0f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="期權監控系統")
    parser.add_argument("--mode", choices=["daily", "intraday"],
                        default="intraday")
    args = parser.parse_args()

    try:
        run_monitor(mode=args.mode)
    except Exception as e:
        err = f"監控系統崩潰：{e}\n{traceback.format_exc()}"
        print(f"❌ {err}")
        send_error_message(err[:500])
        sys.exit(1)
