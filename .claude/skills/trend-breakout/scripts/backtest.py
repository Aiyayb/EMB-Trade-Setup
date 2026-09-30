"""
backtest.py - one Trend Breakout Backtest Run from the command line.

  python backtest.py --from 2021-10-01 --to 2024-12-31                  # Baseline, Tuning Period
  python backtest.py --to 2024-12-31 --stop-atr 3 --adx-min 20          # a Variant (Levers)
  python backtest.py --to 2024-12-31 --no-funding --fee-pct 0 --slippage-pct 0

With no Lever the run is the Baseline. Any run with a Lever that reaches the Holdout Period
(2025-01-01 onward) is refused without --holdout - use variants.py --holdout for the Finalist.
"""

import argparse
import os
import sys
from datetime import datetime

import engine as E
import report_tb


def add_lever_args(ap):
    g = ap.add_argument_group("Levers (all off = Baseline)")
    g.add_argument("--entry-n", type=int, default=E.DEFAULTS["entry_n"], help="Breakout Channel length")
    g.add_argument("--exit-n", type=int, default=E.DEFAULTS["exit_n"], help="Trailing Stop Channel length")
    g.add_argument("--stop-atr", type=float, default=E.DEFAULTS["stop_atr"], help="Initial Stop, x ATR(14)")
    g.add_argument("--chandelier-atr", type=float, help="Trailing Stop = best close since entry -/+ this x ATR")
    g.add_argument("--d1-ema", type=int, help="Filter: last closed 1D close on the trade side of 1D EMA(n)")
    g.add_argument("--adx-min", type=float, help="Filter: 4H ADX(14) at the Breakout >= this")
    g.add_argument("--funding-max", type=float, help="Filter: skip Longs when Funding >= this (e.g. 0.0003), Shorts when <= -this")
    g.add_argument("--pyramid", action="store_true", help="add one unit on the next same-side Breakout while in profit")


def lever_cfg(a):
    return {"entry_n": a.entry_n, "exit_n": a.exit_n, "stop_atr": a.stop_atr, "chandelier_atr": a.chandelier_atr,
            "d1_ema": a.d1_ema, "adx_min": a.adx_min, "funding_max": a.funding_max, "pyramid": a.pyramid}


def main():
    ap = argparse.ArgumentParser(description="Backtest Trend Breakout on BTCUSDT 4H + 15m")
    ap.add_argument("--from", dest="start", default="2021-10-01", help="first entry date (UTC)")
    ap.add_argument("--to", dest="end", help="last entry date (UTC); default = end of data")
    ap.add_argument("--balance", type=float, default=E.DEFAULTS["balance"])
    ap.add_argument("--risk-pct", type=float, default=E.DEFAULTS["risk_pct"])
    ap.add_argument("--fee-pct", type=float, default=E.DEFAULTS["fee_pct"], help="per side")
    ap.add_argument("--slippage-pct", type=float, default=E.DEFAULTS["slippage_pct"], help="per side")
    ap.add_argument("--no-funding", action="store_true", help="ignore Funding (for comparison only)")
    ap.add_argument("--side", choices=["long", "short", "both"], default="both")
    ap.add_argument("--holdout", action="store_true", help="allow a Variant to reach the Holdout Period")
    ap.add_argument("--out", help="output folder; default backtests/tb-<timestamp>")
    add_lever_args(ap)
    a = ap.parse_args()

    cfg = {"balance": a.balance, "risk_pct": a.risk_pct, "fee_pct": a.fee_pct, "slippage_pct": a.slippage_pct,
           "funding": not a.no_funding, "side": a.side, "start": E.parse_date(a.start),
           "end": E.parse_date(a.end, end=True), **lever_cfg(a)}
    if E.levers(cfg) and E.touches_holdout(cfg) and not a.holdout:
        ap.error("this Variant's window reaches the Holdout Period (2025-01-01 onward); end it with --to 2024-12-31 "
                 "(docs/adr/0001, 0002)")
    d = E.load_all(cfg)
    trades, info = E.run(d["bars4"], d["bars15"], cfg, bars1d=d["bars1d"], funding=d["funding"])
    out = a.out or os.path.join(E.ROOT, "backtests", "tb-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    s = report_tb.write_all(out, trades, info, d["bars15"])
    al, eq = s["all"], s["equity"]
    print(f"trades {al['trades']} (filtered {s['filtered']['trades']}) | win {al.get('win_rate_pct', 0):.1f}% | "
          f"PF {al.get('profit_factor') or 0:.2f} | payoff {al.get('payoff') or 0:.2f} | exp {al.get('expectancy_r', 0):+.3f}R | "
          f"MTM DD {eq['max_drawdown_pct']:.1f}% at {a.risk_pct}% | risk budget -> {s['risk_budget']['chosen_risk_pct']}%")
    print(f"output: {out}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
