"""
Google Sheets 操作模組
負責讀取持倉、設定，以及寫入操作日誌
"""
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Google Sheet 欄位定義（對應 Positions 工作表）
COL = {
    "ID":               1,
    "STRATEGY":         2,   # WHEEL_CSP / WHEEL_CC / IRON_CONDOR / BULL_CALL_SPREAD / HEDGE_PUT
    "SYMBOL":           3,   # SPY / QQQ / NVDA
    "STATUS":           4,   # OPEN / CLOSED / ASSIGNED
    "OPEN_DATE":        5,
    "EXPIRY":           6,
    "DTE":              7,   # 自動計算
    "CONTRACTS":        8,   # 張數
    "STRIKE_SELL":      9,   # 賣出的 Strike（主要 Strike）
    "STRIKE_BUY":       10,  # 買入的 Strike（Spread 保護腳）
    "PREMIUM_RECEIVED": 11,  # 開倉時收到的 premium（每股）
    "PREMIUM_CURRENT":  12,  # 目前 premium 市價（每股，系統自動填）
    "PNL_USD":          13,  # P&L 金額（系統自動填）
    "PNL_PCT":          14,  # P&L %（系統自動填）
    "PROFIT_TARGET_PCT":15,  # 目標獲利 %（預設 50）
    "LOSS_LIMIT_PCT":   16,  # 停損 %（預設 200）
    "STOCK_PRICE":      17,  # 標的現價（系統自動填）
    "DISTANCE_PCT":     18,  # 股價距 Strike 的距離 %（系統自動填）
    "NOTES":            19,
    "LAST_UPDATED":     20,
}

def get_client():
    """建立 Google Sheets 客戶端"""
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise ValueError("GOOGLE_CREDENTIALS_JSON 環境變數未設定")
    
    creds_dict = json.loads(creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet():
    """取得試算表物件"""
    client = get_client()
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    if not sheet_id:
        raise ValueError("GOOGLE_SHEET_ID 環境變數未設定")
    return client.open_by_key(sheet_id)


def get_open_positions():
    """讀取所有 OPEN 狀態的持倉"""
    ss = get_spreadsheet()
    ws = ss.worksheet("Positions")
    records = ws.get_all_records()
    
    positions = []
    for i, row in enumerate(records, start=2):  # start=2 因為第1行是標頭
        if str(row.get("STATUS", "")).strip().upper() == "OPEN":
            row["_row"] = i  # 記住行號，方便後續更新
            positions.append(row)
    return positions


def get_settings():
    """讀取 Settings 工作表的設定值"""
    ss = get_spreadsheet()
    ws = ss.worksheet("Settings")
    records = ws.get_all_records()
    settings = {}
    for row in records:
        key = str(row.get("KEY", "")).strip()
        val = str(row.get("VALUE", "")).strip()
        if key:
            settings[key] = val
    return settings


def update_position_prices(row_num, premium_current, pnl_usd, pnl_pct,
                            stock_price, distance_pct, dte):
    """更新持倉的即時數據欄位"""
    ss = get_spreadsheet()
    ws = ss.worksheet("Positions")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    updates = [
        (row_num, COL["PREMIUM_CURRENT"], round(premium_current, 4)),
        (row_num, COL["PNL_USD"],         round(pnl_usd, 2)),
        (row_num, COL["PNL_PCT"],         round(pnl_pct, 2)),
        (row_num, COL["STOCK_PRICE"],     round(stock_price, 2)),
        (row_num, COL["DISTANCE_PCT"],    round(distance_pct, 2)),
        (row_num, COL["DTE"],             dte),
        (row_num, COL["LAST_UPDATED"],    now),
    ]
    
    for r, c, v in updates:
        ws.update_cell(r, c, v)


def update_position_status(row_num, new_status, notes=""):
    """更新持倉狀態（例如 OPEN → ASSIGNED / CLOSED）"""
    ss = get_spreadsheet()
    ws = ss.worksheet("Positions")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    ws.update_cell(row_num, COL["STATUS"], new_status)
    if notes:
        existing = ws.cell(row_num, COL["NOTES"]).value or ""
        ws.update_cell(row_num, COL["NOTES"], f"{existing} | {now}: {notes}".strip(" |"))
    ws.update_cell(row_num, COL["LAST_UPDATED"], now)


def append_log(log_type, symbol, strategy, message):
    """在 Log 工作表新增一筆記錄"""
    ss = get_spreadsheet()
    ws = ss.worksheet("Log")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([now, log_type, symbol, strategy, message])
