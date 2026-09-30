"""
fetch_funding.py - ดึง funding rate ย้อนหลังของ BTCUSDT perpetual (Binance USDⓈ-M) สำหรับ Backtest

OKX ให้ประวัติ funding ย้อนหลังได้แค่ ~3 เดือน จึงใช้ Binance เป็นตัวแทน (proxy) ของต้นทุน funding
ผลลัพธ์ : data/BTCUSDT_funding.csv  คอลัมน์ timestamp (Unix ms, UTC), funding_time_utc, funding_rate
          (funding_rate เป็นสัดส่วนต่อรอบ เช่น 0.0001 = 0.01%; ค่าบวก = Long จ่าย Short)

วิธีใช้:
  python fetch_funding.py                      # ตั้งแต่ 2021-09-01 ถึงปัจจุบัน
  python fetch_funding.py --start 2020-01-01
"""

import argparse
import csv
import os
from datetime import datetime, timezone

from fetch_btc_data import http_get_json

URL = "https://fapi.binance.com/fapi/v1/fundingRate"


def main():
    ap = argparse.ArgumentParser(description="Download BTCUSDT perpetual funding history (Binance)")
    ap.add_argument("--start", default="2021-09-01")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "BTCUSDT_funding.csv"))
    a = ap.parse_args()

    start = int(datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    rows, cursor = {}, start
    while True:
        batch = http_get_json(URL, {"symbol": "BTCUSDT", "startTime": cursor, "limit": 1000})
        if not batch:
            break
        for r in batch:
            rows[int(r["fundingTime"])] = float(r["fundingRate"])
        last = int(batch[-1]["fundingTime"])
        if len(batch) < 1000 or last <= cursor:
            break
        cursor = last + 1

    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "funding_time_utc", "funding_rate"])
        for ts in sorted(rows):
            w.writerow([ts, datetime.fromtimestamp(ts / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), rows[ts]])
    first, last = min(rows), max(rows)
    fmt = lambda ms: datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M")  # noqa: E731
    print(f"{len(rows)} funding events {fmt(first)} -> {fmt(last)} -> {a.out}")


if __name__ == "__main__":
    main()
