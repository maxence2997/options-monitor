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
from strategy   import get_strategy
from notifier   import (send_alerts, send_daily_summary,
                        send_error_message,
                        send_message, _now_utc, _weekday_zh)


def _build_pricing_input(pos: dict) -> dict:
    """
    從 Gist 的持倉 dict 組裝 pricing.get_position_current_value 需要的 dict。
    IC 使用新的六個專用欄位；其他策略使用原有欄位。
    """
    strategy = pos["strategy"].upper()
    base = {
        "SYMBOL":    pos["symbol"],
        "STRATEGY":  strategy,
        "EXPIRY":    pos["expiry"],
        "CONTRACTS": pos["contracts"],
    }

    if strategy == "IRON_CONDOR":
        base.update({
            "SHORT_PUT_STRIKE":  pos["short_put_strike"],
            "LONG_PUT_STRIKE":   pos["long_put_strike"],
            "SHORT_PUT_PREMIUM":       pos["short_put_premium"],
            "LONG_PUT_PREMIUM":  pos.get("long_put_premium", 0),
            "SHORT_CALL_STRIKE": pos["short_call_strike"],
            "LONG_CALL_STRIKE":  pos["long_call_strike"],
            "SHORT_CALL_PREMIUM":      pos["short_call_premium"],
            "LONG_CALL_PREMIUM": pos.get("long_call_premium", 0),
        })
    else:
        base.update({
            "STRIKE_SELL":      pos["strike_sell"],
            "STRIKE_BUY":       pos.get("strike_buy", 0),
            "PREMIUM_RECEIVED": pos["premium_received"],
        })

    return base


def _build_sheet_pos(pos: dict) -> dict:
    """
    組裝傳給 strategy.check() 的 sheet_pos dict。
    IC 補上六個新欄位，供 iron_condor.py 的 breach 判斷使用。
    """
    strategy = pos["strategy"].upper()
    sheet = {
        "SYMBOL":            pos["symbol"],
        "STRATEGY":          strategy,
        "PROFIT_TARGET_PCT": pos.get("profit_target_pct", 50),
        "LOSS_LIMIT_PCT":    pos.get("loss_limit_pct", 200),
        "NOTES":             pos.get("notes", ""),
        "ID":                pos.get("id", "?"),
        "CONTRACTS":         pos["contracts"],
    }

    if strategy == "IRON_CONDOR":
        sheet.update({
            "SHORT_PUT_STRIKE":  pos["short_put_strike"],
            "LONG_PUT_STRIKE":   pos["long_put_strike"],
            "SHORT_PUT_PREMIUM":       pos["short_put_premium"],
            "LONG_PUT_PREMIUM":  pos.get("long_put_premium", 0),
            "SHORT_CALL_STRIKE": pos["short_call_strike"],
            "LONG_CALL_STRIKE":  pos["long_call_strike"],
            "SHORT_CALL_PREMIUM":      pos["short_call_premium"],
            "LONG_CALL_PREMIUM": pos.get("long_call_premium", 0),
            "STRIKE_SELL":       pos["short_put_strike"],
        })
    else:
        sheet.update({
            "STRIKE_SELL": pos["strike_sell"],
            "STRIKE_BUY":  pos.get("strike_buy", 0),
        })

    return sheet


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

            prices    = get_position_current_value(_build_pricing_input(pos))
            sheet_pos = _build_sheet_pos(pos)

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

            alerts = get_strategy(strategy).check(sheet_pos, prices)
            all_alerts.extend(alerts)
            positions_data.append({"position": sheet_pos, "prices": prices})

            print(f"    P&L: ${prices['pnl_usd']:+,.0f} ({prices['pnl_pct']:+.1f}%), "
                  f"DTE={prices['dte']}, Alerts={len(alerts)}")

        except ValueError as e:
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
