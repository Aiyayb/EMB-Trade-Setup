"""Unit tests for the Trend Breakout engine (stdlib unittest).
Run: python -m unittest discover -s .claude/skills/trend-breakout/scripts -p "test_*.py" """

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine as E  # noqa: E402


def market(n4=900, seed=1, drift=0.0):
    """Synthetic 15m candles and the 4H candles built from them (16 x 15m each)."""
    rnd = random.Random(seed)
    b15, p = [], 100.0
    for i in range(n4 * 16):
        o = p
        c = max(1.0, o * (1 + rnd.gauss(drift, 0.004)))
        b15.append({"ts": i * E.M15, "t": f"2022-01-01 {i}", "o": o, "c": c,
                    "h": max(o, c) * (1 + abs(rnd.gauss(0, 0.001))), "l": min(o, c) * (1 - abs(rnd.gauss(0, 0.001)))})
        p = c
    b4 = []
    for k in range(n4):
        g = b15[k * 16:(k + 1) * 16]
        b4.append({"ts": g[0]["ts"], "t": f"2022-01-01 {k}", "o": g[0]["o"], "c": g[-1]["c"],
                   "h": max(x["h"] for x in g), "l": min(x["l"] for x in g)})
    return b4, b15


def bar(o, h, l, c, ts=0):
    return {"ts": ts, "t": "2022-01-01 00:00", "o": o, "h": h, "l": l, "c": c}


CFG = dict(E.DEFAULTS, adx_min=0.0)


class TestIndicators(unittest.TestCase):
    def test_no_look_ahead(self):
        b4, _ = market(500, seed=3)
        full = E.indicators(b4, CFG)
        rnd = random.Random(5)
        for k in rnd.sample(range(len(b4)), 40):
            part = E.indicators(b4[:k + 1], CFG)
            for key in full:
                a, b = full[key][k], part[key][k]
                if a is None or b is None:
                    self.assertIs(a, b, f"{key} at {k}")
                else:
                    self.assertAlmostEqual(a, b, places=9, msg=f"{key} at {k}")

    def test_channel_excludes_current_candle(self):
        b4, _ = market(100, seed=2)
        ind = E.indicators(b4, CFG)
        self.assertEqual(ind["ch_hi"][50], max(b["h"] for b in b4[30:50]))
        self.assertEqual(ind["tr_lo"][50], min(b["l"] for b in b4[41:51]))
        self.assertIsNone(ind["ch_hi"][19])

    def test_breakout_needs_side_filter(self):
        ind = {"ema": [100.0], "atr": [1.0], "ch_hi": [105.0], "ch_lo": [95.0]}
        self.assertEqual(E.breakout(ind, [bar(104, 107, 104, 106)], 0), "long")
        ind["ema"] = [110.0]
        self.assertIsNone(E.breakout(ind, [bar(104, 107, 104, 106)], 0))  # above Channel but below EMA200
        self.assertEqual(E.breakout(ind, [bar(96, 96, 93, 94)], 0), "short")


class TestTradeRules(unittest.TestCase):
    def test_trailing_stop_only_toward_profit(self):
        cfg = dict(E.DEFAULTS)
        ind = {"tr_lo": [90.0, 95.0, 92.0], "tr_hi": [None] * 3, "atr": [1.0] * 3}
        b4 = [bar(100, 100, 100, 100)] * 3
        t = {"d": 1, "stop": 91.0, "best_close": 100.0}
        E.trail(ind, b4, 0, t, cfg)
        self.assertEqual(t["stop"], 91.0)   # Channel 90 is below the Initial Stop
        E.trail(ind, b4, 1, t, cfg)
        self.assertEqual(t["stop"], 95.0)
        E.trail(ind, b4, 2, t, cfg)
        self.assertEqual(t["stop"], 95.0)   # never back down

    def test_chandelier(self):
        cfg = dict(E.DEFAULTS, chandelier_atr=3.0)
        ind = {"atr": [2.0, 2.0]}
        b4 = [bar(100, 100, 100, 100), bar(110, 110, 110, 110)]
        t = {"d": 1, "stop": 90.0, "best_close": 100.0}
        E.trail(ind, b4, 1, t, cfg)
        self.assertEqual(t["stop"], 104.0)  # best close 110 - 3 x 2

    def test_stop_gap_fills_at_open(self):
        t = {"d": 1, "stop": 95.0}
        self.assertEqual(E.stop_hit(t, bar(96, 97, 94, 96)), 95.0)
        self.assertEqual(E.stop_hit(t, bar(93, 94, 90, 91)), 93.0)
        self.assertIsNone(E.stop_hit(t, bar(96, 97, 95.5, 96)))
        s = {"d": -1, "stop": 105.0}
        self.assertEqual(E.stop_hit(s, bar(107, 108, 106, 107)), 107.0)

    def test_position_cap(self):
        cfg = dict(E.DEFAULTS, risk_pct=2.0, slippage_pct=0.0)
        p = E.position(100.0, 99.5, 10000.0, cfg)   # 0.5% stop -> 4x notional wanted
        self.assertTrue(p["capped"])
        self.assertAlmostEqual(p["notional"], 30000.0)
        p = E.position(100.0, 97.0, 10000.0, cfg)
        self.assertFalse(p["capped"])
        self.assertAlmostEqual(p["units"] * 3.0, 200.0)


class TestBacktest(unittest.TestCase):
    def setUp(self):
        self.b4, self.b15 = market(1200, seed=11, drift=0.0002)

    def test_entries_match_rules_and_live_check(self):
        cfg = dict(E.DEFAULTS, fee_pct=0.0, slippage_pct=0.0)
        trades, _ = E.run(self.b4, self.b15, cfg)
        self.assertTrue(trades)
        for t in trades:
            h = t["entry_h"]
            ind = E.indicators(self.b4[:h + 1], cfg)          # what check.py sees at that candle
            side = E.breakout(ind, self.b4[:h + 1], h)
            self.assertEqual(side, "long" if t["d"] == 1 else "short")
            self.assertAlmostEqual(t["signal_price"], self.b4[h]["c"])
            self.assertAlmostEqual(t["initial_stop"], E.initial_stop(ind, self.b4, h, t["d"], cfg))
        for a, b in zip(trades, trades[1:]):
            self.assertLessEqual(a["exit_i"], b["entry_i"])  # one Trade at a time

    def test_costs_and_r(self):
        trades, _ = E.run(self.b4, self.b15, dict(E.DEFAULTS, funding=False))
        for t in trades:
            self.assertAlmostEqual(t["r_multiple"], t["pnl"] / t["risk_amt"])
            self.assertGreater(t["cost_r"], 0)
            self.assertLess(t["r_multiple"], t["gross_r"])

    def test_funding_only_while_open_and_long_pays(self):
        cfg = dict(E.DEFAULTS, fee_pct=0.0, slippage_pct=0.0)
        base, _ = E.run(self.b4, self.b15, cfg)
        fund = [(k * 8 * 3600 * 1000, 0.001) for k in range(1, 1200 * 4 // 2)]
        trades, _ = E.run(self.b4, self.b15, cfg, funding=fund)
        for a, b in zip(base, trades):
            n = sum(1 for ts, _ in fund if a["entry_ts"] < ts <= self.b15[a["exit_i"]]["ts"] + E.M15)
            if n == 0:
                self.assertEqual(b["funding"], 0.0)
            else:
                self.assertEqual(b["funding"] > 0, b["d"] == 1)   # positive rate: Long pays, Short receives

    def test_filter_only_removes_trades(self):
        base, _ = E.run(self.b4, self.b15, dict(E.DEFAULTS))
        kept, info = E.run(self.b4, self.b15, dict(E.DEFAULTS, adx_min=25.0))
        key = lambda t: (t["entry_i"], t["exit_i"], round(t["r_multiple"], 9))  # noqa: E731
        self.assertTrue(info["skipped"])
        self.assertEqual(sorted(map(key, kept + info["skipped"])), sorted(map(key, base)))

    def test_mtm_drawdown(self):
        trades, info = E.run(self.b4, self.b15, dict(E.DEFAULTS, risk_pct=1.0))
        closed = [ev for ev in info["events"] if ev[0] != "mark"]
        self.assertAlmostEqual(E.mtm_dd_pct(closed, 1.0), E.risk.max_dd_pct([t["r_multiple"] for t in trades], 1.0), places=6)
        self.assertGreaterEqual(E.mtm_dd_pct(info["events"], 1.0) + 1e-9, E.mtm_dd_pct(closed, 1.0))
        self.assertAlmostEqual(E.mtm_dd_pct([("open", 1), ("mark", {1: -2.0}), ("close", 1, 1.0)], 1.0), 2.0)

    def test_levers(self):
        self.assertEqual(E.levers(dict(E.DEFAULTS)), {})
        self.assertEqual(E.levers(dict(E.DEFAULTS, stop_atr=3.0, pyramid=True)), {"stop_atr": 3.0, "pyramid": True})
        self.assertFalse(E.touches_holdout({"end": E.parse_date("2024-12-31", end=True)}))
        self.assertTrue(E.touches_holdout({"end": None}))


if __name__ == "__main__":
    unittest.main()
