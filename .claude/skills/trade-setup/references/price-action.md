# Price Action reference

Contents: 1. Candlestick chart · 2. Price patterns · 3. Engulfing (entry trigger) · 4. Dow Theory · 5. SMC (BOS, CHoCH) · 6. Elliott Wave ABC

General rule for every definition below: **use candle closes for confirmation**, not wicks. A wick through a level is a liquidity grab until a candle closes beyond it.

---

## 1. Candlestick chart

Each candle = one period: open, high, low, close (OHLC).
- **Body** = open→close. Green/bullish if close > open, red/bearish if close < open.
- **Wicks (shadows)** = rejected prices. A long lower wick = buyers rejected lower prices; long upper wick = sellers rejected higher prices.
- **Body size vs. average** shows conviction. A large body closing near its extreme = strong momentum.

Key single/multi-candle signals (supporting evidence — the entry trigger is still the engulfing):
| Candle | Meaning | Where it matters |
|--------|---------|------------------|
| Hammer / bullish pin bar | Lower wick ≥ 2× body, small upper wick → rejection of lows | At support / Fib zone |
| Shooting star / bearish pin bar | Upper wick ≥ 2× body → rejection of highs | At resistance |
| Doji | Open ≈ close → indecision | Needs next candle to confirm |
| Morning star / Evening star | 3-candle reversal (big candle, small candle, big opposite candle) | At the end of a pullback |
| Inside bar | Range inside previous candle → compression | Breakout direction matters |

Always read candles in context: the same hammer means much more at a 0.618 Fib + EMA200 than in the middle of a range.

## 2. Price patterns

**Reversal patterns**
- **Double top / double bottom** — two tests of a level fail; confirmed when price closes through the neckline (the swing between the two tops/bottoms). Target ≈ pattern height projected from neckline.
- **Head & Shoulders / Inverse H&S** — left shoulder, higher head, lower right shoulder (for H&S); confirmed on neckline close. Target = head-to-neckline height from breakout.
- **Rising wedge (bearish) / Falling wedge (bullish)** — converging trendlines, momentum fading.

**Continuation patterns**
- **Bull/Bear flag** — sharp pole, then a small counter-trend channel; breakout in pole direction. Target ≈ pole length.
- **Pennant** — like a flag but a small symmetrical triangle.
- **Triangles** — ascending (flat top, rising lows → bullish bias), descending (flat bottom, falling highs → bearish bias), symmetrical (breakout either way, follow trend).
- **Rectangle / range** — horizontal S/R; trade the edges or the breakout + retest.

How patterns plug into the strategy:
- Neckline / breakout level retests are strong **zones** (Step 2).
- A pattern target that lands **before** 3R blocks the trade (Step 5).
- Pattern confirmation on HTF can supply the CHoCH/trend change.

## 3. Bullish / Bearish Engulfing ★ (primary entry trigger)

**Bullish Engulfing**
1. Previous candle is bearish (close < open).
2. Current candle is bullish (close > open).
3. Current body engulfs the previous body: `open ≤ prev.close` and `close ≥ prev.open` (crypto trades 24/7 so the open usually equals the prior close — the body-engulfing condition is what matters).
4. Current body is larger than the previous body.
- **Stronger** if it also closes above the previous candle's **high**, the body is large relative to recent candles, and volume is above average.

**Bearish Engulfing** is the mirror: previous bullish, current bearish, `open ≥ prev.close` and `close ≤ prev.open`, larger body. Stronger if it closes below the previous candle's low.

**Validity rules for this strategy**
- Only counts **inside a zone** (Fib 0.5–0.786, EMA, structure) and **in the HTF bias direction**. An engulfing in no-man's land is noise.
- The candle must be **closed**. An engulfing that is still forming can still fail.
- **SL** goes beyond the engulfing pattern's extreme (lowest low of the two candles for bullish, highest high for bearish) or the invalidating swing, plus a small buffer.

## 4. Dow Theory

Core principles used here:
1. **Trend definition:** uptrend = Higher Highs (HH) + Higher Lows (HL). Downtrend = Lower Highs (LH) + Lower Lows (LL).
2. **Three degrees of trend:** primary (months — 1W/1D), secondary (weeks — pullbacks, 4H/1D), minor (days — 1H/15m). The strategy trades secondary pullbacks inside the primary trend, triggered on the minor trend.
3. **A trend persists until a clear reversal signal:** for an uptrend, that is a failure to make a new HH *and* a close below the last HL. Don't call a top just because it "feels high".
4. **Volume should confirm:** impulses on rising volume, pullbacks on falling volume.
5. **Phases:** accumulation → public participation (markup) → distribution. Best RR is in early markup, after the first HL.

Swing points: a swing high is a candle whose high is the highest of the N candles on each side (the analyzer defaults to N = 5; lower TFs can use 3).

## 5. SMC — BOS and CHoCH

Both are defined by a **candle close** beyond a confirmed swing point.

- **BOS (Break of Structure)** — a break **in the direction of the current trend**. Uptrend: close above the latest swing high (new HH). Downtrend: close below the latest swing low (new LL). Meaning: trend continues; the broken level often becomes support/resistance for the next pullback.
- **CHoCH (Change of Character)** — the **first** break **against** the current trend. In a downtrend: close above the latest LH. In an uptrend: close below the latest HL. Meaning: the trend may be reversing; wait for a pullback and a BOS in the new direction for confirmation.

Using them:
- **HTF:** latest event tells you whether the trend is intact (BOS) or in question (CHoCH).
- **LTF trigger:** during a pullback into the HTF zone, the LTF is trending *against* the HTF. An LTF CHoCH back in the HTF direction is the signal the pullback is over — combine with the engulfing.
- Internal vs. swing structure: only count breaks of meaningful swings on the timeframe you are reading; tiny internal breaks are noise.

## 6. Basic Elliott Wave — ABC correction

Impulse = 5 waves in the trend direction (1-2-3-4-5). After it, a **3-wave correction A-B-C** retraces part of the move. The strategy uses ABC to time the end of pullbacks.

**Zigzag (most common, sharp) 5-3-5**
- Wave A: first leg against the trend.
- Wave B: partial retracement of A, typically 0.382–0.786 of A (must not exceed A's start).
- Wave C: final leg, usually **C = 1.0 × A**, sometimes **1.618 × A** (or 0.618 × A in weak corrections).

**Flat 3-3-5** — B retraces ~90–100%+ of A; C ends near or slightly past the end of A.

Where ABC should end (confluence for a long after an uptrend impulse; mirror for shorts):
- C terminating inside **Fib 0.5–0.786** of the prior impulse.
- Near an EMA 50/99/200 or the prior BOS level.
- Near a Fib Time window.

Trigger is still the same: engulfing candle + LTF CHoCH as wave C completes. If C extends beyond 1.618 × A or the whole correction retraces past the impulse start (100%), the count is wrong — step aside.

Keep wave counts simple; don't force labels. If the ABC isn't obvious, don't use it as confluence.
