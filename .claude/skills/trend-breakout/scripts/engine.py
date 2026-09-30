"""
engine.py - Trend Breakout: rules, indicators and the bar-by-bar backtest (stdlib only).

The rules live in one place (breakout / initial_stop / trail_level / filter_reasons) and are used by
both the backtest below and the live chart check (check.py), so the two can never drift apart.

Baseline (CONTEXT.md, docs/adr/0002):
  Breakout      a 4H candle closes beyond the 20-candle Channel of the previous closed candles
  Side Filter   Long only above 4H EMA200, Short only below
  Entry         at the Breakout candle's close
  Initial Stop  2 x ATR(14) of 4H from entry; defines R
  Trailing Stop the more protective of the Initial Stop and the opposite 10-candle Channel,
                moved only toward profit and only when a 4H candle closes
  Stops are checked on 15m candles; one Trade at a time; size = risk % of equity / R,
  notional capped at 3x equity; fees + slippage on both legs; Funding on every event held across.
"""

import csv
import os
import sys
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "backtest-setup", "scripts")))
import risk  # noqa: E402

M15 = 15 * 60 * 1000
H4 = 4 * 3600 * 1000
D1 = 24 * 3600 * 1000
UTC = timezone.utc
BKK = timezone(timedelta(hours=7))
HOLDOUT_START = int(datetime(2025, 1, 1, tzinfo=UTC).timestamp() * 1000)

DEFAULTS = {
    "balance": 10000.0, "risk_pct": 0.75, "fee_pct": 0.05, "slippage_pct": 0.02, "max_notional_x": 3.0,
    "funding": True, "side": "both", "start": None, "end": None,
    # Baseline rules; Levers change these
    "entry_n": 20, "exit_n": 10, "ema_n": 200, "atr_n": 14, "stop_atr": 2.0,
    "chandelier_atr": None, "d1_ema": None, "adx_min": None, "adx_n": 14, "funding_max": None, "pyramid": False,
}
LEVER_KEYS = ("entry_n", "exit_n", "stop_atr", "chandelier_atr", "d1_ema", "adx_min", "funding_max", "pyramid")


def levers(cfg):
    """The Levers a config sets away from the Baseline, as {name: value}."""
    return {k: cfg[k] for k in LEVER_KEYS if k in cfg and cfg[k] != DEFAULTS[k]}


def touches_holdout(cfg):
    return cfg.get("end") is None or cfg["end"] >= HOLDOUT_START


# ---------------------------------------------------------------- data

def load(path, until_ms=None):
    """Candles from a data/ CSV (timestamp = open time, Unix ms UTC), oldest first."""
    bars = []
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            ts = int(float(r["timestamp"]))
            if until_ms is not None and ts > until_ms:
                continue
            bars.append({"ts": ts, "t": r["open_time_utc"], "o": float(r["open"]), "h": float(r["high"]),
                         "l": float(r["low"]), "c": float(r["close"])})
    bars.sort(key=lambda b: b["ts"])
    return bars


def load_funding(path):
    """[(funding time ms, rate)] - rate > 0 means Longs pay Shorts."""
    with open(path, newline="", encoding="utf-8") as f:
        return sorted((int(r["timestamp"]), float(r["funding_rate"])) for r in csv.DictReader(f))


def data_path(name):
    return os.path.join(ROOT, "data", name)


def load_all(cfg=None):
    """{bars4, bars15, bars1d, funding} for a config (1D only when a Lever needs it)."""
    cfg = cfg or {}
    return {
        "bars4": load(data_path("BTCUSDT_4H.csv")),
        "bars15": load(data_path("BTCUSDT_15m.csv")),
        "bars1d": load(data_path("BTCUSDT_1D.csv")) if cfg.get("d1_ema", True) else None,
        "funding": load_funding(data_path("BTCUSDT_funding.csv")),
    }


def parse_date(s, end=False):
    if s is None:
        return None
    fmt = "%Y-%m-%d %H:%M" if len(s) > 10 else "%Y-%m-%d"
    dt = datetime.strptime(s, fmt).replace(tzinfo=UTC)
    if end and len(s) <= 10:
        dt += timedelta(days=1) - timedelta(milliseconds=1)
    return int(dt.timestamp() * 1000)


def fmt_ts(ms, tz=UTC):
    return datetime.fromtimestamp(ms / 1000, tz).strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------- indicators (value at i uses bars[:i+1] only)

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


def rma(values, n, first=1):
    """Wilder smoothing of values[first:], seeded with the mean of the first n."""
    out = [None] * len(values)
    if len(values) < first + n:
        return out
    a = sum(values[first:first + n]) / n
    out[first + n - 1] = a
    for i in range(first + n, len(values)):
        a = (a * (n - 1) + values[i]) / n
        out[i] = a
    return out


def true_range(bars):
    return [bars[0]["h"] - bars[0]["l"]] + [
        max(b["h"] - b["l"], abs(b["h"] - p["c"]), abs(b["l"] - p["c"])) for p, b in zip(bars, bars[1:])]


def atr(bars, n):
    return rma(true_range(bars), n)


def adx(bars, n):
    """Wilder ADX(n)."""
    pdm, ndm = [0.0], [0.0]
    for p, b in zip(bars, bars[1:]):
        up, dn = b["h"] - p["h"], p["l"] - b["l"]
        pdm.append(up if up > dn and up > 0 else 0.0)
        ndm.append(dn if dn > up and dn > 0 else 0.0)
    tr, sp, sn = rma(true_range(bars), n), rma(pdm, n), rma(ndm, n)
    dx = [None] * len(bars)
    for i in range(len(bars)):
        if tr[i]:
            pdi, ndi = 100 * sp[i] / tr[i], 100 * sn[i] / tr[i]
            dx[i] = 100 * abs(pdi - ndi) / (pdi + ndi) if pdi + ndi else 0.0
    start = next((i for i, v in enumerate(dx) if v is not None), len(dx))
    out = [None] * len(bars)
    if len(bars) >= start + n:
        a = sum(dx[start:start + n]) / n
        out[start + n - 1] = a
        for i in range(start + n, len(bars)):
            a = (a * (n - 1) + dx[i]) / n
            out[i] = a
    return out


def indicators(bars4, cfg):
    """Per-4H-candle values: EMA, ATR, ADX, the Breakout Channel of the previous entry_n candles and the
    Trailing Channel of the last exit_n candles (including the current one)."""
    n, m = cfg["entry_n"], cfg["exit_n"]
    hs, ls = [b["h"] for b in bars4], [b["l"] for b in bars4]
    ln = len(bars4)
    return {
        "ema": ema([b["c"] for b in bars4], cfg["ema_n"]),
        "atr": atr(bars4, cfg["atr_n"]),
        "adx": adx(bars4, cfg["adx_n"]) if cfg["adx_min"] is not None else None,
        "ch_hi": [max(hs[i - n:i]) if i >= n else None for i in range(ln)],
        "ch_lo": [min(ls[i - n:i]) if i >= n else None for i in range(ln)],
        "tr_hi": [max(hs[i - m + 1:i + 1]) if i >= m - 1 else None for i in range(ln)],
        "tr_lo": [min(ls[i - m + 1:i + 1]) if i >= m - 1 else None for i in range(ln)],
    }


def d1_trend(bars1d, n):
    """Per closed 1D candle: 'long' if close > EMA(n), 'short' if below, None during warm-up."""
    e = ema([b["c"] for b in bars1d], n)
    return [None if v is None else "long" if b["c"] > v else "short" for b, v in zip(bars1d, e)]


# ---------------------------------------------------------------- rules

def breakout(ind, bars4, i):
    """'long' / 'short' if 4H candle i is a Breakout the Side Filter allows, else None."""
    c, e, a = bars4[i]["c"], ind["ema"][i], ind["atr"][i]
    hi, lo = ind["ch_hi"][i], ind["ch_lo"][i]
    if None in (e, a, hi, lo):
        return None
    if c > hi and c > e:
        return "long"
    if c < lo and c < e:
        return "short"
    return None


def initial_stop(ind, bars4, i, d, cfg):
    return bars4[i]["c"] - d * cfg["stop_atr"] * ind["atr"][i]


def trail_level(ind, i, t, cfg):
    """Where the Trailing Stop wants to be after 4H candle i closes (before the only-toward-profit rule)."""
    if cfg["chandelier_atr"] is not None:
        return t["best_close"] - t["d"] * cfg["chandelier_atr"] * ind["atr"][i]
    return ind["tr_lo"][i] if t["d"] == 1 else ind["tr_hi"][i]


def trail(ind, bars4, i, t, cfg):
    """Move the Trailing Stop at the close of 4H candle i (only toward profit)."""
    c = bars4[i]["c"]
    t["best_close"] = max(t["best_close"], c) if t["d"] == 1 else min(t["best_close"], c)
    lvl = trail_level(ind, i, t, cfg)
    if lvl is not None:
        t["stop"] = max(t["stop"], lvl) if t["d"] == 1 else min(t["stop"], lvl)


def filter_reasons(cfg, side, ctx):
    """Filters that reject this Breakout (empty list = take it). ctx: adx, d1, funding_rate."""
    out = []
    if cfg["d1_ema"] is not None and ctx.get("d1") != side:
        out.append("d1")
    if cfg["adx_min"] is not None and (ctx.get("adx") is None or ctx["adx"] < cfg["adx_min"]):
        out.append("adx")
    fr = ctx.get("funding_rate")
    if cfg["funding_max"] is not None and fr is not None:
        if (side == "long" and fr >= cfg["funding_max"]) or (side == "short" and fr <= -cfg["funding_max"]):
            out.append("funding")
    return out


def position(entry, stop, equity, cfg):
    """Size for a Trade: {units, notional, risk_amt, capped}."""
    fill = entry * (1 + (1 if stop < entry else -1) * cfg["slippage_pct"] / 100)
    risk_amt = equity * cfg["risk_pct"] / 100
    units = risk_amt / abs(entry - stop)
    cap = cfg["max_notional_x"] * equity / fill
    return {"units": min(units, cap), "planned_units": units, "notional": min(units, cap) * fill,
            "risk_amt": risk_amt, "capped": units > cap, "fill": fill}


# ---------------------------------------------------------------- trade lifecycle

def open_trade(d, h, i, bars4, ind, equity, cfg, ctx, tid, pyramid=False):
    b = bars4[h]
    stop = initial_stop(ind, bars4, h, d, cfg)
    pos = position(b["c"], stop, equity, cfg)
    entry_ts = b["ts"] + H4
    t = {
        "id": tid, "side": "LONG" if d == 1 else "SHORT", "d": d, "entry_i": i, "entry_h": h, "entry_ts": entry_ts,
        "entry_time_utc": fmt_ts(entry_ts), "entry_time_bkk": fmt_ts(entry_ts, BKK), "breakout_candle": b["t"],
        "signal_price": b["c"], "entry_fill": pos["fill"], "initial_stop": stop, "stop": stop,
        "r": abs(b["c"] - stop), "sl_dist_pct": abs(b["c"] - stop) / b["c"] * 100,
        "units": pos["units"], "planned_units": pos["planned_units"], "notional": pos["notional"],
        "risk_amt": pos["risk_amt"], "capped": pos["capped"], "equity_before": equity,
        "fee_in": pos["units"] * pos["fill"] * cfg["fee_pct"] / 100, "funding": 0.0, "best_close": b["c"],
        "channel_hi": ind["ch_hi"][h], "channel_lo": ind["ch_lo"][h], "ema": ind["ema"][h], "atr": ind["atr"][h],
        "adx": ctx.get("adx"), "d1_trend": ctx.get("d1") or "", "funding_rate_at_entry": ctx.get("funding_rate"),
        "pyramid": pyramid, "filtered": "", "liq_flag": False, "year": int(b["t"][:4]),
    }
    trail(ind, bars4, h, t, cfg)
    return t


def close_trade(t, i, bar, px, cfg, reason=None, exit_ts=None):
    d = t["d"]
    fill = px * (1 - d * cfg["slippage_pct"] / 100)
    fee_out = t["units"] * fill * cfg["fee_pct"] / 100
    t.update({
        "exit_i": i, "exit_time_utc": fmt_ts(exit_ts if exit_ts is not None else bar["ts"] + M15),
        "exit_rule_price": px, "exit_fill": fill, "fee_out": fee_out, "bars_held": i - t["entry_i"],
        "exit_reason": reason or ("Initial Stop" if t["stop"] == t["initial_stop"] else "Trailing Stop"),
    })
    t["fees"] = t["fee_in"] + fee_out
    t["pnl"] = d * t["units"] * (fill - t["entry_fill"]) - t["fees"] - t["funding"]
    t["r_multiple"] = t["pnl"] / t["risk_amt"]
    scale = t["units"] / t["planned_units"]
    t["gross_r"] = d * (px - t["signal_price"]) / t["r"] * scale
    t["funding_r"] = t["funding"] / t["risk_amt"]
    t["cost_r"] = t["gross_r"] - t["r_multiple"] - t["funding_r"]


def stop_hit(t, bar):
    """Exit price if the 15m bar touches the stop (a bar opening through it fills at the open), else None."""
    if t["d"] == 1 and bar["l"] <= t["stop"]:
        return min(bar["o"], t["stop"])
    if t["d"] == -1 and bar["h"] >= t["stop"]:
        return max(bar["o"], t["stop"])
    return None


def open_r(t, price):
    """Unrealized R of an open Trade at `price`, after entry fee and Funding so far."""
    return (t["d"] * t["units"] * (price - t["entry_fill"]) - t["fee_in"] - t["funding"]) / t["risk_amt"]


# ---------------------------------------------------------------- backtest

def run(bars4, bars15, cfg, bars1d=None, funding=None):
    """Walk every 15m candle: stops are checked on it, Funding is charged at its events, and when a 4H candle
    closes the Trailing Stops move and Breakouts are taken. Returns (trades, info).
    info['skipped'] = shadow Trades a Filter rejected; info['events'] = open/close/mark stream for
    mark-to-market drawdown at any risk %."""
    cfg = dict(DEFAULTS, **cfg)
    if cfg["d1_ema"] is not None and bars1d is None:
        raise ValueError("d1_ema needs bars1d")
    ind = indicators(bars4, cfg)
    d1 = d1_trend(bars1d, cfg["d1_ema"]) if cfg["d1_ema"] is not None else None
    fund = funding or []
    start_ts = cfg["start"] if cfg["start"] is not None else bars15[0]["ts"]
    end_ts = cfg["end"] if cfg["end"] is not None else bars15[-1]["ts"]

    equity = cfg["balance"]
    trades, skipped, open_, events = [], [], [], []
    h = dd = -1
    fi, last_rate, tid = 0, None, 0

    def book(t):
        nonlocal equity
        if t["filtered"]:
            skipped.append(t)
            return
        equity += t["pnl"]
        t["equity_after"] = equity
        trades.append(t)
        events.append(("close", t["id"], t["r_multiple"]))

    for i, b in enumerate(bars15):
        close_ts = b["ts"] + M15
        for t in list(open_):
            px = stop_hit(t, b)
            if px is not None:
                close_trade(t, i, b, px, cfg)
                open_.remove(t)
                book(t)
        while fi < len(fund) and fund[fi][0] <= close_ts:
            ts, rate = fund[fi]
            fi += 1
            last_rate = rate
            if cfg["funding"]:
                for t in open_:
                    if t["entry_ts"] < ts:
                        t["funding"] += t["d"] * rate * t["units"] * b["c"]
        if d1 is not None:
            while dd + 1 < len(bars1d) and bars1d[dd + 1]["ts"] + D1 <= close_ts:
                dd += 1
        while h + 1 < len(bars4) and bars4[h + 1]["ts"] + H4 <= close_ts:
            h += 1
            for t in open_:
                trail(ind, bars4, h, t, cfg)
            side = breakout(ind, bars4, h)
            if side and (cfg["side"] in ("both", side)) and start_ts <= bars4[h]["ts"] <= end_ts:
                d = 1 if side == "long" else -1
                ctx = {"adx": ind["adx"][h] if ind["adx"] else None,
                       "d1": d1[dd] if d1 is not None and dd >= 0 else None, "funding_rate": last_rate}
                reasons = filter_reasons(cfg, side, ctx)
                base = [t for t in open_ if not t["pyramid"]]
                if not base:
                    tid += 1
                    t = open_trade(d, h, i, bars4, ind, equity, cfg, ctx, tid)
                    t["filtered"] = "/".join(reasons)
                    open_.append(t)
                    if not t["filtered"]:
                        events.append(("open", t["id"]))
                elif (cfg["pyramid"] and not reasons and len(open_) == 1 and base[0]["d"] == d
                      and not base[0]["filtered"] and d * (bars4[h]["c"] - base[0]["entry_fill"]) > 0):
                    tid += 1
                    t = open_trade(d, h, i, bars4, ind, equity, cfg, ctx, tid, pyramid=True)
                    open_.append(t)
                    events.append(("open", t["id"]))
            live = [t for t in open_ if not t["filtered"]]
            if live:
                events.append(("mark", {t["id"]: open_r(t, bars4[h]["c"]) for t in live}))

    last = bars15[-1]
    for t in open_:
        close_trade(t, len(bars15) - 1, last, last["c"], cfg, reason="END")
        book(t)
    return trades, {"cfg": cfg, "skipped": skipped, "events": events, "final_equity": equity}


# ---------------------------------------------------------------- drawdown and risk

def mtm_dd_pct(events, risk_pct):
    """Max Drawdown (% of peak) of mark-to-market equity at `risk_pct`, re-sized from the open/close/mark stream.
    Exact for closed Trades (pnl = R x risk % x equity at entry); open Trades are marked at 4H closes."""
    f = risk_pct / 100
    eq = peak = 1.0
    dd = 0.0
    base = {}
    for ev in events:
        if ev[0] == "open":
            base[ev[1]] = eq
            continue
        if ev[0] == "close":
            eq += f * base.pop(ev[1]) * ev[2]
            val = eq
        else:
            val = eq + sum(f * base[k] * r for k, r in ev[1].items() if k in base)
        peak = max(peak, val)
        dd = max(dd, 1 - val / peak if peak > 0 else 0)
    return dd * 100


def choose_risk(trades, events, ladder=risk.LADDER, limit=risk.DD_LIMIT_PCT, sims=risk.SIMS, seed=1):
    """Largest risk % whose mark-to-market Max Drawdown and bootstrap 95th-percentile Max Drawdown are both
    below the limit (docs/adr/0001, 0002)."""
    rs = [t["r_multiple"] for t in trades]
    p95 = risk.resampled_dd(rs, ladder, sims, seed)
    levels = []
    for r in ladder:
        real = mtm_dd_pct(events, r)
        ok = p95[r] is not None and real < limit and p95[r] < limit
        levels.append({"risk_pct": r, "realized_dd_pct": real, "p95_dd_pct": p95[r], "ok": ok})
    chosen = max((lv["risk_pct"] for lv in levels if lv["ok"]), default=None)
    return {"limit_pct": limit, "sims": sims, "quantile": risk.QUANTILE, "levels": levels, "chosen_risk_pct": chosen}
