---
name: trade-setup
description: The user's personal trading strategy and trade-setup checklist — Price Action (candlesticks, chart patterns, Bullish/Bearish Engulfing), Dow Theory, SMC (CHoCH, BOS), Elliott Wave ABC corrections, EMA 8/26/50/99/200, Fib Retracement, Fib Time, and fixed money management (RR 1:3, 2% risk per trade, move SL to break-even after 2R). Use this skill whenever the user wants to find, build, plan, check, grade or review a trade/entry/setup on any chart (BTC, crypto, forex, stocks, any timeframe), asks "should I long/short here", "where is my SL/TP", "how big should my position be", wants a chart read of the data/ CSV files, is journaling a past trade, or is designing a backtest/bot from these rules — even if they don't say "setup" or name the skill.
---

# Trade Setup — the user's strategy

This skill encodes one specific trader's rulebook. The job is to apply *their* rules consistently, not to invent new ones. When a rule below doesn't cover a situation, say so and state the assumption you made, rather than silently improvising.

You are not a licensed financial advisor. Present setups as an application of the user's own rules ("by your rules this qualifies / doesn't"), and never place orders or execute trades.

Reply in the language the user writes in (Thai or English); keep technical terms (BOS, CHoCH, EMA, RR, BE) in English.

## The rulebook at a glance

| # | Component | Role in a setup |
|---|-----------|-----------------|
| 1 | Candlestick chart | Read every candle's body/wick; closes matter more than wicks |
| 2 | Price patterns | Context + targets (double top/bottom, H&S, triangles, flags, wedges) |
| 3 | **Bullish / Bearish Engulfing** ★ | **Primary entry trigger** |
| 4 | Dow Theory | Defines trend: HH+HL = up, LH+LL = down |
| 5 | SMC — BOS / CHoCH | BOS = trend continues, CHoCH = first sign of reversal |
| 6 | Elliott Wave ABC | Where a pullback/correction is likely to end |
| 7 | EMA 8, 26, 50, 99, 200 | Trend filter + dynamic support/resistance |
| 8 | Fib Time | *When* a turn is likely (time window) |
| 9 | Fib Retracement | *Where* a pullback is likely to end (price zone) |
| 10 | RR = 1:3 | TP is always 3× the SL distance |
| 11 | Risk = 2% of portfolio | Position size comes from the SL distance, not from leverage |
| 12 | Break-even at 2R | Once price reaches 2R in profit, move SL to just beyond entry |

Detailed definitions live in reference files — read them when you need the exact rule:
- `references/price-action.md` — candlesticks, chart patterns, engulfing rules, Dow Theory, SMC BOS/CHoCH, Elliott ABC
- `references/indicators.md` — EMA stack, Fib Retracement, Fib Time
- `references/money-management.md` — position sizing formula, TP/BE math, leverage notes, worked examples

## Workflow: building a setup

Work top-down. Each step either adds confluence or kills the trade. A trade killed early is a good outcome — say so plainly.

### Step 0 — Gather inputs
You need: symbol, timeframe(s), account balance, and price data (or a chart description/screenshot from the user). If the user has candle CSVs (e.g. `data/BTCUSDT_4H.csv`, columns `timestamp, open_time_utc, open_time_bkk, open, high, low, close, volume_btc, volume_usdt`), run the analyzer instead of eyeballing numbers:

```bash
python .claude/skills/trade-setup/scripts/analyze_chart.py --file data/BTCUSDT_4H.csv
```

It prints EMA values/alignment, Dow swing labels (HH/HL/LH/LL), the latest BOS/CHoCH events, recent engulfing candles, and Fib Retracement + Fib Time for two legs: the **impulse leg in the trend direction** (use this for the entry zone) and the most recent swing leg (useful for ABC / LTF context). Add `--until "YYYY-MM-DD HH:MM:SS"` to replay the chart as of a past moment (trade reviews, backtests). Run it on the higher timeframe (1D/4H) for bias and again on the lower timeframe (1H/15m) for the trigger. Use `--json` if you need to process the output further. The analyzer is mechanical — sanity-check its swings against what a trader would see, and say when you disagree.

If balance is unknown, still build the setup and express size as "risk = 2% of balance" with the formula; ask for the balance only if the user wants an exact size.

### Step 1 — Higher-timeframe bias (1D / 4H)
- **Dow structure:** HH+HL → long bias only. LH+LL → short bias only. Mixed/ranging → no bias; wait or trade range edges only with extra confluence.
- **EMA stack:** bullish when price > EMA200 and EMAs are ordered 8 > 26 > 50 > 99 > 200 (bearish = reverse). Partial alignment = weaker trend.
- **Latest SMC event:** most recent BOS confirms the trend; a fresh CHoCH against it means the trend may be flipping — don't trade the old direction until structure resolves.

Trade in the direction of the HTF bias. Counter-trend trades need a HTF CHoCH first.

### Step 2 — Where to enter: the zone (price + time)
Look for a pullback into a zone with stacked confluence:
- **Fib Retracement** of the last impulse leg: 0.5 – 0.618 (golden zone), up to 0.786 max. Deeper than 0.786 → the leg is likely failing.
- **EMA** 50 / 99 / 200 sitting in or near that zone.
- **Prior structure:** old resistance-turned-support (or vice-versa), a pattern neckline, the broken BOS level.
- **Elliott ABC:** pullback looks like a completed A-B-C (C ≈ 1.0–1.618 × A) ending inside the Fib zone.
- **Fib Time:** price reaches the zone near a Fib Time window (0.618 / 1.0 / 1.618 of the prior leg's duration) — raises odds of a turn.

### Step 3 — Trigger (lower timeframe, 1H / 15m)
Enter only when, **inside the zone**:
1. A **Bullish Engulfing** (long) or **Bearish Engulfing** (short) candle **closes**, and ideally
2. LTF structure prints a **CHoCH** in the direction of the HTF bias (the LTF pullback structure breaks).

No closed engulfing candle in the zone → no entry, even if everything else lines up. That's the point of having a trigger.

### Step 4 — Plan the trade (fixed rules, no exceptions)
- **Entry:** close of the engulfing candle (or a limit at its 50% body retest — state which).
- **SL:** beyond the engulfing candle's extreme or the swing that invalidates the idea, whichever is structurally correct (below the low for longs, above the high for shorts), plus a small buffer.
- **TP:** exactly **3R** → `TP = entry ± 3 × |entry − SL|`.
- **Size:** risk **2%** of portfolio → `size = (balance × 0.02) / |entry − SL|`.
- **Break-even:** when price reaches **2R** in profit, move SL to entry + small buffer on the profit side (above entry for longs, below for shorts) so fees are covered and the trade can't become a loss.

Use the calculator so the math is exact:

```bash
python .claude/skills/trade-setup/scripts/trade_calc.py --balance 10000 --entry 65000 --sl 64200
```

Options: `--leverage 10` (shows margin and warns if liquidation would come before SL), `--target 67800` (checks whether a structural target actually allows 3R), `--be-buffer-pct 0.1`.

### Step 5 — Validate before calling it a trade
Reject or downgrade if:
- A major opposing level (HTF S/R, EMA200, pattern target, prior swing) sits **before** the 3R TP. Since RR is fixed at 1:3, a blocked path means *no trade*, not a smaller target.
- SL has to be so wide that the setup is really a different timeframe's trade.
- The trigger is against the HTF bias without a HTF CHoCH.
- Price is mid-range with no zone confluence ("in no-man's land").

### Step 6 — Grade it
- **A setup:** HTF trend + Fib golden zone + ≥1 extra confluence (EMA/structure/ABC/Fib Time) + closed engulfing + LTF CHoCH + clear path to 3R.
- **B setup:** trend + zone + engulfing, but missing LTF CHoCH or only thin confluence.
- **No trade:** missing trend, zone, or trigger, or 3R is blocked.

## Output format

Use this template so setups are comparable over time:

```
## <SYMBOL> <LONG/SHORT> setup — <HTF>/<LTF> — Grade <A/B/No trade>

**Bias (HTF):** <Dow structure> | EMA stack: <aligned/partial/against> | Last SMC: <BOS/CHoCH @ price>
**Zone:** <price range> — Fib <level(s)> | <other confluence> | Fib Time: <window or n/a>
**Trigger:** <engulfing candle time & close> | LTF CHoCH: <yes @ price / not yet>

| Item | Value |
|------|-------|
| Entry | … |
| Stop loss | … (reason: …) |
| Take profit (3R) | … |
| Risk | 2% = <amount> |
| Position size | <units> (<notional>) |
| Move SL to BE at (2R) | … → new SL … |

**Checklist:** ✅/❌ Trend · ✅/❌ Fib zone · ✅/❌ EMA confluence · ✅/❌ Structure/pattern · ✅/❌ ABC · ✅/❌ Fib Time · ✅/❌ Engulfing closed · ✅/❌ LTF CHoCH · ✅/❌ Path to 3R clear
**Invalidation:** <what kills the idea before entry>
**Assumptions:** <anything you had to assume>
```

If there's no valid setup right now, say so first, then describe what would need to happen (e.g. "wait for a pullback to 0.618 at ~X and a bullish engulfing on 1H").

## Reviewing a past trade
Rebuild the setup as it looked at entry time (only use candles up to then), fill the same checklist, and point out which rule was followed or broken — especially SL placement, 2% sizing, 3R target, and whether BE was moved at 2R.
