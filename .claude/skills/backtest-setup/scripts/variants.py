"""
variants.py - run the pre-registered Variants on the Tuning Period, check each against the
Acceptance Bar and pick the Finalist; or run that one Finalist once on the Holdout Period.
Process and limits: docs/adr/0001-evaluate-variants-against-acceptance-bar.md. Stdlib only.

Usage:
  python variants.py                     # Baseline + every registered Variant on the Tuning Period
  python variants.py --only V01 V04      # a subset (still Tuning Period only)
  python variants.py --holdout V07       # the single Finalist run on the Holdout Period (once, ever)
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as bt  # noqa: E402
import report  # noqa: E402
import risk  # noqa: E402

TUNING = ("2021-10-01", "2024-12-31")
HOLDOUT_FROM = "2025-01-01"
SEARCH_BUDGET = 20
PF_BAR, PF_STRETCH, MIN_TRADES, TIE_PF = 1.5, 3.0, 100, 0.1
LEDGER = os.path.join(bt.ROOT, "docs", "holdout-ledger.json")

# Registered before any Variant was run. Append only: never edit or delete a row once it has run,
# and every row counts against the Search Budget. Combinations of the best single Levers go below.
VARIANTS = {
    "V01": ("Entry Timeframe 1h", {"entry_tf": "1h"}),
    "V02": ("SL + 0.25 ATR", {"sl_atr": 0.25}),
    "V03": ("SL + 0.5 ATR", {"sl_atr": 0.5}),
    "V04": ("no Break-even", {"be_at": None}),
    "V05": ("trend >= 5%", {"min_trend_pct": 5.0}),
    "V06": ("trend >= 7%", {"min_trend_pct": 7.0}),
    "V07": ("trend >= 10%", {"min_trend_pct": 10.0}),
    "V08": ("1D trend aligned", {"d1_align": True}),
    "V09": ("no Doji + Engulfing", {"drop_doji": True}),
    "V10": ("min SL 0.5%", {"min_sl_pct": 0.5}),
    "V11": ("min SL 0.75%", {"min_sl_pct": 0.75}),
    "V12": ("min SL 1.0%", {"min_sl_pct": 1.0}),
}
assert len(VARIANTS) <= SEARCH_BUDGET, "Search Budget exceeded - the Variant approach has failed (docs/adr/0001)"


def load_all():
    return bt.load_bars({"entry_tf": "1h", "d1_align": True})


def evaluate(vid, label, lv, start, end, bars, out_root, risk_pct=None):
    """Run one config; size it from the DD budget (or at `risk_pct` when given) and check the Acceptance Bar."""
    cfg = {"start": bt.parse_date(start), "end": bt.parse_date(end, end=True) if end else None, **lv}
    trades, _ = bt.run(bars["bars4"], bars["bars15"], cfg, bars1h=bars["bars1h"], bars1d=bars["bars1d"])
    rb = risk.choose_risk([t["r_multiple"] for t in trades])
    use = risk_pct if risk_pct is not None else (rb["chosen_risk_pct"] or risk.LADDER[0])
    cfg["risk_pct"] = use
    trades, info = bt.run(bars["bars4"], bars["bars15"], cfg, bars1h=bars["bars1h"], bars1d=bars["bars1d"])
    out = os.path.join(out_root, vid)
    os.makedirs(out, exist_ok=True)
    bt.write_trades(trades, os.path.join(out, "trades.csv"))
    s = report.write_all(out, trades, info, bars["bars4"], bars["bars15"], {}, f"{vid} {label}")

    al, sides = s["all"], s["by_side"]
    pf = al.get("profit_factor") or 0.0
    dd = s["equity"]["max_drawdown_pct"]
    checks = {
        f"PF >= {PF_BAR}": pf >= PF_BAR,
        "Max Drawdown < 15%": dd < risk.DD_LIMIT_PCT and (risk_pct is not None or rb["chosen_risk_pct"] is not None),
    }
    if risk_pct is None:
        checks[f"Trades >= {MIN_TRADES}"] = al["trades"] >= MIN_TRADES
    return {
        "id": vid, "label": label, "levers": lv, "from": start, "to": end or s["run"]["to"],
        "trades": al["trades"], "filtered": s["filtered"]["trades"],
        "win_rate_pct": al.get("win_rate_pct"), "profit_factor": al.get("profit_factor"),
        "expectancy_r": al.get("expectancy_r"), "gross_expectancy_r": al.get("gross_expectancy_r"),
        "avg_sl_dist_pct": al.get("avg_sl_dist_pct"), "max_losing_streak": al.get("max_losing_streak"),
        "pf_long": sides.get("LONG", {}).get("profit_factor"), "pf_short": sides.get("SHORT", {}).get("profit_factor"),
        "risk_pct": use, "risk_budget": rb, "max_drawdown_pct": dd, "cagr_pct": s["equity"]["cagr_pct"],
        "checks": checks, "passed": all(checks.values()), "stretch": pf >= PF_STRETCH,
        "report": os.path.relpath(os.path.join(out, "report.html"), out_root).replace("\\", "/"),
    }


def pick_finalist(rows):
    ok = [r for r in rows if r["passed"] and r["id"] != "Baseline"]
    if not ok:
        return None
    best = max(r["profit_factor"] for r in ok)
    near = [r for r in ok if r["profit_factor"] >= best - TIE_PF]
    return min(near, key=lambda r: (len(r["levers"]), -r["profit_factor"]))


# ---------------------------------------------------------------- output

def fmt(v, d=2, suf=""):
    return report.num(v, d, suf)


COLS = [
    ("Variant", lambda r: f"<a href='{report.esc(r['report'])}'>{report.esc(r['id'])}</a>"),
    ("Levers", lambda r: report.esc(r["label"])),
    ("Trades", lambda r: r["trades"]), ("Filtered", lambda r: r["filtered"]),
    ("Win %", lambda r: fmt(r["win_rate_pct"], 1)),
    ("PF (net)", lambda r: fmt(r["profit_factor"])),
    ("PF Long", lambda r: fmt(r["pf_long"])), ("PF Short", lambda r: fmt(r["pf_short"])),
    ("Exp. R net", lambda r: fmt(r["expectancy_r"], 3)), ("Exp. R gross", lambda r: fmt(r["gross_expectancy_r"], 3)),
    ("Avg SL %", lambda r: fmt(r["avg_sl_dist_pct"])),
    ("Risk", lambda r: fmt(r["risk_pct"], 2, "%") + ("" if r["risk_budget"]["chosen_risk_pct"] else " ✗")),
    ("Max DD", lambda r: fmt(r["max_drawdown_pct"], 1, "%")),
    ("Pass", lambda r: "✓" if r["passed"] else "✗ " + ", ".join(k for k, v in r["checks"].items() if not v)),
]


def write_board(rows, out_root, title, finalist=None, note=""):
    with open(os.path.join(out_root, "leaderboard.json"), "w", encoding="utf-8") as f:
        json.dump({"title": title, "finalist": finalist and finalist["id"], "rows": rows}, f, indent=2, ensure_ascii=False)
    used = sum(1 for r in rows if r["id"] != "Baseline")
    tiles = [("Variants run", f"{used} (budget {SEARCH_BUDGET}, registered {len(VARIANTS)})"),
             ("Passed", sum(1 for r in rows if r["passed"] and r["id"] != "Baseline")),
             ("Finalist", finalist["id"] + " " + finalist["label"] if finalist else "none")]
    body = (f"<main><h1>{report.esc(title)}</h1><p class='sub'>Acceptance Bar (net of costs): PF ≥ {PF_BAR} · "
            f"Max Drawdown &lt; 15% at the risk chosen from the DD budget · ≥ {MIN_TRADES} Trades · RR 1:3 · "
            f"Stretch Target PF {PF_STRETCH}. {report.esc(note)}</p><div class='tiles'>"
            + "".join(f"<div class='tile'><div class='k'>{report.esc(k)}</div><div class='v'>{report.esc(v)}</div></div>"
                      for k, v in tiles)
            + "</div><h2>Leaderboard</h2>" + report.table(rows, COLS) + "</main>")
    with open(os.path.join(out_root, "leaderboard.html"), "w", encoding="utf-8") as f:
        f.write(f"<!doctype html><html lang='th'><head><meta charset='utf-8'><meta name='viewport' "
                f"content='width=device-width,initial-scale=1'><title>Variant Leaderboard</title>"
                f"<style>{report.CSS}</style></head><body>{body}</body></html>")


def print_rows(rows):
    print(f"{'id':<9}{'levers':<22}{'trades':>7}{'win%':>7}{'PF':>6}{'expR':>8}{'SL%':>6}{'risk':>6}{'DD%':>7}  pass")
    for r in rows:
        print(f"{r['id']:<9}{r['label'][:21]:<22}{r['trades']:>7}{r['win_rate_pct'] or 0:>7.1f}"
              f"{r['profit_factor'] or 0:>6.2f}{r['expectancy_r'] or 0:>+8.3f}{r['avg_sl_dist_pct'] or 0:>6.2f}"
              f"{r['risk_pct']:>6.2f}{r['max_drawdown_pct']:>7.1f}  {'PASS' if r['passed'] else 'fail'}")


# ---------------------------------------------------------------- CLI

def read_ledger():
    if not os.path.exists(LEDGER):
        return []
    with open(LEDGER, encoding="utf-8") as f:
        return json.load(f)


def main():
    ap = argparse.ArgumentParser(description="Run registered Variants against the Acceptance Bar")
    ap.add_argument("--only", nargs="+", metavar="ID", help="run only these Variant ids on the Tuning Period")
    ap.add_argument("--holdout", metavar="ID", help="run this Finalist once on the Holdout Period")
    ap.add_argument("--out", help="output folder; default backtests/variants-<timestamp>")
    a = ap.parse_args()

    ids = a.only or list(VARIANTS)
    bad = [i for i in ids + ([a.holdout] if a.holdout else []) if i not in VARIANTS]
    if bad:
        ap.error(f"unknown Variant id(s) {bad}; register them in VARIANTS first (they count against the Search Budget)")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_root = a.out or os.path.join(bt.ROOT, "backtests", ("holdout-" if a.holdout else "variants-") + stamp)
    os.makedirs(out_root, exist_ok=True)
    bars = load_all()

    if a.holdout:
        ledger = read_ledger()
        if ledger:
            ap.error(f"the Holdout Period was already used by {ledger[0]['id']} on {ledger[0]['run_at']} "
                     f"({LEDGER}); it cannot be used again (docs/adr/0001)")
        label, lv = VARIANTS[a.holdout]
        tune = evaluate(a.holdout, label, lv, *TUNING, bars, os.path.join(out_root, "tuning"))
        rows = [evaluate("Baseline", "Baseline", {}, *TUNING, bars, os.path.join(out_root, "tuning"))]
        rows += [evaluate(v, *VARIANTS[v], *TUNING, bars, os.path.join(out_root, "tuning")) for v in VARIANTS if v != a.holdout]
        fin = pick_finalist(rows + [tune])
        if not fin or fin["id"] != a.holdout:
            ap.error(f"{a.holdout} is not the Finalist on the Tuning Period (Finalist: {fin and fin['id']})")
        res = evaluate(a.holdout, label, lv, HOLDOUT_FROM, None, bars, out_root, risk_pct=tune["risk_pct"])
        os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
        with open(LEDGER, "w", encoding="utf-8") as f:
            json.dump([{"id": a.holdout, "label": label, "levers": lv, "run_at": stamp, "risk_pct": tune["risk_pct"],
                        "tuning": {k: tune[k] for k in ("trades", "win_rate_pct", "profit_factor", "max_drawdown_pct")},
                        "holdout": {k: res[k] for k in ("trades", "win_rate_pct", "profit_factor", "max_drawdown_pct")},
                        "passed": res["passed"]}], f, indent=2)
        write_board([res], out_root, f"Holdout Period {HOLDOUT_FROM} → end · Finalist {a.holdout}", None,
                    f"Risk fixed at the Tuning Period choice ({tune['risk_pct']}%).")
        print_rows([tune, res])
        print(f"\nHoldout {'PASSED' if res['passed'] else 'FAILED'} - recorded in {LEDGER}\noutput: {out_root}")
        return

    rows = [evaluate("Baseline", "Baseline", {}, *TUNING, bars, out_root)]
    for v in ids:
        rows.append(evaluate(v, *VARIANTS[v], *TUNING, bars, out_root))
        print(f"  {v} done", flush=True)
    fin = pick_finalist(rows) if not a.only else None
    write_board(rows, out_root, f"Variants on the Tuning Period {TUNING[0]} → {TUNING[1]}", fin)
    print_rows(rows)
    print(f"\nFinalist: {fin['id'] + ' ' + fin['label'] if fin else 'none'}\noutput: {out_root}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
