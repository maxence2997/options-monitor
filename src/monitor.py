"""
期權監控主程式（Gist 版）
執行方式：python monitor.py [--mode daily|intraday]
"""
import sys
import os
import argparse
import traceback
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from config     import INITIAL_CAPITAL
from gist_store import load_positions, save_positions
from pricing    import get_position_current_value
from strategy   import get_strategy                          # ← 唯一改動的 import
from notifier   import (send_alerts, send_daily_summary,
                        send_startup_message, send_error_message,
                        send_message, _now_utc, _weekday_zh)


def run_monitor(mode: str = "intraday"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 開始執行監控 (mode={mode})")

    positions = load_positions()
    print(f"找到 {len(positions)} 個 OPEN 持倉")

    if not positions:
        if mode == "daily":
            now = datetime.now(timezone.utc)
            send_message(
                f"📊 <b>每日收盤總結</b>\n"
                f"交易日：{now.strftime('%Y-%m-%d')}（{_weekday_zh(now)}）\n"
                f"結算時間：{now.strftime('%H:%M UTC')}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📭 目前無開放持倉",
                notify=True,
            )
        return

    if mode == "daily":
        send_startup_message(len(positions))

    all_alerts     = []
    positions_data = []
    price_updates  = []
    price_data_map = {}
    total_pnl      = 0.0

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

            price_data_map[str(pos_id)] = prices

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

            # ── 每個策略自己知道自己的規則 ──────────────────────────
            alerts = get_strategy(strategy).check(sheet_pos, prices)

            all_alerts.extend(alerts)
            positions_data.append({"position": sheet_pos, "prices": prices})

            print(f"    P&L: ${prices['pnl_usd']:+,.0f} ({prices['pnl_pct']:+.1f}%), "
                  f"DTE={prices['dte']}, Alerts={len(alerts)}")

        except ValueError as e:
            # 未知策略（不應發生，但優雅處理）
            print(f"  ⚠️  [{pos_id}] {symbol} {strategy}：{e}")
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
        send_alerts(all_alerts, price_data_map=price_data_map)

    if mode == "daily":
        send_daily_summary(positions_data, total_pnl, INITIAL_CAPITAL)

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
