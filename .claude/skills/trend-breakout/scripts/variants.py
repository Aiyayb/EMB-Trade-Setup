"""
variants.py - run the pre-registered Trend Breakout Variants on the Tuning Period, check each against the
Acceptance Bar and pick the Finalist; or run that Finalist once on the Holdout Period.
Process: docs/adr/0001 (method) and docs/adr/0002 (Trend Breakout targets). Stdlib only.

  python variants.py                  # Baseline + every registered Variant, Tuning Period
  python variants.py --only T03 T08   # a subset
  python variants.py --holdout T08    # the single Finalist run on the Holdout Period (once, ever)
"""

import argparse
import json
import os
import sys
from datetime import datetime

import engine as E
import report_tb
import report

TUNING = ("2021-10-01", "2024-12-31")
HOLDOUT_FROM = "2025-01-01"
SEARCH_BUDGET = 20
PF_BAR, MIN_TRADES, SIDE_PF, TIE_PF = 2.0, 100, 1.0, 0.1
LEDGER = os.path.join(E.ROOT, "docs", "holdout-ledger.json")  # shared by every strategy: the Holdout is used once

# Registered 2026-09-30 before any Variant was run (ADR 0002). Append only: never edit or delete a row once it
# has run; every row counts against the Search Budget. Combinations of the best single Levers go below T11.
VARIANTS = {
    "T01": ("Channel 10/5", {"entry_n": 10, "exit_n": 5}),
    "T02": ("Channel 55/20", {"entry_n": 55, "exit_n": 20}),
    "T03": ("Initial Stop 1.5 ATR", {"stop_atr": 1.5}),
    "T04": ("Initial Stop 3 ATR", {"stop_atr": 3.0}),
    "T05": ("Chandelier 3 ATR", {"chandelier_atr": 3.0}),
    "T06": ("Chandelier 4 ATR", {"chandelier_atr": 4.0}),
    "T07": ("1D EMA50 agrees", {"d1_ema": 50}),
    "T08": ("ADX >= 20", {"adx_min": 20.0}),
    "T09": ("ADX >= 25", {"adx_min": 25.0}),
    "T10": ("Funding < 0.03%", {"funding_max": 0.0003}),
    "T11": ("Pyramid 1 add", {"pyramid": True}),
}
assert len(VARIANTS) <= SEARCH_BUDGET, "Search Budget exceeded - the Variant approach has failed (docs/adr/0001)"


def evaluate(vid, label, lv, start, end, data, out_root, risk_pct=None):
    """Run one config, size it from the DD budget (or at `risk_pct`), write its report, check the Acceptance Bar."""
    cfg = {"start": E.parse_date(start), "end": E.parse_date(end, end=True) if end else None, **lv}
    args = (data["bars4"], data["bars15"])
    kw = {"bars1d": data["bars1d"], "funding": data["funding"]}
    trades, info = E.run(*args, cfg, **kw)
    rb = E.choose_risk(trades, info["events"])
    use = risk_pct if risk_pct is not None else (rb["chosen_risk_pct"] or E.risk.LADDER[0])
    trades, info = E.run(*args, dict(cfg, risk_pct=use), **kw)
    out = os.path.join(out_root, vid)
    s = report_tb.write_all(out, trades, info, data["bars15"], f"{vid} {label}", rb)
    al, sides = s["all"], s["by_side"]
    pf = al.get("profit_factor") or 0.0
    pfl, pfs = (sides.get(k, {}).get("profit_factor") for k in ("LONG", "SHORT"))
    dd = s["equity"]["max_drawdown_pct"]
    checks = {
        f"PF >= {PF_BAR:g}": pf >= PF_BAR,
        "Max DD < 15%": dd < E.risk.DD_LIMIT_PCT and (risk_pct is not None or rb["chosen_risk_pct"] is not None),
        "Long PF >= 1": (pfl or 0) >= SIDE_PF,
        "Short PF >= 1": (pfs or 0) >= SIDE_PF,
    }
    if risk_pct is None:
        checks[f"Trades >= {MIN_TRADES}"] = al["trades"] >= MIN_TRADES
    return {
        "id": vid, "label": label, "levers": lv, "from": start, "to": end or s["run"]["to"],
        "trades": al["trades"], "filtered": s["filtered"]["trades"], "win_rate_pct": al.get("win_rate_pct"),
        "profit_factor": al.get("profit_factor"), "payoff": al.get("payoff"), "expectancy_r": al.get("expectancy_r"),
        "gross_expectancy_r": al.get("gross_expectancy_r"), "funding_r": al.get("funding_r_per_trade"),
        "pf_long": pfl, "pf_short": pfs, "max_losing_streak": al.get("max_losing_streak"),
        "risk_pct": use, "risk_budget": rb, "max_drawdown_pct": dd, "cagr_pct": s["equity"]["cagr_pct"],
        "checks": checks, "passed": all(checks.values()),
        "report": os.path.relpath(os.path.join(out, "report.html"), out_root).replace("\\", "/"),
    }


def pick_finalist(rows):
    ok = [r for r in rows if r["passed"] and r["id"] != "Baseline"]
    if not ok:
        return None
    best = max(r["profit_factor"] for r in ok)
    return min((r for r in ok if r["profit_factor"] >= best - TIE_PF), key=lambda r: (len(r["levers"]), -r["profit_factor"]))


def fmt(v, d=2, suf=""):
    return report.num(v, d, suf)


COLS = [
    ("Variant", lambda r: f"<a href='{report.esc(r['report'])}'>{report.esc(r['id'])}</a>"),
    ("Levers", lambda r: report.esc(r["label"])),
    ("Trades", lambda r: r["trades"]), ("Filtered", lambda r: r["filtered"]),
    ("Win %", lambda r: fmt(r["win_rate_pct"], 1)), ("PF (net)", lambda r: fmt(r["profit_factor"])),
    ("Payoff", lambda r: fmt(r["payoff"])),
    ("PF Long", lambda r: fmt(r["pf_long"])), ("PF Short", lambda r: fmt(r["pf_short"])),
    ("Exp. R net", lambda r: fmt(r["expectancy_r"], 3)), ("Funding R", lambda r: fmt(r["funding_r"], 3)),
    ("Risk", lambda r: fmt(r["risk_pct"], 2, "%") + ("" if r["risk_budget"]["chosen_risk_pct"] else " ✗")),
    ("Max DD (MTM)", lambda r: fmt(r["max_drawdown_pct"], 1, "%")), ("CAGR", lambda r: fmt(r["cagr_pct"], 1, "%")),
    ("Pass", lambda r: "✓" if r["passed"] else "✗ " + ", ".join(k for k, v in r["checks"].items() if not v)),
]


def write_board(rows, out_root, title, finalist=None, note=""):
    with open(os.path.join(out_root, "leaderboard.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "finalist": finalist and finalist["id"], "rows": rows}, f, indent=2, ensure_ascii=False)
    tiles = [("Variants run", f"{sum(r['id'] != 'Baseline' for r in rows)} (registered {len(VARIANTS)}, budget {SEARCH_BUDGET})"),
             ("Passed", sum(1 for r in rows if r["passed"] and r["id"] != "Baseline")),
             ("Finalist", finalist["id"] + " " + finalist["label"] if finalist else "none")]
    body = (f"<main><h1>{report.esc(title)}</h1><p class='sub'>Acceptance Bar (after fees, slippage and Funding): "
            f"PF ≥ {PF_BAR:g} · Max Drawdown (mark-to-market) &lt; 15% at the risk chosen from the DD budget · "
            f"≥ {MIN_TRADES} Trades · Long and Short PF ≥ 1. {report.esc(note)}</p><div class='tiles'>"
            + "".join(f"<div class='tile'><div class='k'>{report.esc(k)}</div><div class='v'>{report.esc(v)}</div></div>"
                      for k, v in tiles)
            + "</div><h2>Leaderboard</h2>" + report.table(rows, COLS) + "</main>")
    with open(os.path.join(out_root, "leaderboard.html"), "w", encoding="utf-8") as f:
        f.write(f"<!doctype html><html lang='th'><head><meta charset='utf-8'><meta name='viewport' "
                f"content='width=device-width,initial-scale=1'><title>Trend Breakout Leaderboard</title>"
                f"<style>{report.CSS}</style></head><body>{body}</body></html>")


def print_rows(rows):
    print(f"{'id':<9}{'levers':<22}{'trades':>7}{'win%':>6}{'PF':>6}{'payoff':>7}{'PF L':>6}{'PF S':>6}"
          f"{'expR':>8}{'risk':>6}{'DD%':>6}  pass")
    for r in rows:
        print(f"{r['id']:<9}{r['label'][:21]:<22}{r['trades']:>7}{r['win_rate_pct'] or 0:>6.1f}{r['profit_factor'] or 0:>6.2f}"
              f"{r['payoff'] or 0:>7.2f}{r['pf_long'] or 0:>6.2f}{r['pf_short'] or 0:>6.2f}{r['expectancy_r'] or 0:>+8.3f}"
              f"{r['risk_pct']:>6.2f}{r['max_drawdown_pct']:>6.1f}  "
              + ("PASS" if r["passed"] else "fail: " + ", ".join(k for k, v in r["checks"].items() if not v)))


def read_ledger():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="Run registered Trend Breakout Variants against the Acceptance Bar")
    ap.add_argument("--only", nargs="+", metavar="ID")
    ap.add_argument("--holdout", metavar="ID", help="run this Finalist once on the Holdout Period")
    ap.add_argument("--out")
    a = ap.parse_args()
    ids = a.only or list(VARIANTS)
    bad = [i for i in ids + ([a.holdout] if a.holdout else []) if i not in VARIANTS]
    if bad:
        ap.error(f"unknown Variant id(s) {bad}; register them in VARIANTS first (they count against the Search Budget)")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = a.out or os.path.join(E.ROOT, "backtests", ("tb-holdout-" if a.holdout else "tb-variants-") + stamp)
    os.makedirs(out_root, exist_ok=True)
    data = E.load_all()

    if a.holdout:
        ledger = read_ledger()
        if ledger:
            ap.error(f"the Holdout Period was already used ({ledger[0].get('strategy', 'EMA Pullback')} {ledger[0]['id']} "
                     f"on {ledger[0]['run_at']}); it cannot be used again (docs/adr/0001)")
        tdir = os.path.join(out_root, "tuning")
        rows = [evaluate("Baseline", "Baseline", {}, *TUNING, data, tdir)]
        rows += [evaluate(v, *VARIANTS[v], *TUNING, data, tdir) for v in VARIANTS]
        fin = pick_finalist(rows)
        if not fin or fin["id"] != a.holdout:
            ap.error(f"{a.holdout} is not the Finalist on the Tuning Period (Finalist: {fin and fin['id']})")
        label, lv = VARIANTS[a.holdout]
        res = evaluate(a.holdout, label, lv, HOLDOUT_FROM, None, data, out_root, risk_pct=fin["risk_pct"])
        keep = ("trades", "win_rate_pct", "profit_factor", "payoff", "pf_long", "pf_short", "max_drawdown_pct")
        with open(LEDGER, "w", encoding="utf-8") as f:
            json.dump([{"strategy": "Trend Breakout", "id": a.holdout, "label": label, "levers": lv, "run_at": stamp,
                        "risk_pct": fin["risk_pct"], "tuning": {k: fin[k] for k in keep},
                        "holdout": {k: res[k] for k in keep}, "passed": res["passed"]}], f, indent=2)
        write_board([res], out_root, f"Trend Breakout · Holdout Period {HOLDOUT_FROM} → end · Finalist {a.holdout}",
                    None, f"Risk fixed at the Tuning Period choice ({fin['risk_pct']}%).")
        print_rows([fin, res])
        print(f"\nHoldout {'PASSED' if res['passed'] else 'FAILED'} - recorded in {LEDGER}\noutput: {out_root}")
        return

    rows = [evaluate("Baseline", "Baseline", {}, *TUNING, data, out_root)]
    for v in ids:
        rows.append(evaluate(v, *VARIANTS[v], *TUNING, data, out_root))
    fin = pick_finalist(rows) if not a.only else None
    write_board(rows, out_root, f"Trend Breakout · Variants on the Tuning Period {TUNING[0]} → {TUNING[1]}", fin)
    print_rows(rows)
    print(f"\nFinalist: {fin['id'] + ' ' + fin['label'] if fin else 'none'}\noutput: {out_root}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
