# Indicators reference

Contents: 7. EMA 8/26/50/99/200 · 8. Fib Time · 9. Fib Retracement

---

## 7. EMA 8, 26, 50, 99, 200

Exponential moving averages on **close**. `EMA_t = close_t × k + EMA_{t-1} × (1 − k)`, `k = 2 / (n + 1)`, seeded with the SMA of the first n closes (same as TradingView).

| EMA | Role |
|-----|------|
| 8 | Very short-term momentum; strong trends ride above/below it |
| 26 | Short-term trend; 8/26 cross = momentum shift |
| 50 | Medium trend; first major dynamic S/R for pullbacks |
| 99 | Deeper pullback support/resistance |
| 200 | Long-term trend line: above = bull market bias, below = bear |

**Trend filter**
- **Full bullish alignment:** `price > EMA8 > EMA26 > EMA50 > EMA99 > EMA200` → strong uptrend, longs only.
- **Full bearish alignment:** reverse order → shorts only.
- **Partial / tangled:** EMAs crossing each other, price chopping through them → range or transition; lower-grade setups or no trade.
- Slope matters: a flat EMA200 means no long-term trend.

**Confluence**
- In an uptrend, a pullback that reaches EMA 50 / 99 / 200 **at the same price as a Fib 0.5–0.786 level** is a high-quality zone.
- A candle that wicks through an EMA and closes back on the trend side (ideally an engulfing) is the classic trigger.
- 8/26 crossing back in the trend direction on the LTF supports the CHoCH signal.

**Warnings**
- EMA200 directly above a long entry (or below a short) before 3R counts as an obstacle in Step 5.

## 8. Fib Time

Fib Time projects **when** a swing is likely to end, using the duration of a previous leg. Treat outputs as windows (± 1–2 candles), not exact moments.

**Trend-based Fib Time (default)** — measure the duration of the last leg (bars from swing start to swing end), then project from the leg end:
`window_r = leg_end_time + r × leg_duration`, with r ∈ {0.382, 0.5, 0.618, 1.0, 1.618, 2.618}.
- A pullback that reaches the price zone near the 0.618 or 1.0 window is more likely to turn.
- For ABC: wave C often ends near time equality with wave A (1.0) or 1.618 × A's duration.

**Fib Time Zones** — from a major pivot, mark vertical lines at Fibonacci bar counts 1, 2, 3, 5, 8, 13, 21, 34, 55, 89 (× the unit bar distance). Clusters of zones from different pivots strengthen a window.

Fib Time is confluence only — it never replaces the price zone or the engulfing trigger.

## 9. Fib Retracement

Draw on the **last completed impulse leg**, from swing start to swing end, using wicks (high/low):
- Uptrend leg: from swing **low** (100% / 1.0) to swing **high** (0%). Level price = `high − r × (high − low)`.
- Downtrend leg: from swing **high** to swing **low**. Level price = `low + r × (high − low)`.

| Level | Meaning in this strategy |
|-------|--------------------------|
| 0.236 / 0.382 | Shallow — strong trend; only with strong confluence |
| **0.5 – 0.618** | **Golden zone — primary entry area** |
| 0.705 – 0.786 | Deep — still valid; last line before the leg is considered failing |
| > 0.786 | Leg likely failing — no continuation trade |
| 1.0 | Leg fully retraced — structure broken |

Extensions (for checking room to target, not for setting TP — TP is fixed at 3R): 1.272, 1.618 of the leg beyond its end. If 3R lies far beyond 1.618 extension on a weak trend, consider the target unrealistic and downgrade.

**Best zones = overlaps:** Fib 0.5–0.786 + EMA 50/99/200 + old S/R or BOS level + ABC completion + Fib Time window.
