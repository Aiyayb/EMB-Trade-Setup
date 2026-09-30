"""
risk.py - choose risk % per Trade from the Max Drawdown budget (docs/adr/0001), stdlib only.

A Trade's net R result does not depend on the equity it was sized from (pnl = risk amount x R), so
the equity path at any risk % is exactly prod(1 + risk x R). The chosen risk is the largest step on
the ladder whose realized Max Drawdown and resampled 95th-percentile Max Drawdown are both below
the limit.
"""

import random

LADDER = (0.5, 0.75, 1.0, 1.5, 2.0)
DD_LIMIT_PCT = 15.0
SIMS = 5000
QUANTILE = 0.95


def max_dd_pct(rs, risk_pct):
    """Max Drawdown (% of peak) of the compounded equity path for R results `rs` at `risk_pct`."""
    f = risk_pct / 100
    eq = peak = 1.0
    dd = 0.0
    for r in rs:
        eq *= max(1 + f * r, 0.0)
        if eq > peak:
            peak = eq
        elif peak > 0:
            dd = max(dd, 1 - eq / peak)
    return dd * 100


def resampled_dd(rs, risk_pcts, sims=SIMS, seed=1, q=QUANTILE):
    """q-quantile Max Drawdown % per risk level over `sims` bootstrap paths of len(rs) Trades.
    Every risk level sees the same paths, so results are monotone in risk."""
    if not rs:
        return {r: None for r in risk_pcts}
    rnd = random.Random(seed)
    n = len(rs)
    dds = {r: [] for r in risk_pcts}
    for _ in range(sims):
        path = [rs[rnd.randrange(n)] for _ in range(n)]
        for r in risk_pcts:
            dds[r].append(max_dd_pct(path, r))
    out = {}
    for r, v in dds.items():
        v.sort()
        out[r] = v[min(len(v) - 1, int(q * len(v)))]
    return out


def choose_risk(rs, ladder=LADDER, limit=DD_LIMIT_PCT, sims=SIMS, seed=1):
    """{'levels': [{risk_pct, realized_dd_pct, p95_dd_pct, ok}], 'chosen_risk_pct': float | None}."""
    p95 = resampled_dd(rs, ladder, sims, seed)
    levels = []
    for r in ladder:
        real = max_dd_pct(rs, r)
        ok = p95[r] is not None and real < limit and p95[r] < limit
        levels.append({"risk_pct": r, "realized_dd_pct": real, "p95_dd_pct": p95[r], "ok": ok})
    chosen = max((lv["risk_pct"] for lv in levels if lv["ok"]), default=None)
    return {"limit_pct": limit, "sims": sims, "quantile": QUANTILE, "levels": levels, "chosen_risk_pct": chosen}
