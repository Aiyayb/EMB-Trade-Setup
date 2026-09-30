"""
check.py - Trend Breakout live chart check at the last closed 4H candle (or --until), using the exact rule
functions the backtest uses (engine.py).

  python check.py                                        # is there a Breakout now? levels for the next candle
  python check.py --equity 5000 --risk 0.5               # with position size
  python check.py --open long --entry 64250 --since "2026-09-20 08:00"   # Trailing Stop of an open Trade
  python check.py --until "2024-03-04 12:00"             # the chart as it was then (open time of a 4H candle)

Refresh data first with: python fetch_btc_data.py --tf 15m 4H 1D  and  python fetch_funding.py
"""

import argparse
import sys
import time

import engine as E


def fmt(v, d=1):
    return "–" if v is None else f"{v:,.{d}f}"


def main():
    ap = argparse.ArgumentParser(description="Trend Breakout live chart check")
    ap.add_argument("--until", help="open time (UTC) of the last 4H candle to treat as closed, 'YYYY-MM-DD HH:MM'")
    ap.add_argument("--equity", type=float, help="account equity, for position size")
    ap.add_argument("--risk", type=float, default=E.DEFAULTS["risk_pct"], help="risk %% per Trade (default %(default)s)")
    ap.add_argument("--open", choices=["long", "short"], help="side of a Trade you already hold")
    ap.add_argument("--entry", type=float, help="entry price of that Trade (the Breakout close)")
    ap.add_argument("--since", help="open time (UTC) of that Trade's Breakout candle, 'YYYY-MM-DD HH:MM'")
    a = ap.parse_args()

    cfg = dict(E.DEFAULTS)
    until = E.parse_date(a.until) if a.until else None
    bars4 = E.load(E.data_path("BTCUSDT_4H.csv"), until)
    now_ms = int(time.time() * 1000)
    if until is None and bars4 and bars4[-1]["ts"] + E.H4 > now_ms:
        bars4 = bars4[:-1]  # still forming
    ind = E.indicators(bars4, cfg)
    h = len(bars4) - 1
    b = bars4[h]
    close_ts = b["ts"] + E.H4
    funding = [f for f in E.load_funding(E.data_path("BTCUSDT_funding.csv")) if f[0] <= close_ts]
    rate = funding[-1][1] if funding else None

    print(f"Trend Breakout check · last closed 4H candle {b['t']} UTC (closed {E.fmt_ts(close_ts, E.BKK)} BKK)")
    if until is None:
        age_h = (now_ms - close_ts) / 3600000
        if age_h > 4:
            print(f"  ⚠ data is {age_h:.0f} h old — refresh with fetch_btc_data.py and fetch_funding.py before trading")
    e, atr_ = ind["ema"][h], ind["atr"][h]
    side_ok = "Long only" if b["c"] > e else "Short only"
    fund_txt = f" · last Funding {rate * 100:.4f}%" if rate is not None else ""
    print(f"  close {fmt(b['c'])} · EMA{cfg['ema_n']} {fmt(e)} → Side Filter: {side_ok} · ATR(14) {fmt(atr_)}{fund_txt}")
    print(f"  {cfg['entry_n']}-candle Channel (before this candle): high {fmt(ind['ch_hi'][h])} · low {fmt(ind['ch_lo'][h])}")

    side = E.breakout(ind, bars4, h)
    if side:
        d = 1 if side == "long" else -1
        stop = E.initial_stop(ind, bars4, h, d, cfg)
        r = abs(b["c"] - stop)
        print(f"\n  ✅ BREAKOUT {side.upper()} on this candle → entry at close {fmt(b['c'])}")
        print(f"     Initial Stop {fmt(stop)}  (R = {fmt(r)} = {r / b['c'] * 100:.2f}% of price)")
        t = {"d": d, "stop": stop, "best_close": b["c"]}
        E.trail(ind, bars4, h, t, cfg)
        if t["stop"] != stop:
            print(f"     the 10-candle Channel already lifts the stop to {fmt(t['stop'])}")
        if a.equity:
            pos = E.position(b["c"], stop, a.equity, dict(cfg, risk_pct=a.risk))
            print(f"     size at {a.risk}% of {a.equity:,.0f}: {pos['units']:.4f} BTC · notional {pos['notional']:,.0f}"
                  f" ({pos['notional'] / a.equity:.2f}× equity){' · CAPPED at 3×' if pos['capped'] else ''}"
                  f" · loss at stop ≈ {pos['risk_amt']:,.2f} + costs")
    else:
        print("\n  no Breakout on this candle.")
        nh = max(bb["h"] for bb in bars4[h - cfg["entry_n"] + 1:h + 1])
        nl = min(bb["l"] for bb in bars4[h - cfg["entry_n"] + 1:h + 1])
        if b["c"] > e:
            print(f"  next candle: a LONG Breakout needs a 4H close above {fmt(nh)} (and above EMA200 ≈ {fmt(e)})")
        else:
            print(f"  next candle: a SHORT Breakout needs a 4H close below {fmt(nl)} (and below EMA200 ≈ {fmt(e)})")

    if a.open:
        if a.entry is None or a.since is None:
            ap.error("--open needs --entry and --since")
        s_ms = E.parse_date(a.since)
        k = next((i for i, bb in enumerate(bars4) if bb["ts"] == s_ms), None)
        if k is None:
            ap.error(f"no 4H candle opens at {a.since} UTC")
        d = 1 if a.open == "long" else -1
        stop0 = a.entry - d * cfg["stop_atr"] * ind["atr"][k]
        t = {"d": d, "stop": stop0, "best_close": bars4[k]["c"]}
        E.trail(ind, bars4, k, t, cfg)
        for j in range(k + 1, h + 1):
            in_force = t["stop"]
            if (d == 1 and bars4[j]["l"] <= in_force) or (d == -1 and bars4[j]["h"] >= in_force):
                print(f"\n  ⚠ the stop {fmt(in_force)} was touched during the 4H candle {bars4[j]['t']} — "
                      "by these rules the Trade is already closed")
                break
            E.trail(ind, bars4, j, t, cfg)
        r = abs(a.entry - stop0)
        cur = b["c"]
        print(f"\n  open {a.open.upper()} from {fmt(a.entry)} · Initial Stop {fmt(stop0)} (R {fmt(r)})")
        print(f"  Trailing Stop now {fmt(t['stop'])} · price {fmt(cur)} · open {d * (cur - a.entry) / r:+.2f}R · "
              f"locked {d * (t['stop'] - a.entry) / r:+.2f}R")
    print("\nThis applies your Trend Breakout rules to the data; it is not financial advice.")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
