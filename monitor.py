import os
import time
import json
import math
import requests
from datetime import datetime, timezone

BINANCE_FAPI = "https://fapi.binance.com"
BINANCE_FUTURES_DATA = "https://fapi.binance.com/futures/data"
COINGECKO = "https://api.coingecko.com/api/v3"

RATIO_LOW = float(os.getenv("RATIO_LOW", "0.98"))
RATIO_HIGH = float(os.getenv("RATIO_HIGH", "1.02"))
MIN_MCAP = float(os.getenv("MIN_MCAP", "5000000"))
MIN_OI = float(os.getenv("MIN_OI", "5000000"))
PRICE_DIFF_PCT = float(os.getenv("PRICE_DIFF_PCT", "8"))
MAX_SYMBOLS = int(os.getenv("MAX_SYMBOLS", "0"))
SLEEP_SEC = float(os.getenv("SLEEP_SEC", "0.05"))
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "60"))

TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TG_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

STATE_FILE = "state.json"

def http_get(url, params=None, timeout=15):
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def tg_send(text: str):
    if not TG_TOKEN or not TG_CHAT_ID:
        raise RuntimeError("缺少 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    data = {"chat_id": TG_CHAT_ID, "text": text}
    r = requests.post(url, data=data, timeout=15)
    r.raise_for_status()
    js = r.json()
    if not js.get("ok"):
        raise RuntimeError(f"Telegram发送失败: {js}")

def get_usdt_perp_symbols():
    info = http_get(f"{BINANCE_FAPI}/fapi/v1/exchangeInfo")
    syms = []
    for s in info.get("symbols", []):
        if s.get("contractType") == "PERPETUAL" and s.get("quoteAsset") == "USDT" and s.get("status") == "TRADING":
            syms.append(s["symbol"])
    return syms

def main():
    symbols = get_usdt_perp_symbols()
    state = load_state()
    now = int(time.time())
    hits = []

    for sym in symbols:
        time.sleep(SLEEP_SEC)
        oi_data = http_get(f"{BINANCE_FUTURES_DATA}/openInterestHist", {"symbol": sym, "period": "5m", "limit": 1})
        if not oi_data:
            continue
        oi = float(oi_data[0].get("sumOpenInterestValue", 0))
        if oi < MIN_OI:
            continue
        ratio = oi / MIN_MCAP
        if RATIO_LOW <= ratio <= RATIO_HIGH:
            last = state.get(sym, 0)
            if now - last > COOLDOWN_MINUTES * 60:
                hits.append(f"{sym} OI=${oi/1e6:.2f}M 比例={ratio:.2f}")
                state[sym] = now

    if hits:
        msg = "⚠️ OI≈市值 触发提醒\n" + "\n".join(hits)
        tg_send(msg)
        save_state(state)

if __name__ == "__main__":
    main()
