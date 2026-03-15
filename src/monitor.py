"""
期權監控主程式
執行方式：python monitor.py [--mode daily|intraday]
"""
import sys
import os
import argparse
import traceback
from datetime import datetime

# 加入 src 路徑
sys.path.insert(0, os.path.dirname(__file__))

from sheets   import get_open_positions, get_settings, update_position_prices, append_log
from pricing  import get_position_current_value
from strategy import check_position, check_iron_condor_breach
from notifier import (send_alerts, send_daily_summary, send_startup_message,
                       send_error_message)


def run_monitor(mode: str = "intraday"):
    """
    主監控邏輯
    mode:
        'intraday' - 盤中每小時執行，只發 ACTION/WARNING 通知
        'daily'    - 收盤後執行，發完整每日總結 + 所有通知
    """
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 開始執行監控 (mode={mode})")
    
    # 1. 讀取持倉
    positions = get_open_positions()
    print(f"找到 {len(positions)} 個 OPEN 持倉")
    
    if not positions:
        if mode == "daily":
            from notifier import send_message
            send_message("📊 <b>每日收盤總結</b>\n目前無開放持倉")
        return
    
    if mode == "daily":
        send_startup_message(len(positions))
    
    # 2. 取得設定
    settings = get_settings()
    initial_capital = float(settings.get("INITIAL_CAPITAL", 1_000_000))
    
    # 3. 逐筆處理持倉
    all_alerts  = []
    positions_data = []
    total_pnl   = 0.0
    
    for pos in positions:
        symbol   = pos["SYMBOL"]
        strategy = pos["STRATEGY"]
        pos_id   = pos.get("ID", "?")
        
        try:
            print(f"  處理 [{pos_id}] {symbol} {strategy}...")
            
            # 取得即時價格
            prices = get_position_current_value(pos)
            total_pnl += prices["pnl_usd"]
            
            # 更新 Google Sheet
            update_position_prices(
                row_num         = pos["_row"],
                premium_current = prices["premium_current"],
                pnl_usd         = prices["pnl_usd"],
                pnl_pct         = prices["pnl_pct"],
                stock_price     = prices["stock_price"],
                distance_pct    = prices["distance_pct"],
                dte             = prices["dte"],
            )
            
            # 檢查策略規則
            alerts = check_position(pos, prices)
            
            # 額外檢查 Iron Condor 突破
            ic_alert = check_iron_condor_breach(pos, prices)
            if ic_alert:
                alerts.append(ic_alert)
            
            all_alerts.extend(alerts)
            positions_data.append({"position": pos, "prices": prices})
            
            # 記錄 Log
            for alert in alerts:
                append_log(alert.alert_type, symbol, strategy, alert.message[:200])
            
            print(f"    P&L: ${prices['pnl_usd']:+,.0f} ({prices['pnl_pct']:+.1f}%), "
                  f"DTE={prices['dte']}, Alerts={len(alerts)}")
        
        except Exception as e:
            err_msg = f"處理 [{pos_id}] {symbol} {strategy} 時發生錯誤: {e}"
            print(f"  ❌ {err_msg}")
            traceback.print_exc()
            append_log("ERROR", symbol, strategy, err_msg[:200])
    
    # 4. 發送通知
    if all_alerts:
        print(f"發送 {len(all_alerts)} 個通知...")
        send_alerts(all_alerts)
    
    if mode == "daily":
        send_daily_summary(positions_data, total_pnl, initial_capital)
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 監控完成，總 P&L: ${total_pnl:+,.0f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="期權監控系統")
    parser.add_argument(
        "--mode",
        choices=["daily", "intraday"],
        default="intraday",
        help="執行模式：daily=每日收盤總結，intraday=盤中即時監控"
    )
    args = parser.parse_args()
    
    try:
        run_monitor(mode=args.mode)
    except Exception as e:
        err = f"監控系統崩潰：{e}\n{traceback.format_exc()}"
        print(f"❌ {err}")
        send_error_message(err[:500])
        sys.exit(1)
