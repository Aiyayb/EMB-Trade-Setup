"""
analyze_chart.py - mechanical chart read for the trade-setup strategy (stdlib only).

Reads an OHLC CSV (columns: timestamp, open, high, low, close; optional open_time_utc,
open_time_bkk) and reports:
  - EMA 8/26/50/99/200 values and stack alignment
  - Dow swing structure (HH / HL / LH / LL) from fractal swing points
  - SMC events: BOS and CHoCH (candle close beyond a confirmed swing)
  - Execution checks: trend (EMA26 vs EMA50), sideways filter (EMA8-EMA200 distance < 3%),
    ZigZag (period 10) waves, pullback into the EMA 8/26/50/99/200 zone, Fib Retracement +
    Fib Time of the last completed wave (Fib Time 0.5 passed? retraced >= 0.5?)
  - Entry triggers: Engulfing (+ rejection wick), Inside bar breakout, Doji + Engulfing
  - Fib Retracement / Fib Time of the SMC impulse leg and the last fractal swing leg

Usage:
  python analyze_chart.py --file data/BTCUSDT_4H.csv
  python analyze_chart.py --file data/BTCUSDT_15m.csv --bias long      # LTF: direction comes from 4H
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
SIDEWAY_PCT = 3.0      # |EMA8 - EMA200| / EMA200 below this = sideway, no trade
MIN_RETRACE = 0.5      # LTF pullback must retrace at least this much of the wave
DOJI_BODY = 0.1        # doji: body <= 10% of range
REJECTION_WICK = 0.5   # rejection: wick on the rejection side >= 50% of range
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


def _body(b):
    return abs(b["c"] - b["o"])


def _rng(b):
    return b["h"] - b["l"]


def _is_doji(b):
    return _rng(b) > 0 and _body(b) <= DOJI_BODY * _rng(b)


def _rejection(b, bull):
    """Rejection-side wick as a fraction of the candle range (lower wick for longs)."""
    if _rng(b) == 0:
        return 0.0
    wick = (min(b["o"], b["c"]) - b["l"]) if bull else (b["h"] - max(b["o"], b["c"]))
    return wick / _rng(b)


def triggers(bars, lookback):
    """Entry triggers: Engulfing (rejection wick flagged), Inside bar breakout, Doji + Engulfing."""
    out = []
    start = max(2, len(bars) - lookback)
    body_avg = sum(_body(b) for b in bars[-50:]) / max(1, len(bars[-50:]))
    for i in range(start, len(bars)):
        m, p, c = bars[i - 2], bars[i - 1], bars[i]
        pb, cb = _body(p), _body(c)
        found = []
        if p["c"] < p["o"] and c["c"] > c["o"] and c["o"] <= p["c"] and c["c"] >= p["o"] and cb > pb:
            found.append(("Bullish Engulfing", True, c["c"] > p["h"], [p, c]))
        if p["c"] > p["o"] and c["c"] < c["o"] and c["o"] >= p["c"] and c["c"] <= p["o"] and cb > pb:
            found.append(("Bearish Engulfing", False, c["c"] < p["l"], [p, c]))
        # Doji + Engulfing: a doji, then a candle whose body swallows it and closes beyond its extreme
        if _is_doji(p) and cb > _rng(p):
            if c["c"] > c["o"] and c["c"] > p["h"] and c["o"] <= min(p["o"], p["c"]):
                found.append(("Doji + Bullish Engulfing", True, True, [p, c]))
            if c["c"] < c["o"] and c["c"] < p["l"] and c["o"] >= max(p["o"], p["c"]):
                found.append(("Doji + Bearish Engulfing", False, True, [p, c]))
        # Inside bar breakout: p inside mother bar m, c closes beyond m's range
        if p["h"] <= m["h"] and p["l"] >= m["l"]:
            if c["c"] > m["h"]:
                found.append(("Inside Bar Breakout (bull)", True, True, [m, p, c]))
            if c["c"] < m["l"]:
                found.append(("Inside Bar Breakout (bear)", False, True, [m, p, c]))
        for name, bull, strong, group in found:
            rej = max(_rejection(g, bull) for g in group)
            e = {"i": i, "t": c["t"], "type": name, "dir": "bullish" if bull else "bearish",
                 "close": c["c"], "strong": strong, "rejection_wick": rej,
                 "with_rejection": rej >= REJECTION_WICK,
                 "body_vs_avg": cb / body_avg if body_avg else None}
            if bull:
                e["pattern_low"] = min(g["l"] for g in group)
            else:
                e["pattern_high"] = max(g["h"] for g in group)
            out.append(e)
    return out


def zigzag(bars, prd):
    """ZigZag 'Period' as in the common TradingView script (LonesomeTheBlue style):
    a pivot high is a bar whose high is the highest of the last `prd` bars (incl. itself),
    pivot low likewise. A lone pivot of the other kind flips direction -> new point;
    same direction and more extreme -> the last point moves. The last point repaints."""
    pts, d = [], 0
    for i in range(prd - 1, len(bars)):
        win = bars[i - prd + 1:i + 1]
        ph = bars[i]["h"] >= max(x["h"] for x in win)
        pl = bars[i]["l"] <= min(x["l"] for x in win)
        nd = 1 if ph and not pl else -1 if pl and not ph else d
        if not (ph or pl) or nd == 0:
            continue
        typ, price = ("H", bars[i]["h"]) if nd == 1 else ("L", bars[i]["l"])
        if nd != d or not pts:
            pts.append({"i": i, "type": typ, "price": price})
        elif (typ == "H" and price > pts[-1]["price"]) or (typ == "L" and price < pts[-1]["price"]):
            pts[-1] = {"i": i, "type": typ, "price": price}
        d = nd
    return pts


def execution(bars, emas, events, trig, zz, bias):
    """State of the Execution 1 (long) / Execution 2 (short) checklist on this timeframe."""
    long_ = bias == "long"
    e = {n: emas[n][-1] for n in EMA_PERIODS}
    out = {"bias": bias}
    if e[26] is not None and e[50] is not None:
        out["ema26_vs_50"] = "26 > 50 (uptrend)" if e[26] > e[50] else "26 < 50 (downtrend)"
        out["trend_ok"] = (e[26] > e[50]) == long_
    if e[8] is not None and e[200] is not None:
        dist = abs(e[8] - e[200]) / e[200] * 100
        out["ema8_ema200_distance_pct"] = dist
        out["sideway"] = dist < SIDEWAY_PCT
    out["zigzag_live_leg"] = ("up" if zz[-1]["type"] == "H" else "down") if zz else None

    # last completed ZigZag wave in the bias direction (its end point is not the live point)
    end_type = "H" if long_ else "L"
    w = next((j for j in range(len(zz) - 2, 0, -1) if zz[j]["type"] == end_type), None)
    if w is None:
        out["wave"] = None
        return out
    s0, s1 = zz[w - 1], zz[w]
    hi, lo = max(s0["price"], s1["price"]), min(s0["price"], s1["price"])
    rng = hi - lo
    after = bars[s1["i"] + 1:]
    last = bars[-1]
    if long_:
        extreme = min((x["l"] for x in after), default=hi)
        deepest, current = (hi - extreme) / rng, (hi - last["c"]) / rng
    else:
        extreme = max((x["h"] for x in after), default=lo)
        deepest, current = (extreme - lo) / rng, (last["c"] - lo) / rng
    ft = fib_time(bars, s0, s1)
    since = len(bars) - 1 - s1["i"]
    touched = []  # EMAs the pullback has reached since the wave ended
    for n in EMA_PERIODS:
        for k in range(s1["i"] + 1, len(bars)):
            v = emas[n][k]
            if v is not None and ((bars[k]["l"] <= v) if long_ else (bars[k]["h"] >= v)):
                touched.append(n)
                break
    out["wave"] = {
        "from": {"t": bars[s0["i"]]["t"], "price": s0["price"]},
        "to": {"t": bars[s1["i"]]["t"], "price": s1["price"]},
        "still_pulling_back": w == len(zz) - 2,
        "fib_levels": {r: (hi - r * rng) if long_ else (lo + r * rng) for r in FIB_LEVELS},
        "pullback_extreme": extreme,
        "deepest_retracement": deepest,
        "current_retracement": current,
        "retraced_min_0_5": deepest >= MIN_RETRACE,
        "bars_since_wave_end": since,
        "wave_bars": ft["leg_bars"],
        "fib_time_0_5_passed": since >= 0.5 * ft["leg_bars"],
        "fib_time": ft,
        "emas_touched_since_wave_end": touched,
        "in_ema_zone_now": ((last["l"] <= e[8]) if long_ else (last["h"] >= e[8])) if e[8] else None,
    }
    want = "bullish" if long_ else "bearish"
    out["triggers_after_wave"] = [t for t in trig if t["dir"] == want and t["i"] > s1["i"]]
    out["choch_after_wave"] = [ev for ev in events if ev["kind"] == "CHoCH" and ev["i"] > s1["i"]]
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


def analyze(bars, k, lookback, zz_period=10, bias=None):
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
    trig = triggers(bars, lookback)
    zz = zigzag(bars, zz_period)
    if bias is None and ema_now[26] is not None and ema_now[50] is not None:
        bias = "long" if ema_now[26] > ema_now[50] else "short"
    exe = execution(bars, emas, events, trig, zz, bias) if bias else None

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
        "recent_triggers": trig,
        "zigzag_period": zz_period,
        "recent_zigzag": [{"t": bars[z["i"]]["t"], "type": z["type"], "price": z["price"]} for z in zz[-6:]],
        "execution": exe,
        "impulse_leg": leg_info(imp),
        "impulse_fib_retracement": imp_fib,
        "impulse_fib_time": imp_time,
        "last_swing_leg": leg_info(leg),
        "last_swing_fib_retracement": fib,
        "last_swing_fib_time": ftime,
        "note": f"Swings use a {k}-bar fractal and are confirmed {k} bars after the pivot; "
                "the most recent swing may not be visible yet. The last ZigZag point repaints.",
    }


def p(x):
    return "n/a" if x is None else f"{x:,.2f}"


def trig_line(e):
    ext = f"pattern low {p(e['pattern_low'])}" if "pattern_low" in e else f"pattern high {p(e['pattern_high'])}"
    rej = f"rejection wick {e['rejection_wick']:.0%}" + (" (rejection)" if e["with_rejection"] else "")
    strong = "strong" if e["strong"] else "standard"
    return (f"{e['t']}  {e['type']:<27} close {p(e['close'])} | {ext} | {rej} | {strong}"
            f" | body {e['body_vs_avg']:.1f}x avg")


def ok(v):
    return "n/a" if v is None else ("YES" if v else "no")


def print_execution(x):
    long_ = x["bias"] == "long"
    print(f"\n-- Execution {'1 (LONG)' if long_ else '2 (SHORT)'} checklist on this timeframe --")
    if "ema26_vs_50" in x:
        print(f"  [4H step 1]  Trend: EMA {x['ema26_vs_50']} -> matches bias: {ok(x['trend_ok'])}")
    if "sideway" in x:
        print(f"  [4H note]    EMA8-EMA200 distance {x['ema8_ema200_distance_pct']:.2f}% -> "
              f"{'SIDEWAY (< 3%, no trade)' if x['sideway'] else 'trending (>= 3%)'}")
    w = x["wave"]
    if not w:
        print("  No completed ZigZag wave in the bias direction yet.")
        return
    print(f"  [step 2/5]   Last completed {'up' if long_ else 'down'} wave: {p(w['from']['price'])} @ {w['from']['t']}"
          f" -> {p(w['to']['price'])} @ {w['to']['t']} ({w['wave_bars']} bars)")
    print(f"               ZigZag live leg: {x['zigzag_live_leg']}"
          f"{' (pullback after this wave in progress)' if w['still_pulling_back'] else ' (a newer wave is forming)'}")
    print(f"  [4H step 3]  EMAs reached since wave end: {w['emas_touched_since_wave_end'] or 'none'}"
          f" | last bar touching EMA8 zone: {ok(w['in_ema_zone_now'])}")
    print("  [15m step 6] Fib Retracement of the wave:")
    for lvl, price in w["fib_levels"].items():
        tag = "  <- minimum retracement" if lvl == 0.5 else ""
        print(f"      {lvl:<5} {p(price)}{tag}")
    print(f"  [15m step 7] Fib Time 0.5 passed: {ok(w['fib_time_0_5_passed'])} "
          f"({w['bars_since_wave_end']} bars since wave end, needs {0.5 * w['wave_bars']:.1f})")
    for t in w["fib_time"]["windows"]:
        print(f"      {t['ratio']:<5} +{t['bars_after_leg_end']:>3} bars  {t['utc']} UTC / {t['bkk']} BKK"
              f"  ({'passed' if t['passed'] else 'upcoming'})")
    print(f"  [15m step 8] Pullback extreme {p(w['pullback_extreme'])} = retracement {w['deepest_retracement']:.3f}"
          f" (current {w['current_retracement']:.3f}) -> retraced >= 0.5: {ok(w['retraced_min_0_5'])}")
    print(f"  [step 4/9]   {'Bullish' if long_ else 'Bearish'} triggers after the wave end (lookback window):")
    if not x["triggers_after_wave"]:
        print("      none")
    for t in x["triggers_after_wave"]:
        print("      " + trig_line(t))
    print("  [15m note]   CHoCH after the wave end:")
    if not x["choch_after_wave"]:
        print("      none")
    for ev in x["choch_after_wave"]:
        print(f"      {ev['t']}  CHoCH {ev['dir']} close {p(ev['close'])} broke {p(ev['level'])}")


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

    print("\n-- Recent entry triggers (Engulfing / Inside bar breakout / Doji + Engulfing) --")
    if not r["recent_triggers"]:
        print("  none in lookback window")
    for e in r["recent_triggers"]:
        print("  " + trig_line(e))

    print(f"\n-- ZigZag (period {r['zigzag_period']}) recent points --")
    for z in r["recent_zigzag"]:
        print(f"  {z['t']}  {z['type']}  {p(z['price'])}")

    if r["execution"]:
        print_execution(r["execution"])

    for key, title in (("impulse", "impulse leg in trend direction - use for entry zone"),
                       ("last_swing", "last swing leg")):
        fib, leg, ft = r[f"{key}_fib_retracement"], r[f"{key}_leg"], r[f"{key}_fib_time"]
        if not fib:
            continue
        print(f"\n-- Fib Retracement: {title} ({fib['direction']}): "
              f"{leg['from']['label']} {p(leg['from']['price'])} @ {leg['from']['t']} -> "
              f"{leg['to']['label']} {p(leg['to']['price'])} @ {leg['to']['t']} --")
        for lvl, price in fib["levels"].items():
            tag = "  <- entry zone starts (min 0.5)" if lvl == 0.5 else ""
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
    ap.add_argument("--lookback", type=int, default=20, help="bars to scan for entry triggers")
    ap.add_argument("--zigzag", type=int, default=10, help="ZigZag period")
    ap.add_argument("--bias", choices=["long", "short"],
                    help="direction to check (default: EMA26 vs EMA50 of this file; pass the 4H bias on 15m)")
    ap.add_argument("--until", help='replay: ignore bars after "YYYY-MM-DD HH:MM:SS" UTC')
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    bars = load(a.file, a.until)
    if len(bars) < 2 * a.swing + 2:
        sys.exit("error: not enough bars")
    r = analyze(bars, a.swing, a.lookback, a.zigzag, a.bias)
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
