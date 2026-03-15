"""
從 GitHub Gist 讀取持倉資料（取代 Google Sheets）
"""
import json
import os
import requests
from datetime import datetime


def load_positions() -> list[dict]:
    """從 Gist 讀取所有 OPEN 持倉"""
    gist_id    = os.environ["GIST_ID"]
    gist_token = os.environ["GIST_TOKEN"]

    resp = requests.get(
        f"https://api.github.com/gists/{gist_id}",
        headers={
            "Authorization": f"Bearer {gist_token}",
            "Accept": "application/vnd.github+json",
        },
        timeout=10,
    )
    resp.raise_for_status()

    files = resp.json().get("files", {})
    content = files.get("positions.json", {}).get("content", "")

    if not content:
        return []

    store = json.loads(content)
    positions = store.get("positions", [])
    return [p for p in positions if p.get("status") == "OPEN"]


def save_positions(positions_update: list[dict]) -> None:
    """
    將更新後的 price data 回寫到 Gist
    只更新 premium_current / pnl_usd / pnl_pct / stock_price / distance_pct / dte / last_updated
    （不覆蓋使用者輸入的欄位）
    """
    gist_id    = os.environ["GIST_ID"]
    gist_token = os.environ["GIST_TOKEN"]
    headers = {
        "Authorization": f"Bearer {gist_token}",
        "Accept": "application/vnd.github+json",
    }

    # 先讀取完整 store
    resp = requests.get(f"https://api.github.com/gists/{gist_id}", headers=headers, timeout=10)
    resp.raise_for_status()
    files = resp.json().get("files", {})
    content = files.get("positions.json", {}).get("content", "{}")
    store = json.loads(content)

    # 建立 id → price_data 的 mapping
    update_map = {p["id"]: p for p in positions_update}

    for pos in store.get("positions", []):
        if pos["id"] in update_map:
            data = update_map[pos["id"]]
            pos["premium_current"] = data.get("premium_current")
            pos["pnl_usd"]         = data.get("pnl_usd")
            pos["pnl_pct"]         = data.get("pnl_pct")
            pos["stock_price"]     = data.get("stock_price")
            pos["distance_pct"]    = data.get("distance_pct")
            pos["dte"]             = data.get("dte")
            pos["last_updated"]    = datetime.now().strftime("%Y-%m-%d %H:%M")

    store["last_update"] = datetime.now().isoformat()

    # 回寫 Gist
    requests.patch(
        f"https://api.github.com/gists/{gist_id}",
        headers=headers,
        json={"files": {"positions.json": {"content": json.dumps(store, indent=2)}}},
        timeout=10,
    ).raise_for_status()
