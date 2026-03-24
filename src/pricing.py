"""
期權定價模組
使用 yfinance 1.x 抓取股價與期權 premium 即時數據
"""
import yfinance as yf
from datetime import datetime, date


def get_stock_price(symbol: str) -> float:
    """取得股票現價"""
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="1d", interval="1m")
    if hist.empty:
        hist = ticker.history(period="2d")
        if hist.empty:
            raise ValueError(f"無法取得 {symbol} 的價格")
    return float(hist["Close"].iloc[-1])


def get_option_price(symbol: str, expiry_str: str, strike: float,
                     option_type: str) -> float:
    """
    取得期權的 mid price（bid/ask 中間價）
    option_type: 'call' 或 'put'
    expiry_str:  'YYYY-MM-DD'
    """
    ticker = yf.Ticker(symbol)

    available = ticker.options
    if not available:
        raise ValueError(f"無法取得 {symbol} 的期權資料")

    target = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    best_expiry = min(
        available,
        key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date() - target).days)
    )

    chain = ticker.option_chain(best_expiry)
    df = chain.calls if option_type.lower() == "call" else chain.puts
    df = df.copy()

    df["strike_diff"] = abs(df["strike"] - strike)
    row = df.nsmallest(1, "strike_diff").iloc[0]

    bid  = float(row.get("bid", 0) or 0)
    ask  = float(row.get("ask", 0) or 0)
    last = float(row.get("lastPrice", 0) or 0)

    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    elif last > 0:
        return last
    else:
        return 0.0


def get_spread_price(symbol: str, expiry_str: str,
                     strike_sell: float, strike_buy: float,
                     option_type: str) -> float:
    """
    取得 Spread 現值 = 賣出腳現價 - 買入腳現價
    （對賣方：這是平倉需要花的錢）
    """
    sell_price = get_option_price(symbol, expiry_str, strike_sell, option_type)
    buy_price  = get_option_price(symbol, expiry_str, strike_buy,  option_type)
    return sell_price - buy_price


def calc_dte(expiry_str: str) -> int:
    """計算距到期日的天數"""
    expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    today  = date.today()
    return max(0, (expiry - today).days)


def get_position_current_value(position: dict) -> dict:
    """
    計算單一持倉的即時數據。
    回傳：stock_price, premium_current, pnl_usd, pnl_pct, distance_pct, dte

    所有策略統一使用 short/long + put/call + strike 命名：
      WHEEL_CSP:  short_put_strike
      WHEEL_CC:   short_call_strike
      IC:         short_put_strike, long_put_strike, short_call_strike, long_call_strike
      BCS:        long_call_strike, short_call_strike
      HEDGE_PUT:  long_put_strike
    """
    symbol    = position["SYMBOL"]
    strategy  = position["STRATEGY"].upper()
    expiry    = str(position["EXPIRY"])
    contracts = int(position.get("CONTRACTS", 1))

    stock_price = get_stock_price(symbol)
    dte         = calc_dte(expiry)

    # ── Iron Condor（Put Spread + Call Spread 分開計算）──────────────
    if strategy == "IRON_CONDOR":
        short_put_strike  = float(position["SHORT_PUT_STRIKE"])
        long_put_strike   = float(position["LONG_PUT_STRIKE"])
        short_put_premium       = float(position["SHORT_PUT_PREMIUM"])
        long_put_premium  = float(position.get("LONG_PUT_PREMIUM", 0))
        short_call_strike = float(position["SHORT_CALL_STRIKE"])
        long_call_strike  = float(position["LONG_CALL_STRIKE"])
        short_call_premium      = float(position["SHORT_CALL_PREMIUM"])
        long_call_premium = float(position.get("LONG_CALL_PREMIUM", 0))

        # Net premium = 賣出收入 - 買入成本（才是真實基準）
        put_net_premium   = short_put_premium - long_put_premium
        call_net_premium  = short_call_premium - long_call_premium
        total_net_premium = put_net_premium + call_net_premium

        # 現在平倉需要花的錢（兩側加總）
        put_spread_current  = get_spread_price(symbol, expiry,
                                               short_put_strike, long_put_strike, "put")
        call_spread_current = get_spread_price(symbol, expiry,
                                               short_call_strike, long_call_strike, "call")
        # 現在平倉需要花的錢（兩側 net 加總）
        current_cost = put_spread_current + call_spread_current
        premium_current = current_cost

        pnl_per_share = total_net_premium - current_cost

        put_distance  = (stock_price - short_put_strike) / stock_price * 100
        call_distance = (short_call_strike - stock_price) / stock_price * 100
        distance_pct  = min(put_distance, call_distance)

        pnl_usd = pnl_per_share * 100 * contracts
        pnl_pct = (pnl_per_share / total_net_premium * 100) \
                  if total_net_premium != 0 else 0.0

        return {
            "stock_price":     stock_price,
            "premium_current": premium_current,
            "pnl_usd":         pnl_usd,
            "pnl_pct":         pnl_pct,
            "distance_pct":    distance_pct,
            "dte":             dte,
            # IC 額外回傳兩側各自現值，供 iron_condor.py breach 判斷用
            "put_spread_current":  put_spread_current,
            "call_spread_current": call_spread_current,
        }

    # ── 其他策略 ─────────────────────────────────────────────────────────
    premium_received = float(position["PREMIUM_RECEIVED"])

    if strategy == "WHEEL_CSP":
        short_put_strike = float(position["SHORT_PUT_STRIKE"])
        premium_current  = get_option_price(symbol, expiry, short_put_strike, "put")
        pnl_per_share    = premium_received - premium_current
        distance_pct     = (stock_price - short_put_strike) / stock_price * 100

    elif strategy == "WHEEL_CC":
        short_call_strike = float(position["SHORT_CALL_STRIKE"])
        premium_current   = get_option_price(symbol, expiry, short_call_strike, "call")
        pnl_per_share     = premium_received - premium_current
        distance_pct      = (short_call_strike - stock_price) / stock_price * 100

    elif strategy == "BULL_CALL_SPREAD":
        # long_call_strike = 你買入的 ATM Call（低 Strike）
        # short_call_strike = 你賣出的 OTM Call（高 Strike）
        buy_strike  = float(position["LONG_CALL_STRIKE"])
        sell_strike = float(position["SHORT_CALL_STRIKE"])

        spread_current  = get_spread_price(symbol, expiry, buy_strike, sell_strike, "call")
        premium_current = spread_current
        pnl_per_share   = premium_current - abs(premium_received)
        distance_pct    = (stock_price - buy_strike) / stock_price * 100

    elif strategy == "HEDGE_PUT":
        # long_put_strike = 你買入的 OTM Put Strike（現價 × 85%）
        long_put_strike = float(position["LONG_PUT_STRIKE"])

        premium_current = get_option_price(symbol, expiry, long_put_strike, "put")
        pnl_per_share   = premium_current - abs(premium_received)
        distance_pct    = (long_put_strike - stock_price) / stock_price * 100

    else:
        premium_current = 0.0
        pnl_per_share   = 0.0
        distance_pct    = 0.0

    pnl_usd = pnl_per_share * 100 * contracts
    pnl_pct = (pnl_per_share / abs(premium_received) * 100) \
              if premium_received != 0 else 0.0

    return {
        "stock_price":     stock_price,
        "premium_current": premium_current,
        "pnl_usd":         pnl_usd,
        "pnl_pct":         pnl_pct,
        "distance_pct":    distance_pct,
        "dte":             dte,
    }
