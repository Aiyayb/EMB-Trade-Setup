"""
fetch_btc_data.py - ดึงข้อมูลแท่งเทียน BTC/USDT ย้อนหลังสำหรับ Backtest

แหล่งข้อมูลหลัก : OKX (Spot BTC-USDT)  - ตรงกับ exchange ที่จะเทรดจริง
แหล่งสำรอง      : Binance (Spot BTCUSDT) - ใช้เมื่อ OKX เรียกไม่ได้

Timeframe       : 15m, 1H, 4H, 1D, 1W  (เวลาทั้งหมดอิง UTC เหมือน TradingView)
ผลลัพธ์          : data/BTCUSDT_<tf>.csv  (1 ไฟล์ต่อ timeframe)

คอลัมน์ในไฟล์ CSV:
  timestamp      เวลาเปิดแท่ง (Unix ms, UTC)
  open_time_utc  เวลาเปิดแท่ง (UTC)
  open_time_bkk  เวลาเปิดแท่ง (เวลาไทย UTC+7)
  open, high, low, close
  volume_btc     ปริมาณซื้อขายหน่วย BTC
  volume_usdt    มูลค่าซื้อขายหน่วย USDT

วิธีใช้ (ต้องมี Python 3.8+ ไม่ต้องติดตั้ง library เพิ่ม):
  python fetch_btc_data.py                      # 5 ปีย้อนหลัง ทุก timeframe
  python fetch_btc_data.py --years 7            # ย้อนหลัง 7 ปี
  python fetch_btc_data.py --start 2020-01-01   # กำหนดวันเริ่มเอง
  python fetch_btc_data.py --tf 15m 1H          # เฉพาะบาง timeframe
  python fetch_btc_data.py --source binance     # บังคับใช้ Binance
"""

import argparse
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TIMEFRAMES = ["15m", "1H", "4H", "1D", "1W"]
TF_MS = {
    "15m": 15 * 60_000,
    "1H": 60 * 60_000,
    "4H": 4 * 60 * 60_000,
    "1D": 24 * 60 * 60_000,
    "1W": 7 * 24 * 60 * 60_000,
}
# OKX: 1D/1W ปกติอิงเวลาฮ่องกง (UTC+8) -> ใช้ 1Dutc / 1Wutc ให้ตรงกับ TradingView
OKX_BAR = {"15m": "15m", "1H": "1H", "4H": "4H", "1D": "1Dutc", "1W": "1Wutc"}
BINANCE_BAR = {"15m": "15m", "1H": "1h", "4H": "4h", "1D": "1d", "1W": "1w"}

UTC = timezone.utc
BKK = timezone(timedelta(hours=7))
HEADERS = {"User-Agent": "Mozilla/5.0 (btc-backtest-data-fetcher)"}


def http_get_json(url, params, retries=6):
    full = url + "?" + urllib.parse.urlencode(params)
    delay = 1.0
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(full, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (418, 429) or e.code >= 500:
                print(f"    ! HTTP {e.code} - รอ {delay:.0f}s แล้วลองใหม่ ({attempt}/{retries})")
            else:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            print(f"    ! เชื่อมต่อไม่สำเร็จ ({e}) - รอ {delay:.0f}s ({attempt}/{retries})")
        time.sleep(delay)
        delay = min(delay * 2, 30)
    raise RuntimeError(f"เรียก API ไม่สำเร็จหลังลอง {retries} ครั้ง: {full}")


# ---------------------------------------------------------------- OKX
def fetch_okx(tf, start_ms, end_ms):
    """ดึงย้อนจากปัจจุบันไปอดีต ครั้งละ 100 แท่ง (history-candles)"""
    url = "https://www.okx.com/api/v5/market/history-candles"
    rows = {}
    after = end_ms
    calls = 0
    while True:
        data = http_get_json(url, {"instId": "BTC-USDT", "bar": OKX_BAR[tf],
                                   "after": str(after), "limit": "100"})
        if data.get("code") != "0":
            if data.get("code") == "50011":  # rate limit
                time.sleep(2)
                continue
            raise RuntimeError(f"OKX error: {data}")
        batch = data.get("data", [])
        calls += 1
        if not batch:
            break
        for k in batch:
            ts = int(k[0])
            if k[8] != "1":          # แท่งที่ยังไม่ปิด -> ข้าม
                continue
            if start_ms <= ts < end_ms:
                rows[ts] = (k[1], k[2], k[3], k[4], k[5], k[7])
        oldest = min(int(k[0]) for k in batch)
        if oldest <= start_ms or oldest >= after:
            break
        after = oldest
        if calls % 50 == 0:
            print(f"    ... ถึง {ms_to_utc(oldest)[:10]}  ({len(rows):,} แท่ง)")
        time.sleep(0.11)  # จำกัด ~9 req/s (OKX อนุญาต 20 req / 2s)
    return rows


# ---------------------------------------------------------------- Binance
def fetch_binance(tf, start_ms, end_ms):
    """ดึงจากอดีตไปปัจจุบัน ครั้งละ 1000 แท่ง"""
    url = "https://api.binance.com/api/v3/klines"
    rows = {}
    cursor = start_ms
    calls = 0
    now_ms = int(time.time() * 1000)
    while cursor < end_ms:
        batch = http_get_json(url, {"symbol": "BTCUSDT", "interval": BINANCE_BAR[tf],
                                    "startTime": cursor, "endTime": end_ms - 1, "limit": 1000})
        calls += 1
        if not batch:
            break
        for k in batch:
            ts = int(k[0])
            if int(k[6]) >= now_ms:   # close_time ยังไม่ถึง -> แท่งยังไม่ปิด
                continue
            if start_ms <= ts < end_ms:
                rows[ts] = (k[1], k[2], k[3], k[4], k[5], k[7])
        newest = int(batch[-1][0])
        if newest < cursor:
            break
        cursor = newest + 1
        if calls % 20 == 0:
            print(f"    ... ถึง {ms_to_utc(newest)[:10]}  ({len(rows):,} แท่ง)")
        time.sleep(0.25)
    return rows


# ---------------------------------------------------------------- utils
def ms_to_utc(ms):
    return datetime.fromtimestamp(ms / 1000, UTC).strftime("%Y-%m-%d %H:%M:%S")


def ms_to_bkk(ms):
    return datetime.fromtimestamp(ms / 1000, BKK).strftime("%Y-%m-%d %H:%M:%S")


def align_start(tf, start_ms):
    step = TF_MS[tf]
    if tf == "1W":  # แท่งสัปดาห์เปิดวันจันทร์ 00:00 UTC (epoch 1970-01-05 เป็นวันจันทร์)
        monday0 = 4 * 24 * 3600_000
        return monday0 + -(-(start_ms - monday0) // step) * step
    return -(-start_ms // step) * step


def check_and_save(tf, rows, out_dir, source):
    ts_sorted = sorted(rows)
    step = TF_MS[tf]
    gaps = []
    for a, b in zip(ts_sorted, ts_sorted[1:]):
        if b - a != step:
            gaps.append((a, b, (b - a) // step - 1))
    bad = 0
    for ts in ts_sorted:
        o, h, l, c = map(float, rows[ts][:4])
        if not (l <= min(o, c) and h >= max(o, c) and l > 0):
            bad += 1

    path = os.path.join(out_dir, f"BTCUSDT_{tf}.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "open_time_utc", "open_time_bkk", "open", "high",
                    "low", "close", "volume_btc", "volume_usdt"])
        for ts in ts_sorted:
            o, h, l, c, vb, vq = rows[ts]
            w.writerow([ts, ms_to_utc(ts), ms_to_bkk(ts), o, h, l, c, vb, vq])

    missing = sum(g[2] for g in gaps)
    print(f"  [OK] {tf:>3}: {len(ts_sorted):,} แท่ง | {ms_to_utc(ts_sorted[0])} -> "
          f"{ms_to_utc(ts_sorted[-1])} UTC | ช่องว่าง {len(gaps)} จุด ({missing} แท่ง) | "
          f"OHLC ผิดปกติ {bad}")
    for a, b, n in gaps[:5]:
        print(f"        gap: {ms_to_utc(a)} -> {ms_to_utc(b)} (ขาด {n} แท่ง)")
    return {"timeframe": tf, "source": source, "file": os.path.basename(path),
            "bars": len(ts_sorted), "first_utc": ms_to_utc(ts_sorted[0]),
            "last_utc": ms_to_utc(ts_sorted[-1]), "gap_count": len(gaps),
            "missing_bars": missing, "bad_ohlc": bad}


def main():
    p = argparse.ArgumentParser(description="ดึงข้อมูลแท่งเทียน BTC/USDT สำหรับ Backtest")
    p.add_argument("--years", type=float, default=5)
    p.add_argument("--start", help="วันเริ่ม YYYY-MM-DD (UTC) - ใช้แทน --years")
    p.add_argument("--tf", nargs="+", default=TIMEFRAMES, choices=TIMEFRAMES)
    p.add_argument("--source", choices=["okx", "binance"], default="okx")
    p.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
    a = p.parse_args()

    now = datetime.now(UTC)
    start = (datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=UTC) if a.start
             else now - timedelta(days=round(365.25 * a.years)))
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)
    os.makedirs(a.out, exist_ok=True)

    print(f"BTC/USDT | ช่วง {start:%Y-%m-%d} -> {now:%Y-%m-%d %H:%M} UTC | แหล่งข้อมูล: {a.source.upper()}")
    print(f"บันทึกที่: {a.out}\n")

    summary = []
    for tf in a.tf:
        t0 = time.time()
        print(f"> กำลังดึง {tf} ...")
        s_ms = align_start(tf, start_ms)
        source = a.source
        try:
            rows = (fetch_okx if source == "okx" else fetch_binance)(tf, s_ms, end_ms)
            if not rows:
                raise RuntimeError("ไม่ได้ข้อมูลกลับมา")
        except Exception as e:
            if source == "okx":
                print(f"  ! OKX ล้มเหลว ({e}) -> สลับไปใช้ Binance")
                source = "binance"
                rows = fetch_binance(tf, s_ms, end_ms)
            else:
                raise
        summary.append(check_and_save(tf, rows, a.out, source))
        print(f"        ใช้เวลา {time.time() - t0:.0f}s\n")

    with open(os.path.join(a.out, "_summary.json"), "w", encoding="utf-8") as f:
        json.dump({"symbol": "BTC/USDT", "fetched_at_utc": now.strftime("%Y-%m-%d %H:%M:%S"),
                   "timezone": "UTC", "datasets": summary}, f, ensure_ascii=False, indent=2)
    print("เสร็จเรียบร้อย ✔  ไฟล์ทั้งหมดอยู่ในโฟลเดอร์ data")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
