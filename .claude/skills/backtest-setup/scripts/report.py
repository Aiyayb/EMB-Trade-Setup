"""
report.py - summary.json, assumptions.md and a self-contained report.html for a Backtest Run.
Called by backtest.py; stdlib only, the HTML uses inline SVG and works offline.
"""

import html
import json
import math
import os
from datetime import datetime, timezone

import risk

ASSUMPTIONS = [
    "กฎทั้งหมดมาจาก skill trade-setup (Execution 1 Long / Execution 2 Short) ไม่มีการปรับพารามิเตอร์",
    "เดินทีละแท่ง 15m; ณ ปิดแท่ง 15m เห็นเฉพาะแท่ง 4H ที่ปิดแล้ว (ไม่มี look-ahead)",
    "Sideway = |EMA8 − EMA200| / EMA200 < 3% บน 4H; HTF Setup หมดอายุเมื่อ EMA26/50 สลับ, เข้า Sideway หรือมี 4H Trigger ใหม่มาแทน",
    "4H Trigger: อย่างน้อยหนึ่งแท่งในแพทเทิร์นต้องแตะ EMA Zone (low ≤ EMA8 สำหรับ Long / high ≥ EMA8 สำหรับ Short) และเกิดหลัง 4H Wave จบ",
    "Trigger: Engulfing นับเฉพาะเมื่อมี Rejection (wick ฝั่ง rejection ≥ 50% ของ range แท่งใดแท่งหนึ่งในแพทเทิร์น); Inside bar breakout และ Doji + Engulfing ไม่ต้องมี",
    "15m Wave ต้องจบ (Zigzag พิมพ์จุดตรงข้าม) หลัง 4H Trigger ปิด — นับจากเวลาจบ ไม่สนเวลาเริ่ม",
    "Retrace วัดจากจุดสุดของ pullback ตั้งแต่ Wave จบถึงแท่ง Trigger (≥ 0.5 และไม่เกิน 1.0); เกิน 1.0 = Wave นั้นใช้ไม่ได้ รอ Wave ใหม่",
    "Fib Time 0.5 = ผ่านไปแล้วอย่างน้อย 0.5 × จำนวนแท่งของ Wave นับจากแท่งจบ Wave (นับตามแท่ง เหมือน analyzer)",
    "15m Trigger ต้องเกิดใน Entry Zone: อย่างน้อยหนึ่งแท่งในแพทเทิร์นแตะระดับ Fib 0.5 (อนุมานจากกฎ 4H ข้อ Q9)",
    "CHoCH-Retrace = 15m Wave นั้นเองทำ CHoCH ในทิศเทรด (ระหว่างจุดเริ่มถึงจุดจบ Wave) แล้วค่อย retrace — ไม่บังคับ บันทึกเป็น tag และแยกผลในรายงาน",
    "Entry = ราคาปิดแท่ง Trigger 15m; SL = low/high สุดของ pullback (ไม่มี buffer); TP = 3R; R, TP, BE คิดจากราคาปิด",
    "Size = risk % ของ equity ปัจจุบัน ÷ R (compounding); ถือได้ครั้งละ 1 Trade; 1 Trade ต่อ 1 Wave 15m",
    "ในแท่งเดียวกันชนทั้ง SL และ TP/2R → นับ SL; BE มีผลจากแท่งถัดไปหลังแตะ 2R; ถ้าเปิดแท่งทะลุ SL จะ fill ที่ราคาเปิด",
    "ถือต่อจนชน SL/TP/BE แม้ 4H trend สลับ; Trade ที่ยังเปิดตอนข้อมูลหมดปิดที่ราคาปิดสุดท้าย (reason END)",
    "Fee และ slippage คิดทั้งขาเข้าและขาออก ทุกประเภท exit (รวม TP) → Trade ที่แพ้จะเสียมากกว่า 2% เล็กน้อย",
    "Leverage ใช้แค่ flag ว่า SL ไกลกว่าระยะ liquidation (100/leverage − 0.5%) ไม่มีผลต่อ PnL",
    "Regime ของ Trade = ระยะ EMA8–EMA200 บน 4H ตอนเข้า (3–5%, 5–10%, ≥10%) เพราะช่วง Sideway ไม่มี Trade โดยกฎ",
    "ข้อมูลก่อน --from ใช้ warm-up indicator เท่านั้น ไม่เปิด Trade; Trade ที่เปิดก่อน --to ถือต่อจนจบแม้เลย --to",
    "Win = Trade ที่ปิดที่ TP เท่านั้น (BE และ SL ไม่นับเป็น Win); Profit Factor = R ที่ได้รวม ÷ R ที่เสียรวม หลังต้นทุน",
    "Risk budget: สุ่ม Trade ของ run นี้ซ้ำ (bootstrap) 5,000 ชุด แล้วเลือก risk สูงสุดใน {0.5, 0.75, 1, 1.5, 2}% "
    "ที่ Max Drawdown จริงและ Max Drawdown ที่ percentile 95 ต่ำกว่า 15% (docs/adr/0001)",
]

LEVER_ASSUMPTIONS = {
    "entry_tf": lambda v: f"Lever Entry Timeframe = {v}: Wave, Entry Zone, Trigger, CHoCH และ SL อ่านบน {v} "
                          "ด้วยกฎเดิมทุกข้อ; เข้าเมื่อแท่ง {v} ปิด แต่บริหาร SL/TP/BE ทีละแท่ง 15m",
    "sl_atr": lambda v: f"Lever SL buffer: SL = low/high สุดของ pullback ∓ {v} × ATR(14) (Wilder) ของ Entry Timeframe; "
                        "TP ยังเป็น 3R จาก R ใหม่",
    "be_at": lambda v: "Lever ไม่ใช้ Break-even: SL อยู่ที่เดิมจนชน SL หรือ TP",
    "min_trend_pct": lambda v: f"Filter trend: ระยะ EMA8–EMA200 บน 4H ตอนเข้าต้อง ≥ {v}%",
    "d1_align": lambda v: "Filter 1D: EMA26/50 ของแท่ง 1D ล่าสุดที่ปิดแล้วต้องชี้ทิศเดียวกับ 4H "
                          "(ช่วง warm-up EMA50 บน 1D ≈ ถึงกลาง พ.ย. 2021 ไม่มี Trade)",
    "drop_doji": lambda v: "Filter trigger: ข้าม Trade ที่ Trigger 15m มีแต่ Doji + Engulfing",
    "min_sl_pct": lambda v: f"Filter SL: ข้าม Trade ที่ SL ห่างจาก entry < {v}% ของราคา",
}
FILTER_NOTE = ("Filter ไม่เปลี่ยน Trade ที่เหลือ: Trade ที่ถูกกรองยังเดินเป็นเงา (ใช้ Wave นั้นไปแล้ว และกันช่อง "
               "1 Trade ที่เปิดอยู่จนกว่าจะปิด) แต่ไม่นับผล — ผลจึงเป็นเซตย่อยของ Variant ที่ไม่มี Filter")


def assumptions(cfg):
    lv = levers_of(cfg)
    out = list(ASSUMPTIONS)
    out += [LEVER_ASSUMPTIONS[k](v) for k, v in lv.items()]
    if any(k in lv for k in ("min_trend_pct", "d1_align", "drop_doji", "min_sl_pct")):
        out.append(FILTER_NOTE)
    return out


def levers_of(cfg):
    import backtest
    return backtest.levers(cfg)


# ---------------------------------------------------------------- statistics

def r_drawdown(rs):
    peak = cum = dd = 0.0
    for r in rs:
        cum += r
        peak = max(peak, cum)
        dd = max(dd, peak - cum)
    return dd


def tp_exit(t):
    return t["exit_reason"] == "TP"


def group_stats(trades, is_win=tp_exit):
    """Stats for a set of Trades. `is_win` defines a Win (EMA Pullback: a TP exit)."""
    n = len(trades)
    if not n:
        return {"trades": 0}
    rs = [t["r_multiple"] for t in trades]
    wins = [t for t in trades if is_win(t)]
    gain = sum(r for r in rs if r > 0)
    loss = -sum(r for r in rs if r < 0)
    streak = worst = 0
    for t in trades:
        streak = streak + 1 if not is_win(t) else 0
        worst = max(worst, streak)
    exits = {}
    for t in trades:
        exits[t["exit_reason"]] = exits.get(t["exit_reason"], 0) + 1
    return {
        "trades": n,
        "win_rate_pct": len(wins) / n * 100,
        "expectancy_r": sum(rs) / n,
        "gross_expectancy_r": sum(t["gross_r"] for t in trades) / n,
        "total_r": sum(rs),
        "profit_factor": gain / loss if loss else None,
        "max_drawdown_r": r_drawdown(rs),
        "max_losing_streak": worst,
        "avg_hours_held": sum(t["bars_held"] for t in trades) / n / 4,
        "avg_sl_dist_pct": sum(t["sl_dist_pct"] for t in trades) / n,
        "liq_flags": sum(1 for t in trades if t["liq_flag"]),
        "exits": exits,
    }


def by(trades, key):
    groups = {}
    for t in trades:
        groups.setdefault(key(t), []).append(t)
    return {str(k): group_stats(v) for k, v in sorted(groups.items(), key=lambda kv: str(kv[0]))}


def equity_stats(trades, balance, start_t, end_t):
    curve = [balance] + [t["equity_after"] for t in trades]
    peak, dd = curve[0], 0.0
    for v in curve:
        peak = max(peak, v)
        dd = max(dd, (peak - v) / peak * 100)
    years = max((end_t - start_t).days / 365.25, 1e-9)
    final = curve[-1]
    return {
        "start_equity": balance, "final_equity": final,
        "return_pct": (final / balance - 1) * 100,
        "cagr_pct": ((final / balance) ** (1 / years) - 1) * 100 if final > 0 else -100.0,
        "max_drawdown_pct": dd,
    }


def sideway_share(states4, bars4, start_ms, end_ms):
    """Share of 4H bars that were Sideway / long / short trend, per year, within the run window."""
    out = {}
    for st, b in zip(states4, bars4):
        if not (start_ms <= b["ts"] <= end_ms) or st["sideway"] is None:
            continue
        y = out.setdefault(b["t"][:4], {"bars": 0, "sideway": 0, "long": 0, "short": 0})
        y["bars"] += 1
        if st["sideway"]:
            y["sideway"] += 1
        else:
            y[st["bias"]] += 1
    return {y: {k: (v / d["bars"] * 100 if k != "bars" else v) for k, v in d.items()} for y, d in sorted(out.items())}


def summarize(trades, info, bars4, bars15, args, name=None):
    cfg = info["cfg"]
    start_ms = cfg["start"] if cfg["start"] is not None else bars15[0]["ts"]
    end_ms = cfg["end"] if cfg["end"] is not None else bars15[-1]["ts"]
    start_t = datetime.fromtimestamp(start_ms / 1000, timezone.utc)
    end_t = datetime.fromtimestamp(min(end_ms, bars15[-1]["ts"]) / 1000, timezone.utc)
    return {
        "run": {
            "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "from": start_t.strftime("%Y-%m-%d"), "to": end_t.strftime("%Y-%m-%d"),
            "side": cfg["side"], "balance": cfg["balance"], "risk_pct": cfg["risk_pct"], "rr": cfg["rr"],
            "be_at_r": cfg["be_at"], "be_buffer_pct": cfg["be_buffer_pct"], "fee_pct": cfg["fee_pct"],
            "slippage_pct": cfg["slippage_pct"], "leverage_flag": cfg["leverage"], "zigzag": cfg["zigzag"],
            "file_4h": os.path.basename(args.get("file_4h", "")), "file_15m": os.path.basename(args.get("file_15m", "")),
            "name": name or ("Baseline" if not levers_of(cfg) else "Variant"),
            "entry_tf": cfg["entry_tf"], "levers": levers_of(cfg),
        },
        "equity": equity_stats(trades, cfg["balance"], start_t, end_t),
        "all": group_stats(trades),
        "by_side": by(trades, lambda t: t["side"]),
        "by_year": by(trades, lambda t: t["year"]),
        "by_regime": by(trades, lambda t: t["regime"]),
        "by_choch_retrace": by(trades, lambda t: "with CHoCH" if t["choch_retrace"] else "without CHoCH"),
        "by_trigger": by(trades, lambda t: t["trigger"].split(" | ")[0]),
        "by_exit": by(trades, lambda t: t["exit_reason"]),
        "filtered": {"trades": len(info.get("skipped", [])),
                     "by_reason": {k: len(v) for k, v in _group(info.get("skipped", []), lambda t: t["filtered"]).items()}},
        "risk_budget": risk.choose_risk([t["r_multiple"] for t in trades]),
        "market_4h_by_year_pct": sideway_share(info["states4"], bars4, start_ms, end_ms),
        "assumptions": assumptions(cfg),
    }


def _group(items, key):
    out = {}
    for t in items:
        out.setdefault(key(t), []).append(t)
    return out


# ---------------------------------------------------------------- HTML

def esc(s):
    return html.escape(str(s))


def num(v, d=2, suffix=""):
    if v is None:
        return "–"
    if isinstance(v, float) and math.isinf(v):
        return "∞"
    return f"{v:,.{d}f}{suffix}"


def nice_ticks(lo, hi, n=5):
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw)
    start = math.floor(lo / step) * step
    ticks, v = [], start
    while v <= hi + step * 0.001:
        ticks.append(round(v, 10))
        v += step
    return ticks


def line_chart(cid, series, ylabel, log=False, fmt="{:,.0f}"):
    """Inline SVG line chart. series = [{name, cls, points: [(label, y)]}] sharing one x index."""
    W, H, L, R, T, B = 960, 320, 64, 24, 16, 36
    ys = [y for s in series for _, y in s["points"]]
    tf = (lambda v: math.log10(max(v, 1e-9))) if log else (lambda v: v)
    lo, hi = min(map(tf, ys)), max(map(tf, ys))
    if log:
        ticks = [10 ** e for e in range(math.floor(lo), math.ceil(hi) + 1)]
        for m in (2, 5):
            ticks += [m * 10 ** e for e in range(math.floor(lo), math.ceil(hi) + 1)]
        ticks = sorted(t for t in ticks if lo - 0.05 <= tf(t) <= hi + 0.05)
        lo, hi = min(lo, tf(ticks[0])), max(hi, tf(ticks[-1]))
    else:
        ticks = nice_ticks(lo, hi)
        lo, hi = ticks[0], ticks[-1]
    n = max(len(s["points"]) for s in series)
    x = lambda i: L + (W - L - R) * (i / max(n - 1, 1))  # noqa: E731
    y = lambda v: T + (H - T - B) * (1 - (tf(v) - lo) / ((hi - lo) or 1))  # noqa: E731
    out = [f'<svg id="{cid}" class="chart" viewBox="0 0 {W} {H}" role="img" aria-label="{esc(ylabel)}">']
    for t in ticks:
        out.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}"/>'
                   f'<text class="tick" x="{L - 8}" y="{y(t) + 4:.1f}" text-anchor="end">{esc(fmt.format(t))}</text>')
    if not log and lo < 0 < hi:
        out.append(f'<line class="zero" x1="{L}" x2="{W - R}" y1="{y(0):.1f}" y2="{y(0):.1f}"/>')
    labels = series[0]["points"]
    for k in range(0, n, max(1, n // 6)):
        out.append(f'<text class="tick" x="{x(k):.1f}" y="{H - 12}" text-anchor="middle">{esc(labels[k][0][:7])}</text>')
    for s in series:
        d = " ".join(f"{'M' if i == 0 else 'L'}{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(s["points"]))
        out.append(f'<path class="line {s["cls"]}" d="{d}"/>')
        if len(series) == 1:
            continue
        lx, lv = x(len(s["points"]) - 1), s["points"][-1][1]
        out.append(f'<text class="direct" x="{lx - 4:.1f}" y="{y(lv) - 8:.1f}" text-anchor="end">{esc(s["name"])}</text>')
    out.append(f'<line class="cross" x1="0" x2="0" y1="{T}" y2="{H - B}" visibility="hidden"/>')
    out.append(f'<rect class="hit" x="{L}" y="{T}" width="{W - L - R}" height="{H - T - B}"/></svg>')
    data = {"L": L, "R": R, "W": W, "n": n, "fmt": fmt,
            "series": [{"name": s["name"], "cls": s["cls"], "pts": s["points"]} for s in series]}
    return "".join(out), data


def table(rows, cols):
    head = "".join(f"<th>{esc(c)}</th>" for c, _ in cols)
    body = "".join("<tr>" + "".join(f"<td>{f(r)}</td>" for _, f in cols) + "</tr>" for r in rows)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


GROUP_COLS = [
    ("กลุ่ม", lambda r: esc(r[0])),
    ("Trades", lambda r: r[1]["trades"]),
    ("Win %", lambda r: num(r[1].get("win_rate_pct"), 1)),
    ("Exp. R (net)", lambda r: num(r[1].get("expectancy_r"), 3)),
    ("Exp. R (gross)", lambda r: num(r[1].get("gross_expectancy_r"), 3)),
    ("Total R", lambda r: num(r[1].get("total_r"), 1)),
    ("PF", lambda r: num(r[1].get("profit_factor"), 2)),
    ("Max DD (R)", lambda r: num(r[1].get("max_drawdown_r"), 1)),
    ("Losing streak", lambda r: r[1].get("max_losing_streak", "–")),
    ("Avg SL %", lambda r: num(r[1].get("avg_sl_dist_pct"), 2)),
    ("Exits", lambda r: esc(", ".join(f"{k} {v}" for k, v in sorted(r[1].get("exits", {}).items())))),
]


def group_table(groups):
    return table(list(groups.items()), GROUP_COLS)


CSS = """
:root{color-scheme:light;--bg:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--muted:#8a8984;
--line:#e6e5e0;--s1:#2a78d6;--s2:#eb6834;--good:#008300;--bad:#e34948}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--bg:#1a1a19;--card:#232322;
--ink:#ffffff;--ink2:#c3c2b7;--muted:#8d8c85;--line:#3a3936;--s1:#3987e5;--s2:#d95926;--good:#3fae3f;--bad:#e66767}}
:root[data-theme="dark"]{color-scheme:dark;--bg:#1a1a19;--card:#232322;--ink:#ffffff;--ink2:#c3c2b7;--muted:#8d8c85;
--line:#3a3936;--s1:#3987e5;--s2:#d95926;--good:#3fae3f;--bad:#e66767}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 system-ui,-apple-system,"Segoe UI","Noto Sans Thai",sans-serif}
main{max-width:1080px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}
h2{font-size:18px;margin:36px 0 10px}.sub{color:var(--ink2);margin:0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:20px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile .k{color:var(--ink2);font-size:13px}.tile .v{font-size:22px;font-weight:600;font-variant-numeric:tabular-nums}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;position:relative}
.chart{width:100%;height:auto;display:block}.grid{stroke:var(--line);stroke-width:1}
.zero{stroke:var(--muted);stroke-width:1}.tick{fill:var(--muted);font-size:12px}
.line{fill:none;stroke-width:2;stroke-linejoin:round}.l1{stroke:var(--s1)}.l2{stroke:var(--s2)}
.direct{fill:var(--ink2);font-size:12px;font-weight:600}.cross{stroke:var(--muted);stroke-dasharray:3 3}
.hit{fill:transparent;cursor:crosshair}
.legend{display:flex;gap:16px;color:var(--ink2);font-size:13px;margin-bottom:6px}
.legend i{display:inline-block;width:14px;height:3px;border-radius:2px;vertical-align:middle;margin-right:6px}
.tip{position:absolute;pointer-events:none;background:var(--card);border:1px solid var(--line);border-radius:8px;
padding:6px 9px;font-size:12px;color:var(--ink);box-shadow:0 2px 8px rgba(0,0,0,.12);display:none;white-space:nowrap}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{color:var(--ink2);font-weight:600}
.pos{color:var(--good)}.neg{color:var(--bad)}ol{padding-left:20px;color:var(--ink2)}li{margin:3px 0}
details summary{cursor:pointer;color:var(--ink2)}.note{color:var(--ink2);font-size:13px}
"""

JS = """
document.querySelectorAll('.card[data-chart]').forEach(card=>{
 const d=JSON.parse(card.dataset.chart),svg=card.querySelector('svg'),tip=card.querySelector('.tip'),
 cross=svg.querySelector('.cross'),hit=svg.querySelector('.hit');
 const f=v=>d.fmt.includes('+')?(v>=0?'+':'')+v.toFixed(1)+' R':v.toLocaleString(undefined,{maximumFractionDigits:0});
 hit.addEventListener('mousemove',e=>{const r=svg.getBoundingClientRect(),sx=d.W/r.width,
  px=(e.clientX-r.left)*sx,i=Math.max(0,Math.min(d.n-1,Math.round((px-d.L)/(d.W-d.L-d.R)*(d.n-1)))),
  x=d.L+(d.W-d.L-d.R)*i/Math.max(d.n-1,1);
  cross.setAttribute('x1',x);cross.setAttribute('x2',x);cross.setAttribute('visibility','visible');
  tip.innerHTML='<b>'+(i===0?'start':'#'+i+' · '+d.series[0].pts[i][0])+'</b>'+d.series.map(s=>
   '<br>'+s.name+': '+f(s.pts[i][1])).join('');
  tip.style.display='block';const cr=card.getBoundingClientRect();
  let left=e.clientX-cr.left+14;if(left>cr.width-180)left-=200;tip.style.left=left+'px';tip.style.top=(e.clientY-cr.top+10)+'px';});
 hit.addEventListener('mouseleave',()=>{tip.style.display='none';cross.setAttribute('visibility','hidden');});
});
"""


def chart_card(svg_data, legend):
    svg, data = svg_data
    leg = ("<div class='legend'>" + "".join(f"<span><i style='background:var(--{c})'></i>{esc(n)}</span>" for n, c in legend)
           + "</div>") if legend else ""
    return f"<div class='card' data-chart='{esc(json.dumps(data))}'>{leg}{svg}<div class='tip'></div></div>"


def render_html(s, trades):
    run, eq, al = s["run"], s["equity"], s["all"]
    title = f"{run['name']} {run['from']} → {run['to']} ({run['side']})"
    rb = s["risk_budget"]
    tiles = [
        ("Trades", al["trades"]), ("Win rate", num(al.get("win_rate_pct"), 1, "%")),
        ("Expectancy (net)", num(al.get("expectancy_r"), 3, " R")),
        ("Expectancy (gross)", num(al.get("gross_expectancy_r"), 3, " R")),
        ("Profit factor", num(al.get("profit_factor"), 2)),
        ("Equity", f"{num(eq['start_equity'], 0)} → {num(eq['final_equity'], 0)}"),
        ("CAGR", num(eq["cagr_pct"], 1, "%")), ("Max drawdown", num(eq["max_drawdown_pct"], 1, "%")),
        ("Risk from DD budget", num(rb["chosen_risk_pct"], 2, "%") if rb["chosen_risk_pct"] else "none fits"),
    ]
    tiles_html = "".join(f"<div class='tile'><div class='k'>{esc(k)}</div><div class='v'>{esc(v)}</div></div>"
                         for k, v in tiles)
    parts = [f"<main><h1>{esc(title)}</h1>",
             f"<p class='sub'>BTCUSDT · 4H trend + {run['entry_tf']} entry · risk {run['risk_pct']}% · "
             f"RR 1:{run['rr']:g} · "
             + (f"BE at {run['be_at_r']:g}R (+{run['be_buffer_pct']}%)" if run["be_at_r"] is not None else "no BE")
             + f" · fee {run['fee_pct']}% + slippage {run['slippage_pct']}% per side · created {esc(run['created'])}</p>",
             "<p class='sub'>Levers: " + (esc(", ".join(f"{k}={v}" for k, v in run["levers"].items())) or "none (Baseline)")
             + (f" · filtered (shadow) Trades: {s['filtered']['trades']} "
                + esc(str(s['filtered']['by_reason'])) if s["filtered"]["trades"] else "") + "</p>",
             f"<div class='tiles'>{tiles_html}</div>",
             "<h2>Risk from the Max Drawdown budget</h2><p class='note'>Max Drawdown ของ Trade ชุดนี้ที่ risk แต่ละระดับ: "
             "จริงตามลำดับเวลา และ percentile 95 จากการสุ่มซ้ำ 5,000 ชุด (ต้อง &lt; 15% ทั้งคู่)</p>" + table(rb["levels"], [
                 ("Risk", lambda r: num(r["risk_pct"], 2, "%")), ("Realized DD", lambda r: num(r["realized_dd_pct"], 1, "%")),
                 ("p95 DD", lambda r: num(r["p95_dd_pct"], 1, "%")), ("< 15%", lambda r: "✓" if r["ok"] else "✗")])]

    if trades:
        pts = [("start", run["balance"])] + [(t["exit_time_utc"], t["equity_after"]) for t in trades]
        parts.append("<h2>Equity curve (log scale)</h2>")
        parts.append(chart_card(line_chart("eq", [{"name": "Equity", "cls": "l1", "points": pts}], "Equity", log=True), None))
        net = gross = 0.0
        pn, pg = [("start", 0.0)], [("start", 0.0)]
        for t in trades:
            net += t["r_multiple"]
            gross += t["gross_r"]
            pn.append((t["exit_time_utc"], net))
            pg.append((t["exit_time_utc"], gross))
        parts.append("<h2>Cumulative R — before vs after costs</h2>"
                     "<p class='note'>ช่องว่างระหว่างสองเส้น = ต้นทุน fee + slippage ที่สะสม (วัดเป็น R)</p>")
        parts.append(chart_card(line_chart("r", [{"name": "Gross R", "cls": "l2", "points": pg},
                                                 {"name": "Net R", "cls": "l1", "points": pn}], "Cumulative R", fmt="{:+,.0f}"),
                                [("Gross R (ก่อนต้นทุน)", "s2"), ("Net R (หลังต้นทุน)", "s1")]))

    for key, head in [("by_side", "แยก Long / Short"), ("by_year", "แยกรายปี (ตามเวลาเข้า)"),
                      ("by_regime", "แยก Regime (ระยะ EMA8–EMA200 บน 4H ตอนเข้า)"),
                      ("by_choch_retrace", "มี / ไม่มี CHoCH-Retrace ก่อนเข้า"),
                      ("by_trigger", "แยกตาม 15m Trigger"), ("by_exit", "แยกตามเหตุที่ปิด")]:
        parts.append(f"<h2>{esc(head)}</h2>" + group_table(s[key]))

    mk = s["market_4h_by_year_pct"]
    parts.append("<h2>สภาพตลาด 4H ต่อปี (% ของแท่ง 4H)</h2>" + table(list(mk.items()), [
        ("ปี", lambda r: esc(r[0])), ("แท่ง 4H", lambda r: int(r[1]["bars"])),
        ("Uptrend (Long)", lambda r: num(r[1]["long"], 1, "%")), ("Downtrend (Short)", lambda r: num(r[1]["short"], 1, "%")),
        ("Sideway", lambda r: num(r[1]["sideway"], 1, "%"))]))

    def cls(v):
        return "pos" if v > 0 else "neg"
    parts.append("<h2>Trade Log</h2><details><summary>แสดงทุก Trade (" + str(len(trades)) +
                 " รายการ — รายละเอียด checklist เต็มอยู่ใน trades.csv)</summary>" + table(
        list(enumerate(trades, 1)), [
            ("#", lambda r: r[0]), ("Side", lambda r: r[1]["side"]), ("Entry (BKK)", lambda r: esc(r[1]["entry_time_bkk"])),
            ("Entry", lambda r: num(r[1]["signal_price"], 1)), ("SL", lambda r: num(r[1]["sl_initial"], 1)),
            ("TP", lambda r: num(r[1]["tp"], 1)), ("SL %", lambda r: num(r[1]["sl_dist_pct"], 2)),
            ("Trigger", lambda r: esc(r[1]["trigger"])), ("CHoCH", lambda r: "✓" if r[1]["choch_retrace"] else ""),
            ("Exit", lambda r: esc(r[1]["exit_reason"])),
            ("R", lambda r: f"<span class='{cls(r[1]['r_multiple'])}'>{r[1]['r_multiple']:+.2f}</span>"),
            ("Equity", lambda r: num(r[1]["equity_after"], 0))]) + "</details>")

    parts.append("<h2>Assumptions</h2><ol>" + "".join(f"<li>{esc(a)}</li>" for a in s["assumptions"]) + "</ol></main>")
    return (f"<!doctype html><html lang='th'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{esc(title)}</title><style>{CSS}</style></head>"
            f"<body>{''.join(parts)}<script>{JS}</script></body></html>")


def write_all(out, trades, info, bars4, bars15, args, name=None):
    s = summarize(trades, info, bars4, bars15, args, name)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(s, f, indent=2, ensure_ascii=False)
    with open(os.path.join(out, "assumptions.md"), "w", encoding="utf-8") as f:
        f.write(f"# Assumptions — {s['run']['name']} {s['run']['from']} → {s['run']['to']} ({s['run']['side']})\n\n")
        f.write("## Parameters\n\n" + "\n".join(f"- `{k}`: {v}" for k, v in s["run"].items()) + "\n\n")
        f.write("## Rule interpretations\n\n" + "\n".join(f"{i}. {a}" for i, a in enumerate(s["assumptions"], 1)) + "\n")
    with open(os.path.join(out, "report.html"), "w", encoding="utf-8") as f:
        f.write(render_html(s, trades))
    return s
