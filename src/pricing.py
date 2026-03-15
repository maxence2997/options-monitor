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

    # 找最接近的到期日
    target = datetime.strptime(expiry_str, "%Y-%m-%d").date()
    best_expiry = min(
        available,
        key=lambda d: abs((datetime.strptime(d, "%Y-%m-%d").date() - target).days)
    )

    chain = ticker.option_chain(best_expiry)
    df = chain.calls if option_type.lower() == "call" else chain.puts
    df = df.copy()

    # yfinance 1.x: strike 欄位名稱不變
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
    計算單一持倉的即時數據
    回傳：stock_price, premium_current, pnl_usd, pnl_pct, distance_pct, dte
    """
    symbol           = position["SYMBOL"]
    strategy         = position["STRATEGY"].upper()
    expiry           = str(position["EXPIRY"])
    contracts        = int(position.get("CONTRACTS", 1))
    strike_sell      = float(position["STRIKE_SELL"])
    strike_buy       = float(position.get("STRIKE_BUY") or 0)
    premium_received = float(position["PREMIUM_RECEIVED"])

    stock_price = get_stock_price(symbol)
    dte         = calc_dte(expiry)

    if strategy == "WHEEL_CSP":
        premium_current = get_option_price(symbol, expiry, strike_sell, "put")
        pnl_per_share   = premium_received - premium_current
        distance_pct    = (stock_price - strike_sell) / stock_price * 100

    elif strategy == "WHEEL_CC":
        premium_current = get_option_price(symbol, expiry, strike_sell, "call")
        pnl_per_share   = premium_received - premium_current
        distance_pct    = (strike_sell - stock_price) / stock_price * 100

    elif strategy == "IRON_CONDOR":
        put_current     = get_spread_price(symbol, expiry, strike_sell, strike_buy, "put")
        premium_current = put_current
        pnl_per_share   = premium_received - premium_current
        distance_pct    = (stock_price - strike_sell) / stock_price * 100

    elif strategy == "BULL_CALL_SPREAD":
        spread_current  = get_spread_price(symbol, expiry, strike_sell, strike_buy, "call")
        premium_current = spread_current
        pnl_per_share   = premium_current - abs(premium_received)
        distance_pct    = (stock_price - strike_sell) / stock_price * 100

    elif strategy == "HEDGE_PUT":
        premium_current = get_option_price(symbol, expiry, strike_sell, "put")
        pnl_per_share   = premium_current - abs(premium_received)
        distance_pct    = (strike_sell - stock_price) / stock_price * 100

    else:
        premium_current = 0.0
        pnl_per_share   = 0.0
        distance_pct    = 0.0

    pnl_usd = pnl_per_share * 100 * contracts
    pnl_pct = (pnl_per_share / abs(premium_received) * 100) if premium_received != 0 else 0.0

    return {
        "stock_price":     stock_price,
        "premium_current": premium_current,
        "pnl_usd":         pnl_usd,
        "pnl_pct":         pnl_pct,
        "distance_pct":    distance_pct,
        "dte":             dte,
    }
