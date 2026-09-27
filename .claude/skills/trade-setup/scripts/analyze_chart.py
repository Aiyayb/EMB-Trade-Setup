"""
analyze_chart.py - mechanical chart read for the trade-setup strategy (stdlib only).

Reads an OHLC CSV (columns: timestamp, open, high, low, close; optional open_time_utc,
open_time_bkk) and reports:
  - EMA 8/26/50/99/200 values and stack alignment
  - Dow swing structure (HH / HL / LH / LL) from fractal swing points
  - SMC events: BOS and CHoCH (candle close beyond a confirmed swing)
  - Recent Bullish / Bearish Engulfing candles
  - Fib Retracement of the last swing leg + where price sits
  - Fib Time windows projected from the last leg

Usage:
  python analyze_chart.py --file data/BTCUSDT_4H.csv
  python analyze_chart.py --file data/BTCUSDT_1H.csv --swing 3 --lookback 20
  python analyze_chart.py --file data/BTCUSDT_1D.csv --until "2025-03-01 00:00:00"   # replay history
  python analyze_chart.py --file data/BTCUSDT_4H.csv --json
"""

import argparse
import csv
import json
import sys
from datetime import datetime, timedelta, timezone

EMA_PERIODS = [8, 26, 50, 99, 200]
FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.705, 0.786, 1.0]
FIB_TIME_RATIOS = [0.382, 0.5, 0.618, 1.0, 1.618, 2.618]
UTC = timezone.utc
BKK = timezone(timedelta(hours=7))


def load(path, until=None):
    bars = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ts = int(float(row["timestamp"]))
            bars.append({
                "ts": ts,
                "t": row.get("open_time_utc") or datetime.fromtimestamp(ts / 1000, UTC).strftime("%Y-%m-%d %H:%M:%S"),
                "o": float(row["open"]), "h": float(row["high"]),
                "l": float(row["low"]), "c": float(row["close"]),
            })
    bars.sort(key=lambda b: b["ts"])
    if until:
        cut = int(datetime.strptime(until, "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC).timestamp() * 1000)
        bars = [b for b in bars if b["ts"] <= cut]
    return bars


def ema(values, n):
    out = [None] * len(values)
    if len(values) < n:
        return out
    k = 2 / (n + 1)
    e = sum(values[:n]) / n
    out[n - 1] = e
    for i in range(n, len(values)):
        e = values[i] * k + e * (1 - k)
        out[i] = e
    return out


def find_swings(bars, k):
    """Fractal swings: high/low is the extreme of k bars on each side. Confirmed at index i+k."""
    swings = []
    for i in range(k, len(bars) - k):
        h, l = bars[i]["h"], bars[i]["l"]
        # strict on the left, non-strict on the right -> one pivot per flat top/bottom
        if all(h > b["h"] for b in bars[i - k:i]) and all(h >= b["h"] for b in bars[i + 1:i + k + 1]):
            swings.append({"i": i, "type": "H", "price": h, "confirmed_at": i + k})
        if all(l < b["l"] for b in bars[i - k:i]) and all(l <= b["l"] for b in bars[i + 1:i + k + 1]):
            swings.append({"i": i, "type": "L", "price": l, "confirmed_at": i + k})
    swings.sort(key=lambda s: (s["i"], s["type"]))
    return swings


def label_dow(swings):
    last = {"H": None, "L": None}
    for s in swings:
        prev = last[s["type"]]
        if prev is None:
            s["label"] = "SH" if s["type"] == "H" else "SL"
        elif s["type"] == "H":
            s["label"] = "HH" if s["price"] > prev["price"] else "LH"
        else:
            s["label"] = "HL" if s["price"] > prev["price"] else "LL"
        last[s["type"]] = s
    return swings


def smc_events(bars, swings):
    """Walk bars in time; a close beyond the latest confirmed, unbroken swing = BOS or CHoCH."""
    by_confirm = {}
    for s in swings:
        by_confirm.setdefault(s["confirmed_at"], []).append(s)
    trend = None  # "up" / "down"
    last_h = last_l = None
    events = []
    for i, b in enumerate(bars):
        for s in by_confirm.get(i, []):
            if s["type"] == "H":
                last_h = dict(s, broken=False)
            else:
                last_l = dict(s, broken=False)
        if last_h and not last_h["broken"] and b["c"] > last_h["price"]:
            kind = "CHoCH" if trend == "down" else "BOS"
            events.append({"i": i, "t": b["t"], "kind": kind, "dir": "bullish",
                           "level": last_h["price"], "swing_t": bars[last_h["i"]]["t"], "close": b["c"]})
            trend = "up"
            last_h["broken"] = True
        if last_l and not last_l["broken"] and b["c"] < last_l["price"]:
            kind = "CHoCH" if trend == "up" else "BOS"
            events.append({"i": i, "t": b["t"], "kind": kind, "dir": "bearish",
                           "level": last_l["price"], "swing_t": bars[last_l["i"]]["t"], "close": b["c"]})
            trend = "down"
            last_l["broken"] = True
    return events, trend


def engulfings(bars, lookback):
    out = []
    start = max(1, len(bars) - lookback)
    body_avg = sum(abs(b["c"] - b["o"]) for b in bars[-50:]) / max(1, len(bars[-50:]))
    for i in range(start, len(bars)):
        p, c = bars[i - 1], bars[i]
        pb, cb = abs(p["c"] - p["o"]), abs(c["c"] - c["o"])
        if p["c"] < p["o"] and c["c"] > c["o"] and c["o"] <= p["c"] and c["c"] >= p["o"] and cb > pb:
            out.append({"i": i, "t": c["t"], "type": "Bullish Engulfing", "close": c["c"],
                        "pattern_low": min(p["l"], c["l"]), "strong": c["c"] > p["h"],
                        "body_vs_avg": cb / body_avg if body_avg else None})
        if p["c"] > p["o"] and c["c"] < c["o"] and c["o"] >= p["c"] and c["c"] <= p["o"] and cb > pb:
            out.append({"i": i, "t": c["t"], "type": "Bearish Engulfing", "close": c["c"],
                        "pattern_high": max(p["h"], c["h"]), "strong": c["c"] < p["l"],
                        "body_vs_avg": cb / body_avg if body_avg else None})
    return out


def last_leg(swings):
    """Most recent alternating pair: (start swing, end swing)."""
    if len(swings) < 2:
        return None
    end = swings[-1]
    for s in reversed(swings[:-1]):
        if s["type"] != end["type"]:
            return s, end
    return None


def impulse_leg(bars, swings, events, trend):
    """Impulse leg in the current SMC trend: from the swing that launched the latest
    break in that direction to the most extreme price since the break (may be unconfirmed)."""
    ev = next((e for e in reversed(events) if e["dir"] == ("bullish" if trend == "up" else "bearish")), None)
    if ev is None:
        return None
    origin_type = "L" if trend == "up" else "H"
    origin = next((s for s in reversed(swings) if s["type"] == origin_type and s["i"] < ev["i"]), None)
    if origin is None:
        return None
    tail = range(ev["i"], len(bars))
    if trend == "up":
        j = max(tail, key=lambda i: bars[i]["h"])
        end = {"i": j, "type": "H", "price": bars[j]["h"], "label": "high"}
    else:
        j = min(tail, key=lambda i: bars[i]["l"])
        end = {"i": j, "type": "L", "price": bars[j]["l"], "label": "low"}
    return origin, end


def fib_retracement(start, end, price):
    hi, lo = max(start["price"], end["price"]), min(start["price"], end["price"])
    rng = hi - lo
    up = end["type"] == "H"  # leg low -> high
    levels = {r: (hi - r * rng) if up else (lo + r * rng) for r in FIB_LEVELS}
    retr = ((hi - price) / rng if up else (price - lo) / rng) if rng else None
    return {"direction": "up" if up else "down", "high": hi, "low": lo, "levels": levels,
            "current_retracement": retr}


def fib_time(bars, start, end):
    dur = end["i"] - start["i"]
    step = bars[1]["ts"] - bars[0]["ts"] if len(bars) > 1 else 0
    out = []
    for r in FIB_TIME_RATIOS:
        n = round(end["i"] + r * dur)
        ts = bars[end["i"]]["ts"] + round(r * dur) * step
        out.append({"ratio": r, "bars_after_leg_end": round(r * dur),
                    "utc": datetime.fromtimestamp(ts / 1000, UTC).strftime("%Y-%m-%d %H:%M"),
                    "bkk": datetime.fromtimestamp(ts / 1000, BKK).strftime("%Y-%m-%d %H:%M"),
                    "passed": n <= len(bars) - 1})
    return {"leg_bars": dur, "windows": out}


def analyze(bars, k, lookback):
    closes = [b["c"] for b in bars]
    emas = {n: ema(closes, n) for n in EMA_PERIODS}
    last = bars[-1]
    ema_now = {n: emas[n][-1] for n in EMA_PERIODS}

    vals = [last["c"]] + [ema_now[n] for n in EMA_PERIODS]
    if None in vals:
        stack = "insufficient data"
    elif all(vals[i] > vals[i + 1] for i in range(len(vals) - 1)):
        stack = "full bullish (price > 8 > 26 > 50 > 99 > 200)"
    elif all(vals[i] < vals[i + 1] for i in range(len(vals) - 1)):
        stack = "full bearish (price < 8 < 26 < 50 < 99 < 200)"
    else:
        above200 = ema_now[200] is not None and last["c"] > ema_now[200]
        stack = f"mixed / partial - price {'above' if above200 else 'below'} EMA200"
    slope200 = None
    if emas[200][-1] is not None and len(bars) > 10 and emas[200][-11] is not None:
        slope200 = (emas[200][-1] - emas[200][-11]) / emas[200][-11] * 100

    swings = label_dow(find_swings(bars, k))
    events, smc_trend = smc_events(bars, swings)
    leg = last_leg(swings)
    fib = fib_retracement(leg[0], leg[1], last["c"]) if leg else None
    ftime = fib_time(bars, leg[0], leg[1]) if leg else None
    imp = impulse_leg(bars, swings, events, smc_trend) if smc_trend else None
    imp_fib = fib_retracement(imp[0], imp[1], last["c"]) if imp else None
    imp_time = fib_time(bars, imp[0], imp[1]) if imp else None

    def leg_info(lg):
        return ({"from": {"t": bars[lg[0]["i"]]["t"], "price": lg[0]["price"], "label": lg[0]["label"]},
                 "to": {"t": bars[lg[1]["i"]]["t"], "price": lg[1]["price"], "label": lg[1]["label"]}}
                if lg else None)

    return {
        "last_bar": {"t": last["t"], "o": last["o"], "h": last["h"], "l": last["l"], "c": last["c"]},
        "bars": len(bars),
        "ema": ema_now,
        "ema_stack": stack,
        "ema200_slope_pct_10bars": slope200,
        "recent_swings": [{"t": bars[s["i"]]["t"], "label": s["label"], "price": s["price"]} for s in swings[-8:]],
        "smc_trend": smc_trend,
        "recent_smc_events": events[-5:],
        "recent_engulfing": engulfings(bars, lookback),
        "impulse_leg": leg_info(imp),
        "impulse_fib_retracement": imp_fib,
        "impulse_fib_time": imp_time,
        "last_swing_leg": leg_info(leg),
        "last_swing_fib_retracement": fib,
        "last_swing_fib_time": ftime,
        "note": f"Swings use a {k}-bar fractal and are confirmed {k} bars after the pivot; "
                "the most recent swing may not be visible yet.",
    }


def p(x):
    return "n/a" if x is None else f"{x:,.2f}"


def print_report(r, path):
    lb = r["last_bar"]
    print(f"=== {path} | {r['bars']} bars | last closed bar {lb['t']} UTC ===")
    print(f"O {p(lb['o'])}  H {p(lb['h'])}  L {p(lb['l'])}  C {p(lb['c'])}\n")

    print("-- EMA --")
    print("  " + "  ".join(f"EMA{n}: {p(v)}" for n, v in r["ema"].items()))
    print(f"  Stack: {r['ema_stack']}")
    if r["ema200_slope_pct_10bars"] is not None:
        print(f"  EMA200 slope (10 bars): {r['ema200_slope_pct_10bars']:+.2f}%")

    print("\n-- Dow structure (recent swings) --")
    for s in r["recent_swings"]:
        print(f"  {s['t']}  {s['label']:>3}  {p(s['price'])}")

    print(f"\n-- SMC (current structure trend: {r['smc_trend']}) --")
    for e in r["recent_smc_events"]:
        print(f"  {e['t']}  {e['kind']:<5} {e['dir']:<8} close {p(e['close'])} broke {p(e['level'])} (swing {e['swing_t']})")

    print("\n-- Recent engulfing candles --")
    if not r["recent_engulfing"]:
        print("  none in lookback window")
    for e in r["recent_engulfing"]:
        ext = f"pattern low {p(e['pattern_low'])}" if "pattern_low" in e else f"pattern high {p(e['pattern_high'])}"
        strong = "strong (closed beyond prev extreme)" if e["strong"] else "standard"
        print(f"  {e['t']}  {e['type']:<18} close {p(e['close'])} | {ext} | {strong} | body {e['body_vs_avg']:.1f}x avg")

    for key, title in (("impulse", "impulse leg in trend direction - use for entry zone"),
                       ("last_swing", "last swing leg")):
        fib, leg, ft = r[f"{key}_fib_retracement"], r[f"{key}_leg"], r[f"{key}_fib_time"]
        if not fib:
            continue
        print(f"\n-- Fib Retracement: {title} ({fib['direction']}): "
              f"{leg['from']['label']} {p(leg['from']['price'])} @ {leg['from']['t']} -> "
              f"{leg['to']['label']} {p(leg['to']['price'])} @ {leg['to']['t']} --")
        for lvl, price in fib["levels"].items():
            tag = "  <- golden zone" if lvl in (0.5, 0.618) else ""
            print(f"  {lvl:<5} {p(price)}{tag}")
        if fib["current_retracement"] is not None:
            print(f"  Current price retracement: {fib['current_retracement']:.3f}")
        print(f"  Fib Time ({ft['leg_bars']}-bar leg, projected from leg end):")
        for w in ft["windows"]:
            flag = "passed" if w["passed"] else "upcoming"
            print(f"    {w['ratio']:<5} +{w['bars_after_leg_end']:>3} bars  {w['utc']} UTC / {w['bkk']} BKK  ({flag})")

    print(f"\nNote: {r['note']}")


def main():
    ap = argparse.ArgumentParser(description="Mechanical chart read for the trade-setup strategy")
    ap.add_argument("--file", required=True, help="OHLC CSV, e.g. data/BTCUSDT_4H.csv")
    ap.add_argument("--swing", type=int, default=5, help="fractal bars each side for swing points")
    ap.add_argument("--lookback", type=int, default=10, help="bars to scan for engulfing candles")
    ap.add_argument("--until", help='replay: ignore bars after "YYYY-MM-DD HH:MM:SS" UTC')
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    bars = load(a.file, a.until)
    if len(bars) < 2 * a.swing + 2:
        sys.exit("error: not enough bars")
    r = analyze(bars, a.swing, a.lookback)
    if a.json:
        print(json.dumps(r, indent=2, default=str))
    else:
        print_report(r, a.file)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
