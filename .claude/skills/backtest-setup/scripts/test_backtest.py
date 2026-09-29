"""Unit tests for backtest.py (stdlib unittest). Run: python -m unittest test_backtest -v"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest as bt  # noqa: E402

ac = bt.ac
CFG = dict(bt.DEFAULTS)


def bar(o, h, l, c, ts=0):
    return {"ts": ts, "t": "2024-01-01 00:00:00", "o": o, "h": h, "l": l, "c": c}


def random_walk(n, seed=1):
    rnd = random.Random(seed)
    bars, p = [], 100.0
    for i in range(n):
        o = p
        c = max(1.0, o + rnd.gauss(0, 1))
        h = max(o, c) + abs(rnd.gauss(0, 0.5))
        l = min(o, c) - abs(rnd.gauss(0, 0.5))
        bars.append({"ts": i * bt.M15, "t": str(i), "o": o, "h": h, "l": l, "c": c})
        p = c
    return bars


def strip(pts):
    return [(p["i"], p["type"], p["price"]) for p in pts]


class TestIndicators(unittest.TestCase):
    def test_incremental_zigzag_matches_batch_at_every_bar(self):
        bars = random_walk(600)
        zz = bt.Zigzag(bars, 10)
        for i in range(len(bars)):
            zz.update(i)
            self.assertEqual(strip(zz.pts), strip(ac.zigzag(bars[:i + 1], 10)), f"bar {i}")

    def test_born_is_first_appearance(self):
        bars = random_walk(600, seed=7)
        zz = bt.Zigzag(bars, 10)
        seen = {}
        for i in range(len(bars)):
            zz.update(i)
            n = len(zz.pts)
            seen.setdefault(n - 1, i) if n else None
        for k, p in enumerate(zz.pts):
            self.assertEqual(p["born"], seen[k])
            self.assertLessEqual(p["born"], p["i"])

    def test_triggers_at_matches_full_scan(self):
        bars = random_walk(400, seed=3)
        full = ac.triggers(bars, len(bars))
        for i in range(2, len(bars)):
            want = sorted(t["type"] for t in full if t["i"] == i)
            got = sorted(t["type"] for t in bt.triggers_at(bars, i))
            self.assertEqual(got, want, f"bar {i}")

    def test_engulfing_needs_rejection(self):
        t = {"dir": "bullish", "type": "Bullish Engulfing", "with_rejection": False}
        self.assertFalse(bt.is_valid_trigger(t, True))
        t["with_rejection"] = True
        self.assertTrue(bt.is_valid_trigger(t, True))
        self.assertFalse(bt.is_valid_trigger(t, False))
        ib = {"dir": "bullish", "type": "Inside Bar Breakout (bull)", "with_rejection": False}
        self.assertTrue(bt.is_valid_trigger(ib, True))
        dj = {"dir": "bearish", "type": "Doji + Bearish Engulfing", "with_rejection": False}
        self.assertTrue(bt.is_valid_trigger(dj, False))

    def test_regime(self):
        self.assertEqual(bt.regime_of(3.2), "trend 3-5%")
        self.assertEqual(bt.regime_of(7), "trend 5-10%")
        self.assertEqual(bt.regime_of(12), "trend >=10%")


class TestTradeManagement(unittest.TestCase):
    def cfg(self, **kw):
        c = dict(CFG, fee_pct=0.0, slippage_pct=0.0)
        c.update(kw)
        return c

    def long_trade(self, cfg, entry=100.0, sl=90.0, equity=10000.0):
        # R = 10 -> TP 130, BE trigger 120, BE SL 100.1
        return bt.open_trade(True, 0, bar(entry, entry, entry, entry), sl, equity, cfg)

    def test_levels_and_size(self):
        c = self.cfg()
        t = self.long_trade(c)
        self.assertAlmostEqual(t["tp"], 130)
        self.assertAlmostEqual(t["be_trigger"], 120)
        self.assertAlmostEqual(t["be_sl"], 100.1)
        self.assertAlmostEqual(t["units"], 20)  # 2% of 10k = 200 / R 10
        s = bt.open_trade(False, 0, bar(100, 100, 100, 100), 110, 10000, c)
        self.assertAlmostEqual(s["tp"], 70)
        self.assertAlmostEqual(s["be_trigger"], 80)
        self.assertAlmostEqual(s["be_sl"], 99.9)

    def test_sl_hit(self):
        c = self.cfg()
        t = self.long_trade(c)
        self.assertTrue(bt.manage(t, 1, bar(99, 101, 89, 95), c))
        self.assertEqual(t["exit_reason"], "SL")
        self.assertAlmostEqual(t["r_multiple"], -1)

    def test_tp_hit(self):
        c = self.cfg()
        t = self.long_trade(c)
        self.assertTrue(bt.manage(t, 1, bar(100, 131, 95, 129), c))
        self.assertEqual(t["exit_reason"], "TP")
        self.assertAlmostEqual(t["r_multiple"], 3)

    def test_sl_and_tp_same_bar_counts_sl(self):
        c = self.cfg()
        t = self.long_trade(c)
        bt.manage(t, 1, bar(100, 140, 80, 100), c)
        self.assertEqual(t["exit_reason"], "SL")

    def test_be_applies_from_next_bar(self):
        c = self.cfg()
        t = self.long_trade(c)
        self.assertFalse(bt.manage(t, 1, bar(100, 121, 99, 118), c))  # 2R reached, low 99 < BE SL but BE not active yet
        self.assertTrue(t["be_pending"])
        self.assertTrue(bt.manage(t, 2, bar(118, 119, 100.05, 101), c))
        self.assertEqual(t["exit_reason"], "BE")
        self.assertAlmostEqual(t["exit_rule_price"], 100.1)
        self.assertGreater(t["r_multiple"], 0)

    def test_sl_and_2r_same_bar_counts_sl(self):
        c = self.cfg()
        t = self.long_trade(c)
        bt.manage(t, 1, bar(100, 125, 85, 100), c)
        self.assertEqual(t["exit_reason"], "SL")

    def test_gap_through_sl_fills_at_open(self):
        c = self.cfg()
        t = self.long_trade(c)
        bt.manage(t, 1, bar(85, 86, 80, 82), c)
        self.assertAlmostEqual(t["exit_rule_price"], 85)
        self.assertAlmostEqual(t["r_multiple"], -1.5)

    def test_short_tp_and_sl(self):
        c = self.cfg()
        s = bt.open_trade(False, 0, bar(100, 100, 100, 100), 110, 10000, c)
        bt.manage(s, 1, bar(100, 105, 69, 72), c)
        self.assertEqual(s["exit_reason"], "TP")
        self.assertAlmostEqual(s["r_multiple"], 3)
        s = bt.open_trade(False, 0, bar(100, 100, 100, 100), 110, 10000, c)
        bt.manage(s, 1, bar(100, 111, 60, 100), c)
        self.assertEqual(s["exit_reason"], "SL")

    def test_costs(self):
        c = self.cfg(fee_pct=0.05, slippage_pct=0.02)
        t = self.long_trade(c)
        self.assertAlmostEqual(t["entry_fill"], 100.02)
        bt.manage(t, 1, bar(99, 101, 89, 95), c)
        exit_fill = 90 * (1 - 0.0002)
        fees = 20 * 100.02 * 0.0005 + 20 * exit_fill * 0.0005
        self.assertAlmostEqual(t["pnl"], 20 * (exit_fill - 100.02) - fees)
        self.assertLess(t["r_multiple"], -1)

    def test_liquidation_flag(self):
        c = self.cfg(leverage=10)
        self.assertFalse(self.long_trade(c, sl=91)["liq_flag"])   # 9% < 9.5%
        self.assertTrue(self.long_trade(c, sl=90)["liq_flag"])    # 10% > 9.5%


if __name__ == "__main__":
    unittest.main()
