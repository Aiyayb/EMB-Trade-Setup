"""
report_tb.py - summary.json, trades.csv, assumptions.md and report.html for a Trend Breakout Backtest Run.
Reuses the statistics and page styling of backtest-setup/scripts/report.py; stdlib only.
"""

import csv
import json
import os
from datetime import datetime, timezone

import engine as E
import report  # backtest-setup/scripts (on sys.path via engine)

ASSUMPTIONS = [
    "Rules: Baseline ของ Trend Breakout (CONTEXT.md, docs/adr/0002) บวก Lever ที่ระบุใน run นี้เท่านั้น",
    "เดินทีละแท่ง 15m; ณ ปิดแท่ง 15m เห็นเฉพาะแท่ง 4H/1D ที่ปิดแล้ว (ไม่มี look-ahead)",
    "Breakout = ราคาปิด 4H เกิน Channel ของ N แท่งก่อนหน้า (ไม่รวมแท่งปัจจุบัน) และอยู่ฝั่งเดียวกับ EMA200 4H (Side Filter)",
    "Entry = ราคาปิดแท่ง Breakout; Initial Stop = entry ∓ k × ATR(14) Wilder ของแท่งนั้น; R = |entry − Initial Stop|",
    "Trailing Stop ขยับเมื่อแท่ง 4H ปิดเท่านั้น (รวมแท่ง Breakout เอง) และขยับได้ทางเดียวไปทางกำไร",
    "ตรวจ stop ทุกแท่ง 15m; แท่งที่เปิดทะลุ stop จะ fill ที่ราคาเปิด; ไม่มี TP",
    "ถือได้ครั้งละ 1 Trade (Lever pyramiding เพิ่มได้อีก 1 หน่วย); ออกแล้วเข้าใหม่ได้ทันทีเมื่อมี Breakout ถัดไป",
    "Size = risk % ของ equity ที่ปิดแล้ว ÷ R; notional สูงสุด 3 เท่าของ equity (ถ้าชนเพดาน risk จริงจะต่ำกว่าแผน)",
    "Fee และ slippage คิดทั้งขาเข้าและขาออก",
    "Funding: ใช้ประวัติ BTCUSDT perpetual ของ Binance เป็นตัวแทน (OKX มีย้อนหลังแค่ ~3 เดือน); "
    "Trade จ่าย/รับทุกรอบ funding ที่ถือข้าม คิดจากราคาปิดแท่ง 15m ณ เวลานั้น (ค่าบวก = Long จ่าย)",
    "Win = Trade ที่ R สุทธิ > 0 หลัง fee, slippage และ Funding; PF = R ที่ได้รวม ÷ R ที่เสียรวม",
    "Max Drawdown = mark-to-market (equity รวมกำไร/ขาดทุนที่ยังไม่ปิด ณ ปิดแท่ง 4H)",
    "Risk budget: risk สูงสุดใน {0.5, 0.75, 1, 1.5, 2}% ที่ Max Drawdown (mark-to-market) และ Max Drawdown "
    "percentile 95 จาก bootstrap 5,000 ชุด ต่ำกว่า 15% ทั้งคู่",
    "ข้อมูลก่อน --from ใช้ warm-up indicator เท่านั้น (EMA200 4H ≈ 33 วัน); Trade ที่เปิดก่อน --to ถือต่อจนออก",
]
LEVER_TEXT = {
    "entry_n": lambda v: f"Lever Channel: Breakout ใช้ Channel {v} แท่ง",
    "exit_n": lambda v: f"Lever Channel: Trailing Stop ใช้ Channel {v} แท่ง",
    "stop_atr": lambda v: f"Lever Initial Stop = {v} × ATR(14)",
    "chandelier_atr": lambda v: f"Lever Trailing Stop แบบ chandelier: ราคาปิดที่ดีที่สุดตั้งแต่เข้า ∓ {v} × ATR(14) แทน Channel",
    "d1_ema": lambda v: f"Filter 1D: ราคาปิด 1D ล่าสุดที่ปิดแล้วต้องอยู่ฝั่งเดียวกับ EMA{v} ของ 1D (warm-up ≈ {v} วันไม่มี Trade)",
    "adx_min": lambda v: f"Filter ADX: ADX(14) ของ 4H ตอน Breakout ต้อง ≥ {v}",
    "funding_max": lambda v: f"Filter Funding: ข้าม Long เมื่อ funding ล่าสุด ≥ {v * 100:.2f}% และ Short เมื่อ ≤ −{v * 100:.2f}%",
    "pyramid": lambda v: "Lever pyramiding: เพิ่ม 1 หน่วย (risk เท่าเดิม) เมื่อมี Breakout ทิศเดิมขณะ Trade แรกกำไร; "
                         "bootstrap risk budget ถือว่า Trade เรียงกัน (ประมาณ) ส่วน DD mark-to-market ถูกต้อง",
}
FILTER_NOTE = ("Filter ไม่เปลี่ยน Trade ที่เหลือ: Breakout ที่ถูกกรองยังเดินเป็นเงา (กันช่อง 1 Trade จนกว่าจะออก) "
               "แต่ไม่นับผล")

TRADE_COLUMNS = [
    "id", "side", "pyramid", "breakout_candle", "entry_time_utc", "entry_time_bkk", "exit_time_utc", "exit_reason",
    "r_multiple", "gross_r", "cost_r", "funding_r", "pnl", "equity_before", "equity_after",
    "signal_price", "entry_fill", "initial_stop", "stop", "exit_rule_price", "exit_fill", "r", "sl_dist_pct",
    "units", "notional", "risk_amt", "capped", "fees", "funding", "bars_held", "year",
    "channel_hi", "channel_lo", "ema", "atr", "adx", "d1_trend", "funding_rate_at_entry", "filtered",
]


def is_win(t):
    return t["r_multiple"] > 0


def stats(trades):
    s = report.group_stats(trades, is_win=is_win)
    if not trades:
        return s
    w = [t["r_multiple"] for t in trades if t["r_multiple"] > 0]
    lo = [-t["r_multiple"] for t in trades if t["r_multiple"] <= 0]
    s["payoff"] = (sum(w) / len(w)) / (sum(lo) / len(lo)) if w and lo and sum(lo) else None
    s["avg_days_held"] = s.pop("avg_hours_held") / 24
    s["funding_r_per_trade"] = sum(t["funding_r"] for t in trades) / len(trades)
    s["cost_r_per_trade"] = sum(t["cost_r"] for t in trades) / len(trades)
    s["best_r"] = max(t["r_multiple"] for t in trades)
    s.pop("liq_flags", None)
    return s


def by(trades, key):
    groups = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t)
    return {str(k): stats(v) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def assumptions(cfg):
    lv = E.levers(cfg)
    out = ASSUMPTIONS + [LEVER_TEXT[k](v) for k, v in lv.items()]
    if any(k in lv for k in ("d1_ema", "adx_min", "funding_max")):
        out.append(FILTER_NOTE)
    return out


def summarize(trades, info, bars15, name=None, risk_budget=None):
    cfg = info["cfg"]
    start_ms = cfg["start"] if cfg["start"] is not None else bars15[0]["ts"]
    end_ms = min(cfg["end"] if cfg["end"] is not None else bars15[-1]["ts"], bars15[-1]["ts"])
    start_t = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
    end_t = datetime.fromtimestamp(end_ms / 1000, timezone.utc)
    eq = report.equity_stats(trades, cfg["balance"], start_t, end_t)
    eq["closed_trade_max_drawdown_pct"] = eq.pop("max_drawdown_pct")
    eq["max_drawdown_pct"] = E.mtm_dd_pct(info["events"], cfg["risk_pct"])
    skipped = info["skipped"]
    reasons = {}
    for t in skipped:
        reasons[t["filtered"]] = reasons.get(t["filtered"], 0) + 1
    return {
        "run": {
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "strategy": "Trend Breakout",
            "name": name or ("Baseline" if not E.levers(cfg) else "Variant"),
            "from": start_t.strftime("%Y-%m-%d"), "to": end_t.strftime("%Y-%m-%d"), "side": cfg["side"],
            "balance": cfg["balance"], "risk_pct": cfg["risk_pct"], "fee_pct": cfg["fee_pct"],
            "slippage_pct": cfg["slippage_pct"], "funding": cfg["funding"], "max_notional_x": cfg["max_notional_x"],
            "rules": {k: cfg[k] for k in ("entry_n", "exit_n", "ema_n", "atr_n", "stop_atr") + E.LEVER_KEYS[3:]},
            "levers": E.levers(cfg),
        },
        "equity": eq,
        "all": stats(trades),
        "by_side": by(trades, lambda t: t["side"]),
        "by_year": by(trades, lambda t: t["year"]),
        "by_side_year": by(trades, lambda t: f"{t['year']} {t['side']}"),
        "by_exit": by(trades, lambda t: t["exit_reason"]),
        "filtered": {"trades": len(skipped), "by_reason": reasons},
        "risk_budget": risk_budget or E.choose_risk(trades, info["events"]),
        "assumptions": assumptions(cfg),
    }


GROUP_COLS = [
    ("กลุ่ม", lambda r: report.esc(r[0])),
    ("Trades", lambda r: r[1]["trades"]),
    ("Win %", lambda r: report.num(r[1].get("win_rate_pct"), 1)),
    ("PF", lambda r: report.num(r[1].get("profit_factor"), 2)),
    ("Payoff", lambda r: report.num(r[1].get("payoff"), 2)),
    ("Exp. R (net)", lambda r: report.num(r[1].get("expectancy_r"), 3)),
    ("Exp. R (gross)", lambda r: report.num(r[1].get("gross_expectancy_r"), 3)),
    ("Funding R", lambda r: report.num(r[1].get("funding_r_per_trade"), 3)),
    ("Total R", lambda r: report.num(r[1].get("total_r"), 1)),
    ("Max DD (R)", lambda r: report.num(r[1].get("max_drawdown_r"), 1)),
    ("Losing streak", lambda r: r[1].get("max_losing_streak", "–")),
    ("Avg days", lambda r: report.num(r[1].get("avg_days_held"), 1)),
    ("Avg stop %", lambda r: report.num(r[1].get("avg_sl_dist_pct"), 2)),
]


def render_html(s, trades):
    run, eq, al, rb = s["run"], s["equity"], s["all"], s["risk_budget"]
    title = f"Trend Breakout · {run['name']} {run['from']} → {run['to']}"
    tiles = [
        ("Trades", al["trades"]), ("Win rate", report.num(al.get("win_rate_pct"), 1, "%")),
        ("Profit factor", report.num(al.get("profit_factor"), 2)), ("Payoff", report.num(al.get("payoff"), 2)),
        ("Expectancy (net)", report.num(al.get("expectancy_r"), 3, " R")),
        ("Max drawdown (MTM)", report.num(eq["max_drawdown_pct"], 1, "%")),
        ("Equity", f"{report.num(eq['start_equity'], 0)} → {report.num(eq['final_equity'], 0)}"),
        ("CAGR", report.num(eq["cagr_pct"], 1, "%")),
        ("Risk from DD budget", report.num(rb["chosen_risk_pct"], 2, "%") if rb["chosen_risk_pct"] else "none fits"),
    ]
    rules = run["rules"]
    parts = [
        f"<main><h1>{report.esc(title)}</h1>",
        f"<p class='sub'>BTCUSDT perp · 4H Breakout of {rules['entry_n']}-candle Channel · Side Filter EMA{rules['ema_n']} · "
        f"Initial Stop {rules['stop_atr']:g} ATR · Trailing "
        + (f"chandelier {rules['chandelier_atr']:g} ATR" if rules["chandelier_atr"] else f"{rules['exit_n']}-candle Channel")
        + f" · risk {run['risk_pct']}% · fee {run['fee_pct']}% + slippage {run['slippage_pct']}% per side"
        + (" + Funding" if run["funding"] else " · no Funding") + f" · created {report.esc(run['created'])}</p>",
        "<p class='sub'>Levers: " + (report.esc(", ".join(f"{k}={v}" for k, v in run["levers"].items())) or "none (Baseline)")
        + (f" · filtered (shadow) Breakouts: {s['filtered']['trades']} {report.esc(str(s['filtered']['by_reason']))}"
           if s["filtered"]["trades"] else "") + "</p>",
        "<div class='tiles'>" + "".join(f"<div class='tile'><div class='k'>{report.esc(k)}</div>"
                                        f"<div class='v'>{report.esc(v)}</div></div>" for k, v in tiles) + "</div>",
        "<h2>Risk from the Max Drawdown budget</h2><p class='note'>Max Drawdown แบบ mark-to-market ตามลำดับเวลาจริง "
        "และ percentile 95 จากการสุ่มซ้ำ (ต้อง &lt; 15% ทั้งคู่)</p>" + report.table(rb["levels"], [
            ("Risk", lambda r: report.num(r["risk_pct"], 2, "%")),
            ("Realized DD (MTM)", lambda r: report.num(r["realized_dd_pct"], 1, "%")),
            ("p95 DD", lambda r: report.num(r["p95_dd_pct"], 1, "%")), ("< 15%", lambda r: "✓" if r["ok"] else "✗")]),
    ]
    if trades:
        pts = [("start", run["balance"])] + [(t["exit_time_utc"], t["equity_after"]) for t in trades]
        parts.append("<h2>Equity curve (closed Trades, log scale)</h2>")
        parts.append(report.chart_card(report.line_chart("eq", [{"name": "Equity", "cls": "l1", "points": pts}],
                                                         "Equity", log=True), None))
        net = gross = 0.0
        pn, pg = [("start", 0.0)], [("start", 0.0)]
        for t in trades:
            net += t["r_multiple"]
            gross += t["gross_r"]
            pn.append((t["exit_time_utc"], net))
            pg.append((t["exit_time_utc"], gross))
        parts.append("<h2>Cumulative R — before vs after costs and Funding</h2>")
        parts.append(report.chart_card(report.line_chart("r", [{"name": "Gross R", "cls": "l2", "points": pg},
                                                               {"name": "Net R", "cls": "l1", "points": pn}],
                                                         "Cumulative R", fmt="{:+,.0f}"),
                                       [("Gross R (ก่อนต้นทุน)", "s2"), ("Net R (หลัง fee, slippage, Funding)", "s1")]))
    for key, head in [("by_side", "แยก Long / Short"), ("by_year", "แยกรายปี (ตามเวลาเข้า)"),
                      ("by_side_year", "แยกปี × ฝั่ง"), ("by_exit", "แยกตามเหตุที่ปิด")]:
        parts.append(f"<h2>{report.esc(head)}</h2>" + report.table(list(s[key].items()), GROUP_COLS))

    def cls(v):
        return "pos" if v > 0 else "neg"
    parts.append("<h2>Trade Log</h2><details><summary>แสดงทุก Trade (" + str(len(trades)) + " รายการ — ครบใน trades.csv)"
                 "</summary>" + report.table(list(enumerate(trades, 1)), [
                     ("#", lambda r: r[0]), ("Side", lambda r: r[1]["side"] + (" +" if r[1]["pyramid"] else "")),
                     ("Entry (BKK)", lambda r: report.esc(r[1]["entry_time_bkk"])),
                     ("Entry", lambda r: report.num(r[1]["signal_price"], 1)),
                     ("Initial Stop", lambda r: report.num(r[1]["initial_stop"], 1)),
                     ("Stop %", lambda r: report.num(r[1]["sl_dist_pct"], 2)),
                     ("Exit", lambda r: report.esc(r[1]["exit_reason"])),
                     ("Exit price", lambda r: report.num(r[1]["exit_rule_price"], 1)),
                     ("Days", lambda r: report.num(r[1]["bars_held"] / 96, 1)),
                     ("R", lambda r: f"<span class='{cls(r[1]['r_multiple'])}'>{r[1]['r_multiple']:+.2f}</span>"),
                     ("Equity", lambda r: report.num(r[1]["equity_after"], 0))]) + "</details>")
    parts.append("<h2>Assumptions</h2><ol>" + "".join(f"<li>{report.esc(a)}</li>" for a in s["assumptions"]) + "</ol></main>")
    return (f"<!doctype html><html lang='th'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>Trend Breakout Backtest</title>"
            f"<style>{report.CSS}</style></head><body>{''.join(parts)}<script>{report.JS}</script></body></html>")


def write_trades(trades, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for t in trades:
            w.writerow({k: round(v, 6) if isinstance(v, float) else v for k, v in t.items()})


def write_all(out, trades, info, bars15, name=None, risk_budget=None):
    os.makedirs(out, exist_ok=True)
    write_trades(trades, os.path.join(out, "trades.csv"))
    s = summarize(trades, info, bars15, name, risk_budget)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out, "assumptions.md"), "w", encoding="utf-8") as f:
        f.write(f"# Assumptions — Trend Breakout {s['run']['name']} {s['run']['from']} → {s['run']['to']}\n\n")
        f.write("## Parameters\n\n" + "\n".join(f"- `{k}`: {v}" for k, v in s["run"].items()) + "\n\n")
        f.write("## Rule interpretations\n\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(s["assumptions"], 1)) + "\n")
    with open(os.path.join(out, "report.html"), "w", encoding="utf-8") as f:
        f.write(render_html(s, trades))
    return s
