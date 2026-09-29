"""
parity_check.py - prove the backtest engine sees exactly what analyze_chart.py --until sees.

At random 15m bars (plus a sample of real entry bars) it compares the engine's bar-by-bar state
with a fresh analyze_chart run on data cut at that moment: 4H EMAs / trend / Sideway distance /
Wave, 15m EMAs / Wave / deepest retracement / Fib 0.5 / Fib Time 0.5 / triggers on that bar.
Any mismatch means look-ahead or logic drift.

Usage:
  python parity_check.py                 # 20 random bars + 10 entry bars
  python parity_check.py --random 50 --entries 20 --seed 7
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as bt  # noqa: E402

ac = bt.ac
TOL = 1e-9


def close(a, b):
    if a is None or b is None:
        return a is b
    return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))


def check(snap, bars4, bars15, f4, f15):
    errs = []
    h, i = snap["h"], snap["i"]
    now = bars15[i]["ts"] + bt.M15
    if bars4[h]["ts"] + bt.H4 > now:
        errs.append(f"look-ahead: 4H bar {bars4[h]['t']} not closed at {bars15[i]['t']} close")
    if h + 1 < len(bars4) and bars4[h + 1]["ts"] + bt.H4 <= now:
        errs.append(f"stale: 4H bar {bars4[h + 1]['t']} already closed but not used")
    b4 = ac.load(f4, bars4[h]["t"])
    r4 = ac.analyze(b4, 5, 20, 10)
    for n in ac.EMA_PERIODS:
        if not close(snap["ema4"][n], r4["ema"][n]):
            errs.append(f"4H EMA{n} {snap['ema4'][n]} != {r4['ema'][n]}")
    x4 = r4["execution"] or {}
    if snap["bias"] != x4.get("bias"):
        errs.append(f"4H bias {snap['bias']} != {x4.get('bias')}")
    if not close(snap["dist4"], x4.get("ema8_ema200_distance_pct")):
        errs.append(f"4H sideway dist {snap['dist4']} != {x4.get('ema8_ema200_distance_pct')}")
    w4 = x4.get("wave")
    ew4 = snap["wave4"]
    mine = ((bars4[ew4[0]["i"]]["t"], ew4[0]["price"]), (bars4[ew4[1]["i"]]["t"], ew4[1]["price"])) if ew4 else None
    theirs = ((w4["from"]["t"], w4["from"]["price"]), (w4["to"]["t"], w4["to"]["price"])) if w4 else None
    if mine != theirs:
        errs.append(f"4H wave {mine} != {theirs}")

    b15 = ac.load(f15, snap["t"])
    r15 = ac.analyze(b15, 5, 20, 10, snap["bias"])
    for n in ac.EMA_PERIODS:
        if not close(snap["ema15"][n], r15["ema"][n]):
            errs.append(f"15m EMA{n} {snap['ema15'][n]} != {r15['ema'][n]}")
    w15 = (r15["execution"] or {}).get("wave")
    ew = snap.get("wave15")
    if bool(w15) != bool(ew):
        errs.append(f"15m wave presence engine={bool(ew)} analyzer={bool(w15)}")
    elif ew:
        if ew["from"] != (w15["from"]["t"], w15["from"]["price"]) or ew["to"] != (w15["to"]["t"], w15["to"]["price"]):
            errs.append(f"15m wave {ew['from']}->{ew['to']} != {w15['from']}->{w15['to']}")
        else:
            if not close(ew["deepest"], w15["deepest_retracement"]):
                errs.append(f"15m deepest {ew['deepest']} != {w15['deepest_retracement']}")
            if ew["fib_time_0_5_passed"] != w15["fib_time_0_5_passed"]:
                errs.append(f"15m fib time 0.5 {ew['fib_time_0_5_passed']} != {w15['fib_time_0_5_passed']}")
            if not close(ew["fib_050"], w15["fib_levels"][0.5]):
                errs.append(f"15m fib 0.5 {ew['fib_050']} != {w15['fib_levels'][0.5]}")
    trig = sorted(t["type"] for t in r15["recent_triggers"] if t["i"] == len(b15) - 1)
    if trig != snap["triggers15"]:
        errs.append(f"15m triggers {snap['triggers15']} != {trig}")
    return errs


def main():
    ap = argparse.ArgumentParser(description="Parity: backtest engine vs analyze_chart.py --until")
    ap.add_argument("--random", type=int, default=20)
    ap.add_argument("--entries", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--file-4h", default=os.path.join(bt.ROOT, "data", "BTCUSDT_4H.csv"))
    ap.add_argument("--file-15m", default=os.path.join(bt.ROOT, "data", "BTCUSDT_15m.csv"))
    a = ap.parse_args()

    bars4, bars15 = ac.load(a.file_4h), ac.load(a.file_15m)
    rnd = random.Random(a.seed)
    warm = 210 * 16  # EMA200 on 4H needs ~200 closed 4H bars
    probes = set(rnd.sample(range(warm, len(bars15)), a.random))
    trades, _ = bt.run(bars4, bars15, {})
    entries = [t["entry_i"] for t in trades]
    probes |= set(rnd.sample(entries, min(a.entries, len(entries))))
    _, info = bt.run(bars4, bars15, {}, probe=probes)

    fails = 0
    for n, i in enumerate(sorted(probes), 1):
        snap = info["snapshots"][i]
        tag = "entry " if i in entries else "random"
        errs = check(snap, bars4, bars15, a.file_4h, a.file_15m)
        fails += bool(errs)
        print(f"[{n:>3}/{len(probes)}] {tag} {snap['t']}  {'OK' if not errs else 'MISMATCH'}", flush=True)
        for e in errs:
            print("      - " + e)
    print(f"\n{len(probes) - fails}/{len(probes)} probes match")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
