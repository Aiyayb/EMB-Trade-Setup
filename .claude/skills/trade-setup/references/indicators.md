# Indicators reference

Contents: 7. EMA 8/26/50/99/200 · 8. Fib Time · 9. Fib Retracement · 10. Zigzag period 10

---

## 7. EMA 8, 26, 50, 99, 200

Exponential moving averages on **close**. `EMA_t = close_t × k + EMA_{t-1} × (1 − k)`, `k = 2 / (n + 1)`, seeded with the SMA of the first n closes (same as TradingView).

The strategy uses the EMAs in three fixed ways:

| Use | Rule |
|-----|------|
| **Trend (4H)** | **EMA26 > EMA50 → uptrend, Long only (Execution 1). EMA26 < EMA50 → downtrend, Short only (Execution 2).** |
| **Sideway filter** | `|EMA8 − EMA200| / EMA200 × 100 < 3%` → sideway, **no trade** (checked on 4H) |
| **Pullback zone (4H step 3)** | The band from EMA8 to EMA200. Price must pull back into it after the first wave completes; touching EMA8 = entered the zone, EMA 26/50/99/200 = deeper in the zone |

| EMA | Character |
|-----|-----------|
| 8 | Very short-term momentum; edge of the pullback zone |
| 26 | Short-term trend; with 50 defines the 4H trend |
| 50 | Medium trend; with 26 defines the 4H trend |
| 99 | Deeper pullback support/resistance |
| 200 | Long-term trend line; far edge of the zone; base for the sideway filter |

Notes
- The full stack (8 > 26 > 50 > 99 > 200) shows a strong trend, but it is **not** required — the trend rule is only EMA26 vs EMA50.
- A candle that wicks into the EMA zone and closes back on the trend side with an engulfing = "Rejection + Engulfing".
- EMA200 sitting between entry and the 3R TP is an obstacle worth flagging.

## 8. Fib Time

Fib Time projects **when** a move is likely to turn, using the duration of the previous wave. Treat outputs as windows (± 1–2 candles), not exact moments.

**How the strategy uses it (15m step 6–7)** — take the completed Zigzag(10) wave, measure its duration (bars from wave start to wave end), and project from the wave end (TradingView Trend-Based Fib Time with points A = wave start, B = wave end, C = wave end):
`window_r = wave_end_time + r × wave_duration`, with r ∈ {0.382, 0.5, 0.618, 1.0, 1.618, 2.618}.

- **Rule: wait for price to pass Fib Time 0.5** — i.e. at least `0.5 × wave_duration` bars must have closed since the wave end before a trigger counts.
- Later windows (0.618 / 1.0 / 1.618) that line up with the Fib 0.5–0.618 price zone add confidence.
- For ABC: wave C often ends near time equality with wave A (1.0) or 1.618 × A's duration.

## 9. Fib Retracement

**How the strategy uses it (15m step 6, 8)** — draw on the completed Zigzag(10) wave. The pullback must retrace **not less than 0.5** (touching 0.5 is OK). The rules set no maximum; a retrace past 1.0 (beyond the wave start) removes the previous low/high used for the SL, so the setup is invalid.

Drawing, using wicks (high/low):
- Uptrend leg: from swing **low** (100% / 1.0) to swing **high** (0%). Level price = `high − r × (high − low)`.
- Downtrend leg: from swing **high** to swing **low**. Level price = `low + r × (high − low)`.

| Level | Meaning in this strategy |
|-------|--------------------------|
| 0.236 / 0.382 | Too shallow — **not** an entry (rule: retrace not less than 0.5) |
| **0.5** | **Minimum retracement — entry zone starts here (0.5 is OK)** |
| 0.618 – 0.786 | Deeper part of the entry zone — still valid |
| 1.0 | Wave fully retraced — previous low/high broken, setup invalid |

Extensions (for checking room to target, not for setting TP — TP is fixed at 3R): 1.272, 1.618 of the wave beyond its end.

**Best zones = overlaps:** Fib ≥ 0.5 + EMA 8/26/50/99/200 + old S/R or BOS level + ABC completion + a Fib Time window after 0.5.

## 10. Zigzag, period 10

Used on **both 4H and 15m** to decide when "the first wave is completed" (steps 2 and 5), and to anchor Fib Retracement / Fib Time (step 6).

Convention (common TradingView "ZigZag" script with a *Period* input, e.g. LonesomeTheBlue's; the analyzer reproduces it):
- A bar is a **pivot high** if its high is the highest of the last 10 bars (including itself); **pivot low** likewise for lows.
- A pivot of the opposite kind flips the Zigzag direction and adds a new point. A more extreme pivot in the same direction **moves** the last point.
- The **last point repaints** until the direction flips.

**Wave completed** = a Zigzag leg in the trade direction whose end point is no longer the last point, i.e. Zigzag has already drawn the opposite point after it (long: low → high, then a new low starts the pullback; short: mirror).

If the user's Zigzag uses a different setting (e.g. TradingView's built-in *Deviation %* + *Depth*), the points can differ — ask, or re-run the analyzer with `--zigzag N`.
