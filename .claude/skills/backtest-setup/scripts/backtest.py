"""
backtest.py - replay the trade-setup strategy (Execution 1 Long / Execution 2 Short) over
4H + 15m candles, bar by bar with no look-ahead (stdlib only).

With no Lever options this is the Baseline. Levers (see CONTEXT.md, docs/adr/0001) turn it into a
Variant: --entry-tf 1h, --sl-atr K, --no-be, and the Filters --min-trend-pct, --d1-align,
--drop-doji, --min-sl-pct. A Filter never changes the Trades it keeps: a filtered Trade still runs
as a shadow (it uses its Wave and blocks the one open-Trade slot until it would have exited) but is
not booked. Runs that reach the Holdout Period with any Lever set need --holdout.

Rules come from the trade-setup skill; indicator logic is imported from its analyze_chart.py so
the backtest and the chart read can never drift apart (parity_check.py verifies this).

Usage:
  python backtest.py --from 2021-10-01 --to 2026-09-26
  python backtest.py --from 2024-01-01 --to 2024-12-31 --side long --balance 5000
  python backtest.py --from 2021-10-01 --to 2024-12-31 --entry-tf 1h --sl-atr 0.25
"""

import argparse
import bisect
import csv
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "trade-setup", "scripts")))
import analyze_chart as ac  # noqa: E402

M15 = 15 * 60 * 1000
H1 = 3600 * 1000
H4 = 4 * 3600 * 1000
D1 = 24 * 3600 * 1000
ENTRY_TF_MS = {"15m": M15, "1h": H1}
UTC = timezone.utc
BKK = timezone(timedelta(hours=7))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))

DEFAULTS = {
    "balance": 10000.0, "risk_pct": 2.0, "rr": 3.0, "be_at": 2.0, "be_buffer_pct": 0.1,
    "fee_pct": 0.05, "slippage_pct": 0.02, "leverage": 10.0, "mmr_pct": 0.5,
    "side": "both", "zigzag": 10, "swing": 5, "start": None, "end": None,
    # Levers: at these values the engine is the Baseline
    "entry_tf": "15m", "sl_atr": 0.0, "atr_period": 14,
    "min_trend_pct": None, "d1_align": False, "drop_doji": False, "min_sl_pct": None,
}
LEVER_DEFAULTS = {"entry_tf": "15m", "sl_atr": 0.0, "be_at": 2.0, "min_trend_pct": None,
                  "d1_align": False, "drop_doji": False, "min_sl_pct": None}
HOLDOUT_START = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

REGIMES = [(10.0, "trend >=10%"), (5.0, "trend 5-10%"), (ac.SIDEWAY_PCT, "trend 3-5%")]


class Zigzag:
    """Bar-by-bar version of analyze_chart.zigzag. State after update(i) equals
    ac.zigzag(bars[:i+1]); each point also records `born`, the bar it first appeared on."""

    def __init__(self, bars, prd):
        self.bars, self.prd, self.pts, self.d = bars, prd, [], 0

    def update(self, i):
        prd, bars = self.prd, self.bars
        if i < prd - 1:
            return
        win = bars[i - prd + 1:i + 1]
        ph = bars[i]["h"] >= max(x["h"] for x in win)
        pl = bars[i]["l"] <= min(x["l"] for x in win)
        nd = 1 if ph and not pl else -1 if pl and not ph else self.d
        if not (ph or pl) or nd == 0:
            return
        typ, price = ("H", bars[i]["h"]) if nd == 1 else ("L", bars[i]["l"])
        pts = self.pts
        if nd != self.d or not pts:
            pts.append({"i": i, "type": typ, "price": price, "born": i})
        elif (typ == "H" and price > pts[-1]["price"]) or (typ == "L" and price < pts[-1]["price"]):
            pts[-1] = {"i": i, "type": typ, "price": price, "born": pts[-1]["born"]}
        self.d = nd


def last_wave(pts, long_):
    """Index of the end point of the last completed Wave in the trade direction (as ac.execution)."""
    end_type = "H" if long_ else "L"
    for j in range(len(pts) - 2, 0, -1):
        if pts[j]["type"] == end_type:
            return j
    return None


def triggers_at(bars, i):
    """Trigger patterns completed by the close of bar i (ac.triggers on the last 3 bars)."""
    if i < 2:
        return []
    out = ac.triggers(bars[i - 2:i + 1], 1)
    for t in out:
        t["i"], t["t"] = i, bars[i]["t"]
    return out


def is_valid_trigger(t, long_):
    if t["dir"] != ("bullish" if long_ else "bearish"):
        return False
    if t["type"] in ("Bullish Engulfing", "Bearish Engulfing"):
        return t["with_rejection"]
    return True


def pattern_span(t):
    n = 3 if t["type"].startswith("Inside") else 2
    return range(t["i"] - n + 1, t["i"] + 1)


def regime_of(dist):
    for floor, name in REGIMES:
        if dist >= floor:
            return name
    return "sideway"


def fmt_ts(ms, tz=UTC):
    return datetime.fromtimestamp(ms / 1000, tz).strftime("%Y-%m-%d %H:%M")


def levers(cfg):
    """The Levers a config sets away from the Baseline, as {name: value}."""
    return {k: cfg.get(k, v) for k, v in LEVER_DEFAULTS.items() if cfg.get(k, v) != v}


def touches_holdout(cfg):
    return cfg.get("end") is None or cfg["end"] >= HOLDOUT_START


def atr(bars, n):
    """Wilder ATR(n); None until n true ranges are available."""
    out = [None] * len(bars)
    if len(bars) <= n:
        return out
    tr = [bars[0]["h"] - bars[0]["l"]] + [
        max(b["h"] - b["l"], abs(b["h"] - p["c"]), abs(b["l"] - p["c"])) for p, b in zip(bars, bars[1:])]
    a = sum(tr[1:n + 1]) / n
    out[n] = a
    for i in range(n + 1, len(bars)):
        a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def d1_bias(bars1d):
    """1D trend per daily bar: 'long' when EMA26 > EMA50, 'short' when below, None during warm-up."""
    closes = [b["c"] for b in bars1d]
    e26, e50 = ac.ema(closes, 26), ac.ema(closes, 50)
    return [None if a is None or b is None else "long" if a > b else "short" for a, b in zip(e26, e50)]


def filter_reasons(cfg, st4, setup, d1, trig, trade):
    """Filters that reject this Trade (empty list = keep it)."""
    out = []
    if cfg["min_trend_pct"] is not None and st4["dist"] < cfg["min_trend_pct"]:
        out.append("trend")
    if cfg["d1_align"] and d1 != setup["bias"]:
        out.append("d1")
    if cfg["drop_doji"] and all(t["type"].startswith("Doji") for t in trig):
        out.append("doji")
    if cfg["min_sl_pct"] is not None and trade["sl_dist_pct"] < cfg["min_sl_pct"]:
        out.append("min_sl")
    return out


# ---------------------------------------------------------------- 4H: HTF Setup state machine

def htf_pass(bars4, cfg):
    """State after the close of every 4H bar: trend, Sideway distance, last Wave and the active HTF Setup."""
    closes = [b["c"] for b in bars4]
    emas = {n: ac.ema(closes, n) for n in ac.EMA_PERIODS}
    zz = Zigzag(bars4, cfg["zigzag"])
    states, setup = [], None
    for h in range(len(bars4)):
        zz.update(h)
        e = {n: emas[n][h] for n in ac.EMA_PERIODS}
        st = {"h": h, "ema": e, "bias": None, "dist": None, "sideway": None, "wave": None, "setup": None}
        j = None
        if e[26] is not None and e[50] is not None:
            long_ = e[26] > e[50]
            st["bias"] = "long" if long_ else "short"
            j = last_wave(zz.pts, long_)
            if j is not None:
                st["wave"] = (dict(zz.pts[j - 1]), dict(zz.pts[j]))
        if e[8] is not None and e[200] is not None:
            st["dist"] = abs(e[8] - e[200]) / e[200] * 100
            st["sideway"] = st["dist"] < ac.SIDEWAY_PCT
        if setup and (setup["bias"] != st["bias"] or st["sideway"] is not False):
            setup = None
        if st["sideway"] is False and j is not None and h > zz.pts[j]["i"]:
            s0, s1 = zz.pts[j - 1], zz.pts[j]
            for t in triggers_at(bars4, h):
                if not is_valid_trigger(t, long_):
                    continue
                in_zone = any(k > s1["i"] and emas[8][k] is not None and
                              (bars4[k]["l"] <= emas[8][k] if long_ else bars4[k]["h"] >= emas[8][k])
                              for k in pattern_span(t))
                if not in_zone:
                    continue
                touched = [n for n in ac.EMA_PERIODS
                           if any(emas[n][k] is not None and
                                  (bars4[k]["l"] <= emas[n][k] if long_ else bars4[k]["h"] >= emas[n][k])
                                  for k in range(s1["i"] + 1, h + 1))]
                setup = {
                    "bias": st["bias"], "trig_h": h, "trig_type": t["type"], "trig_time": bars4[h]["t"],
                    "trig_close_ts": bars4[h]["ts"] + H4,
                    "wave_from": (bars4[s0["i"]]["t"], s0["price"]), "wave_to": (bars4[s1["i"]]["t"], s1["price"]),
                    "emas_touched": touched,
                }
                break
        st["setup"] = setup
        states.append(st)
    return states


# ---------------------------------------------------------------- trade management

def open_trade(long_, i, bar, sl, equity, cfg, bar_ms=M15):
    d = 1 if long_ else -1
    signal = bar["c"]
    r = abs(signal - sl)
    slip, fee = cfg["slippage_pct"] / 100, cfg["fee_pct"] / 100
    fill = signal * (1 + d * slip)
    risk_amt = equity * cfg["risk_pct"] / 100
    units = risk_amt / r
    sl_pct = r / signal * 100
    return {
        "side": "LONG" if long_ else "SHORT", "d": d, "entry_i": i,
        "entry_time_utc": fmt_ts(bar["ts"] + bar_ms), "entry_time_bkk": fmt_ts(bar["ts"] + bar_ms, BKK),
        "signal_price": signal, "entry_fill": fill, "sl_initial": sl, "sl": sl, "r": r,
        "sl_dist_pct": sl_pct,
        "tp": signal + d * cfg["rr"] * r,
        "be_trigger": signal + d * cfg["be_at"] * r if cfg["be_at"] is not None else None,
        "be_sl": signal * (1 + d * cfg["be_buffer_pct"] / 100),
        "units": units, "notional": units * fill, "risk_amt": risk_amt, "equity_before": equity,
        "fee_in": units * fill * fee,
        "liq_flag": sl_pct > 100 / cfg["leverage"] - cfg["mmr_pct"],
        "be_pending": False, "be_active": False, "filtered": "",
    }


def close_trade(t, i, bar, px, reason, cfg, exit_ts=None):
    d = t["d"]
    fill = px * (1 - d * cfg["slippage_pct"] / 100)
    fee_out = t["units"] * fill * cfg["fee_pct"] / 100
    t.update({
        "exit_i": i, "exit_time_utc": fmt_ts(exit_ts if exit_ts is not None else bar["ts"] + M15),
        "exit_rule_price": px, "exit_fill": fill, "exit_reason": reason, "fee_out": fee_out,
        "bars_held": i - t["entry_i"],
    })
    t["fees"] = t["fee_in"] + fee_out
    t["pnl"] = d * t["units"] * (fill - t["entry_fill"]) - t["fees"]
    t["r_multiple"] = t["pnl"] / t["risk_amt"]
    t["gross_r"] = d * (px - t["signal_price"]) / t["r"]
    return True


def manage(t, i, bar, cfg):
    """Advance an open Trade by one 15m bar. SL is checked before TP; BE applies from the bar
    after 2R is reached (never, when be_at is None). Returns True when the Trade closed on this bar."""
    d = t["d"]
    if t["be_pending"]:
        t["sl"], t["be_active"], t["be_pending"] = t["be_sl"], True, False
    if (bar["l"] <= t["sl"]) if d == 1 else (bar["h"] >= t["sl"]):
        px = min(bar["o"], t["sl"]) if d == 1 else max(bar["o"], t["sl"])
        return close_trade(t, i, bar, px, "BE" if t["be_active"] else "SL", cfg)
    if (bar["h"] >= t["tp"]) if d == 1 else (bar["l"] <= t["tp"]):
        return close_trade(t, i, bar, t["tp"], "TP", cfg)
    if t["be_trigger"] is not None and not t["be_active"] and ((bar["h"] >= t["be_trigger"]) if d == 1 else (bar["l"] <= t["be_trigger"])):
        t["be_pending"] = True
    return False


# ---------------------------------------------------------------- 15m walk

def pullback_extreme(bars, lo_i, hi_i, long_, default):
    rng = range(lo_i, hi_i + 1)
    if long_:
        return min((bars[k]["l"] for k in rng), default=default)
    return max((bars[k]["h"] for k in rng), default=default)


def wave_geometry(s0, s1):
    hi, lo = max(s0["price"], s1["price"]), min(s0["price"], s1["price"])
    return hi, lo, hi - lo


def run(bars4, bars15, cfg, probe=(), bars1h=None, bars1d=None):
    """Walk every 15m bar in time; entry logic runs whenever an Entry Timeframe bar closes and open
    Trades are always managed on 15m bars. Returns (trades, info); info['skipped'] holds the shadow
    Trades that Filters rejected and info['snapshots'] the engine state at `probe` indices."""
    cfg = dict(DEFAULTS, **cfg)
    if cfg["entry_tf"] == "1h":
        if bars1h is None:
            raise ValueError("entry_tf 1h needs bars1h")
        bars_e, e_ms = bars1h, H1
    else:
        bars_e, e_ms = bars15, M15
    if probe and bars_e is not bars15:
        raise ValueError("probe snapshots need entry_tf 15m")
    if cfg["d1_align"] and bars1d is None:
        raise ValueError("d1_align needs bars1d")
    states4 = htf_pass(bars4, cfg)
    swings = ac.label_dow(ac.find_swings(bars_e, cfg["swing"]))
    events, _ = ac.smc_events(bars_e, swings)
    choch = {"bullish": [], "bearish": []}
    for ev in events:
        if ev["kind"] == "CHoCH":
            choch[ev["dir"]].append(ev["i"])
    atr_e = atr(bars_e, cfg["atr_period"]) if cfg["sl_atr"] else None
    bias1d = d1_bias(bars1d) if cfg["d1_align"] else None
    emas15 = {n: ac.ema([b["c"] for b in bars15], n) for n in ac.EMA_PERIODS} if probe else None

    start_ts = cfg["start"] if cfg["start"] is not None else bars15[0]["ts"]
    end_ts = cfg["end"] if cfg["end"] is not None else bars15[-1]["ts"]
    probe = set(probe)
    zz = Zigzag(bars_e, cfg["zigzag"])
    equity = cfg["balance"]
    trades, skipped, trade = [], [], None
    used, dead = set(), set()
    ext_key = ext = ext_last = None
    snapshots = {}
    h = e = d = -1

    def book(t):
        nonlocal equity
        if t["filtered"]:
            skipped.append(t)
            return
        equity += t["pnl"]
        t["equity_after"] = equity
        trades.append(t)

    for i, b in enumerate(bars15):
        close_ts = b["ts"] + M15
        while h + 1 < len(bars4) and bars4[h + 1]["ts"] + H4 <= close_ts:
            h += 1
        if bias1d:
            while d + 1 < len(bars1d) and bars1d[d + 1]["ts"] + D1 <= close_ts:
                d += 1
        closed = []
        while e + 1 < len(bars_e) and bars_e[e + 1]["ts"] + e_ms <= close_ts:
            e += 1
            zz.update(e)
            closed.append(e)
        st4 = states4[h] if h >= 0 else None

        if trade and manage(trade, i, b, cfg):
            book(trade)
            trade = None

        if i in probe:
            snapshots[i] = snapshot(bars4, bars15, i, h, st4, zz, emas15)

        setup = st4["setup"] if st4 else None
        if not setup or (cfg["side"] != "both" and setup["bias"] != cfg["side"]):
            continue
        long_ = setup["bias"] == "long"
        for k in closed:
            eb = bars_e[k]
            if trade or not (start_ts <= eb["ts"] <= end_ts):
                continue
            j = last_wave(zz.pts, long_)
            if j is None:
                continue
            s0, s1 = zz.pts[j - 1], zz.pts[j]
            key = (s0["i"], s1["i"], setup["bias"])
            if key in used or key in dead:
                continue
            done_i = zz.pts[j + 1]["born"]
            if bars_e[done_i]["ts"] < setup["trig_close_ts"]:
                continue

            hi, lo, rng = wave_geometry(s0, s1)
            if rng <= 0:
                continue
            if ext_key != key:
                ext_key, ext = key, pullback_extreme(bars_e, s1["i"] + 1, k, long_, hi if long_ else lo)
            else:
                ext = (min if long_ else max)(ext, pullback_extreme(bars_e, ext_last + 1, k, long_, ext))
            ext_last = k
            deepest = (hi - ext) / rng if long_ else (ext - lo) / rng
            if deepest > 1.0:
                dead.add(key)
                continue
            since, leg = k - s1["i"], s1["i"] - s0["i"]
            if since < 0.5 * leg or deepest < ac.MIN_RETRACE:
                continue
            fib05 = hi - 0.5 * rng if long_ else lo + 0.5 * rng
            trig = [t for t in triggers_at(bars_e, k) if is_valid_trigger(t, long_) and
                    (t["pattern_low"] <= fib05 if long_ else t["pattern_high"] >= fib05)]
            if not trig:
                continue
            sl = ext
            if cfg["sl_atr"]:
                if atr_e[k] is None:
                    continue
                sl = ext - cfg["sl_atr"] * atr_e[k] if long_ else ext + cfg["sl_atr"] * atr_e[k]
            if (eb["c"] - sl if long_ else sl - eb["c"]) <= 0:
                continue

            trade = open_trade(long_, i, eb, sl, equity, cfg, e_ms)
            used.add(key)
            d1 = bias1d[d] if bias1d and d >= 0 else None
            trade["filtered"] = "/".join(filter_reasons(cfg, st4, setup, d1, trig, trade))
            dir_ = "bullish" if long_ else "bearish"
            lst = choch[dir_]
            c = bisect.bisect_right(lst, s0["i"])
            choch_i = lst[c] if c < len(lst) and lst[c] <= s1["i"] else None
            trade.update({
                "entry_tf": cfg["entry_tf"], "d1_bias": d1 or "",
                "htf_bias": setup["bias"], "htf_ema26": st4["ema"][26], "htf_ema50": st4["ema"][50],
                "htf_dist_pct": st4["dist"], "regime": regime_of(st4["dist"]),
                "htf_wave_from": setup["wave_from"][0], "htf_wave_from_price": setup["wave_from"][1],
                "htf_wave_to": setup["wave_to"][0], "htf_wave_to_price": setup["wave_to"][1],
                "htf_emas_touched": "/".join(map(str, setup["emas_touched"])),
                "htf_trigger": setup["trig_type"], "htf_trigger_time": setup["trig_time"],
                "wave_from": bars_e[s0["i"]]["t"], "wave_from_price": s0["price"],
                "wave_to": bars_e[s1["i"]]["t"], "wave_to_price": s1["price"],
                "wave_done": bars_e[done_i]["t"], "wave_bars": leg, "bars_since_wave_end": since,
                "fib_050": fib05, "deepest_retrace": deepest, "pullback_extreme": ext,
                "atr": atr_e[k] if atr_e else None,
                "trigger": " | ".join(t["type"] for t in trig), "trigger_time": eb["t"],
                "choch_retrace": choch_i is not None,
                "choch_time": bars_e[choch_i]["t"] if choch_i is not None else "",
                "year": int(eb["t"][:4]),
            })

    if trade:
        last = bars15[-1]
        close_trade(trade, len(bars15) - 1, last, last["c"], "END", cfg)
        book(trade)
    return trades, {"snapshots": snapshots, "states4": states4, "cfg": cfg, "final_equity": equity,
                    "skipped": skipped}


def snapshot(bars4, bars15, i, h, st4, zz, emas15):
    """Engine view at the close of 15m bar i, in the same terms analyze_chart reports."""
    out = {"i": i, "t": bars15[i]["t"], "h": h, "h_t": bars4[h]["t"] if h >= 0 else None,
           "ema15": {n: emas15[n][i] for n in ac.EMA_PERIODS}, "triggers15": sorted(t["type"] for t in triggers_at(bars15, i))}
    if st4:
        out.update({"ema4": st4["ema"], "bias": st4["bias"], "dist4": st4["dist"], "wave4": st4["wave"]})
    if st4 and st4["bias"]:
        long_ = st4["bias"] == "long"
        j = last_wave(zz.pts, long_)
        if j is not None:
            s0, s1 = zz.pts[j - 1], zz.pts[j]
            hi, lo, rng = wave_geometry(s0, s1)
            ext = pullback_extreme(bars15, s1["i"] + 1, i, long_, hi if long_ else lo)
            out["wave15"] = {
                "from": (bars15[s0["i"]]["t"], s0["price"]), "to": (bars15[s1["i"]]["t"], s1["price"]),
                "deepest": ((hi - ext) / rng if long_ else (ext - lo) / rng) if rng else None,
                "fib_time_0_5_passed": (i - s1["i"]) >= 0.5 * (s1["i"] - s0["i"]),
                "fib_050": hi - 0.5 * rng if long_ else lo + 0.5 * rng,
            }
    return out


# ---------------------------------------------------------------- CLI

TRADE_COLUMNS = [
    "id", "side", "entry_tf", "entry_time_utc", "entry_time_bkk", "exit_time_utc", "exit_reason", "r_multiple", "gross_r", "pnl",
    "equity_before", "equity_after", "signal_price", "entry_fill", "sl_initial", "tp", "be_trigger", "be_sl",
    "be_active", "exit_rule_price", "exit_fill", "r", "sl_dist_pct", "units", "notional", "risk_amt", "fees",
    "bars_held", "liq_flag", "year", "regime",
    "htf_bias", "htf_ema26", "htf_ema50", "htf_dist_pct", "htf_wave_from", "htf_wave_from_price",
    "htf_wave_to", "htf_wave_to_price", "htf_emas_touched", "htf_trigger", "htf_trigger_time",
    "wave_from", "wave_from_price", "wave_to", "wave_to_price", "wave_done", "wave_bars",
    "bars_since_wave_end", "fib_050", "deepest_retrace", "pullback_extreme", "atr", "d1_bias",
    "trigger", "trigger_time", "choch_retrace", "choch_time", "filtered",
]


def write_trades(trades, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TRADE_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for n, t in enumerate(trades, 1):
            row = dict(t, id=n)
            for k, v in row.items():
                if isinstance(v, float):
                    row[k] = round(v, 6)
            w.writerow(row)


def parse_date(s, end=False):
    if s is None:
        return None
    fmt = "%Y-%m-%d %H:%M" if len(s) > 10 else "%Y-%m-%d"
    dt = datetime.strptime(s, fmt).replace(tzinfo=UTC)
    if end and len(s) <= 10:
        dt += timedelta(days=1) - timedelta(milliseconds=1)
    return int(dt.timestamp() * 1000)


def add_lever_args(ap):
    g = ap.add_argument_group("Levers (all off = Baseline)")
    g.add_argument("--entry-tf", choices=sorted(ENTRY_TF_MS), default="15m", help="Entry Timeframe")
    g.add_argument("--sl-atr", type=float, default=0.0,
                   help="SL buffer beyond the pullback extreme, x ATR(14) of the Entry Timeframe")
    g.add_argument("--no-be", action="store_true", help="never move SL to break-even")
    g.add_argument("--min-trend-pct", type=float, help="Filter: 4H EMA8-EMA200 distance at entry >= this %%")
    g.add_argument("--d1-align", action="store_true", help="Filter: 1D EMA26/50 must agree with the 4H trend")
    g.add_argument("--drop-doji", action="store_true", help="Filter: skip Trades whose only Triggers are Doji + Engulfing")
    g.add_argument("--min-sl-pct", type=float, help="Filter: skip Trades whose SL is closer than this %% of price")
    ap.add_argument("--holdout", action="store_true",
                    help="allow a Variant to run on the Holdout Period (2025-01-01 onward) - see docs/adr/0001")


def lever_cfg(a):
    return {"entry_tf": a.entry_tf, "sl_atr": a.sl_atr, "be_at": None if a.no_be else DEFAULTS["be_at"],
            "min_trend_pct": a.min_trend_pct, "d1_align": a.d1_align, "drop_doji": a.drop_doji,
            "min_sl_pct": a.min_sl_pct}


def load_bars(cfg, file_4h=None, file_15m=None, file_1h=None, file_1d=None):
    """Load the candle files a config needs: {bars4, bars15, bars1h, bars1d}."""
    data = os.path.join(ROOT, "data")
    return {
        "bars4": ac.load(file_4h or os.path.join(data, "BTCUSDT_4H.csv")),
        "bars15": ac.load(file_15m or os.path.join(data, "BTCUSDT_15m.csv")),
        "bars1h": ac.load(file_1h or os.path.join(data, "BTCUSDT_1H.csv")) if cfg.get("entry_tf") == "1h" else None,
        "bars1d": ac.load(file_1d or os.path.join(data, "BTCUSDT_1D.csv")) if cfg.get("d1_align") else None,
    }


def main():
    ap = argparse.ArgumentParser(description="Backtest the trade-setup strategy on 4H + 15m candles")
    ap.add_argument("--from", dest="start", default="2021-10-01", help="first entry date (UTC), YYYY-MM-DD")
    ap.add_argument("--to", dest="end", help="last entry date (UTC), YYYY-MM-DD; default = end of data")
    ap.add_argument("--file-4h", default=os.path.join(ROOT, "data", "BTCUSDT_4H.csv"))
    ap.add_argument("--file-15m", default=os.path.join(ROOT, "data", "BTCUSDT_15m.csv"))
    ap.add_argument("--file-1h", default=os.path.join(ROOT, "data", "BTCUSDT_1H.csv"))
    ap.add_argument("--file-1d", default=os.path.join(ROOT, "data", "BTCUSDT_1D.csv"))
    ap.add_argument("--balance", type=float, default=DEFAULTS["balance"])
    ap.add_argument("--risk-pct", type=float, default=DEFAULTS["risk_pct"])
    ap.add_argument("--fee-pct", type=float, default=DEFAULTS["fee_pct"], help="per side")
    ap.add_argument("--slippage-pct", type=float, default=DEFAULTS["slippage_pct"], help="per side")
    ap.add_argument("--be-buffer-pct", type=float, default=DEFAULTS["be_buffer_pct"])
    ap.add_argument("--leverage", type=float, default=DEFAULTS["leverage"], help="only for the liquidation flag")
    ap.add_argument("--side", choices=["long", "short", "both"], default="both")
    ap.add_argument("--out", help="output folder; default backtests/<timestamp>-<side>")
    add_lever_args(ap)
    a = ap.parse_args()

    cfg = {"balance": a.balance, "risk_pct": a.risk_pct, "fee_pct": a.fee_pct, "slippage_pct": a.slippage_pct,
           "be_buffer_pct": a.be_buffer_pct, "leverage": a.leverage, "side": a.side,
           "start": parse_date(a.start), "end": parse_date(a.end, end=True), **lever_cfg(a)}
    if levers(cfg) and touches_holdout(cfg) and not a.holdout:
        ap.error("this Variant's window reaches the Holdout Period (2025-01-01 onward); end it with "
                 "--to 2024-12-31, or pass --holdout for the single Finalist run (docs/adr/0001)")
    bars = load_bars(cfg, a.file_4h, a.file_15m, a.file_1h, a.file_1d)
    trades, info = run(bars["bars4"], bars["bars15"], cfg, bars1h=bars["bars1h"], bars1d=bars["bars1d"])

    out = a.out or os.path.join(ROOT, "backtests", datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + a.side)
    os.makedirs(out, exist_ok=True)
    write_trades(trades, os.path.join(out, "trades.csv"))
    try:
        import report
        report.write_all(out, trades, info, bars["bars4"], bars["bars15"], vars(a))
    except ImportError:
        pass
    n = len(trades)
    wins = sum(1 for t in trades if t["exit_reason"] == "TP")
    print(f"trades {n} (filtered {len(info['skipped'])}) | win rate {wins / n * 100 if n else 0:.1f}% | "
          f"expectancy {sum(t['r_multiple'] for t in trades) / n if n else 0:+.3f}R | "
          f"equity {cfg['balance']:,.2f} -> {info['final_equity']:,.2f}")
    print(f"output: {out}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
