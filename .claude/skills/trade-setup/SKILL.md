---
name: trade-setup
description: The user's personal trading strategy and trade-setup checklist — 4H trend (EMA26 vs EMA50) + 15m entry, Execution 1 (Long) / Execution 2 (Short) step lists, Zigzag period 10 waves, pullback to the EMA 8/26/50/99/200 zone, Fib Retracement + Fib Time entry zone, triggers (Rejection + Engulfing, Inside bar breakout, Doji + Engulfing), SMC CHoCH-Retrace, Dow Theory, Elliott ABC, sideways filter (EMA8–EMA200 < 3%), and fixed money management (RR 1:3, 2% risk per trade, move SL to break-even after 2R). Use this skill whenever the user wants to find, build, plan, check, grade or review a trade/entry/setup on any chart (BTC, crypto, forex, stocks), asks "should I long/short here", "where is my SL/TP", "how big should my position be", wants a chart read of the data/ CSV files, is journaling a past trade, or is designing a backtest/bot from these rules — even if they don't say "setup" or name the skill.
---

# Trade Setup — the user's strategy

This skill encodes one specific trader's rulebook. Apply *their* rules exactly and consistently; don't invent new ones. When a rule doesn't cover a situation, say so and state the assumption you made instead of silently improvising.

You are not a licensed financial advisor. Present setups as an application of the user's own rules ("by your rules this qualifies / doesn't"), and never place orders or execute trades.

Reply in the language the user writes in (Thai or English); keep technical terms (BOS, CHoCH, EMA, RR, BE, Fib, Zigzag) in English.

## Knowledge & indicators the strategy uses

| # | Component | Role |
|---|-----------|------|
| **Price Action** | | |
| 1 | Candlestick chart | Read body/wicks; confirmation is on candle **close** |
| 2 | Price patterns | Context, reversal patterns before 15m entry, obstacles before 3R |
| 3 | **Bullish / Bearish Engulfing** ★ | Core of every entry trigger |
| 4 | Dow Theory | HH+HL = up, LH+LL = down |
| 5 | SMC — CHoCH, BOS | 15m **CHoCH-Retrace** is the preferred entry structure |
| 6 | Basic Elliott Wave (ABC correction) | The pullback into the zone is usually an ABC |
| **Indicators** | | |
| 7 | EMA 8, 26, 50, 99, 200 | 4H trend (26 vs 50), pullback zone (8→200), sideways filter (8 vs 200) |
| 8 | Fib Time | Wait for price to pass **Fib Time 0.5** of the 15m wave |
| 9 | Fib Retracement | 15m pullback must retrace **≥ 0.5** of the wave |
| 10 | Zigzag, period 10 | Defines a **completed wave** on 4H and 15m |
| **Money Management** | | |
| 11 | RR = 1:3 | TP = 3R, always |
| 12 | Risk per trade = 2% of portfolio | Size from SL distance |
| 13 | Break Even | When price reaches **2R** in profit, move SL to just beyond entry (above entry for longs, below for shorts) |

Detailed definitions live in reference files — read them when you need the exact rule:
- `references/price-action.md` — candlesticks, patterns, engulfing + the three trigger types, Dow, SMC CHoCH/BOS/CHoCH-Retrace, Elliott ABC
- `references/indicators.md` — EMA roles & filters, Zigzag 10, Fib Retracement, Fib Time
- `references/money-management.md` — sizing formula, TP/BE math, leverage, worked examples

## Timeframes

- **4H** = trend + setup (is there a trade to look for?)
- **15m** = entry, SL and TP (exactly where and when)

Only trade in the 4H trend direction: **Long only when 4H EMA26 > EMA50, Short only when 4H EMA26 < EMA50.**

## Filters that apply to both executions

- **Sideway = no trade:** if the distance between EMA200 and EMA8 is **less than 3%**, the market is sideways — no trade. Measured on the 4H as `|EMA8 − EMA200| / EMA200 × 100` (assumption: the rule doesn't say which timeframe or which EMA is the base; 4H and EMA200 are used — say so if it matters).
- **15m structure before entry:** before entering you should see a reversal pattern or the SMC **CHoCH-Retrace**. Focus on: 15m CHoCH → retrace into the Fib Retracement zone → wait for the **ENGULFING**.

## Execution 1 — Long position

Concept: Long only in an uptrend. 4H identifies the trend (EMA26 > 50); 15m is used to enter and set SL and TP.

| Step | TF | Condition |
|------|----|-----------|
| 1 | 4H | EMA26 > EMA50 |
| 2 | 4H | Wait for the first wave (up) to complete — Zigzag period 10 |
| 3 | 4H | Wait for price to pull back into the EMA 8/26/50/99/200 zone |
| 4 | 4H | Wait for a trigger: **Rejection + Engulfing**, or **Inside bar breakout**, or **Doji + Engulfing** (bullish) |
| 5 | 15m | Wait for the first wave (up) to complete — Zigzag period 10 |
| 6 | 15m | Draw Fib Retracement and Fib Time on that wave to create the entry zone |
| 7 | 15m | Wait for price to pass **Fib Time 0.5** |
| 8 | 15m | Wait for price to pull back into the zone — must retrace **not less than 0.5** (0.5 is OK) |
| 9 | 15m | Wait for a trigger: Rejection + Engulfing, or Inside bar breakout, or Doji + Engulfing (bullish) |
| 10 | 15m | **Entry Long.** SL at the **previous low**, TP at **3R** |

## Execution 2 — Short position

Concept: Short only in a downtrend. 4H identifies the trend (EMA26 < 50); 15m is used to enter and set SL and TP.

| Step | TF | Condition |
|------|----|-----------|
| 1 | 4H | EMA26 < EMA50 |
| 2 | 4H | Wait for the first wave (down) to complete — Zigzag period 10 |
| 3 | 4H | Wait for price to pull back into the EMA 8/26/50/99/200 zone |
| 4 | 4H | Wait for a trigger: Rejection + Engulfing, or Inside bar breakout, or Doji + Engulfing (bearish) |
| 5 | 15m | Wait for the first wave (down) to complete — Zigzag period 10 |
| 6 | 15m | Draw Fib Retracement and Fib Time on that wave to create the entry zone |
| 7 | 15m | Wait for price to pass **Fib Time 0.5** |
| 8 | 15m | Wait for price to pull back into the zone — must retrace **not less than 0.5** (0.5 is OK) |
| 9 | 15m | Wait for a trigger: Rejection + Engulfing, or Inside bar breakout, or Doji + Engulfing (bearish) |
| 10 | 15m | **Entry Short.** SL at the **previous high**, TP at **3R** |

Steps are sequential: each step is only checked after the previous one is satisfied. If an earlier step fails (e.g. 4H EMA26 crosses back, or sideway), the setup is off — say so plainly. A skipped trade is a good outcome.

### Interpreting the steps

- **"First wave completed" (steps 2, 5):** the last Zigzag(10) leg in the trade direction has ended — Zigzag has printed the opposite point after it and price is now pulling back. On 15m this is typically the impulse that made the CHoCH in the 4H direction.
- **Fib Retracement (step 6):** from the wave's start to its end (long: low → high; short: high → low). The 15m entry zone starts at **0.5**. No maximum is set by the rules; if price retraces past **1.0** (beyond the wave start), the previous low/high is gone and the setup is invalid.
- **Fib Time (steps 6–7):** measure the wave's duration (bars from start to end) and project from the wave end. "Passed Fib Time 0.5" = at least `0.5 × wave duration` bars have closed since the wave end. A trigger before that time doesn't count.
- **EMA zone (step 3):** the area between EMA8 and EMA200. Reaching EMA8 means price has entered the zone; deeper EMAs (50/99/200) are deeper parts of the same zone.
- **Triggers (steps 4, 9):** see `references/price-action.md` §3. The candle must be **closed**, and it must form in the zone (4H: at the EMA zone; 15m: after Fib Time 0.5 and after a ≥ 0.5 retracement).
- **SL (step 10):** at the previous low (long) / previous high (short) — the extreme of the 15m pullback that produced the trigger. The rule doesn't specify a buffer; if you suggest one, say so.

## Workflow

### Step 0 — Gather inputs
You need: symbol, account balance, and 4H + 15m price data (or a chart description/screenshot from the user). If the user has candle CSVs (e.g. `data/BTCUSDT_4H.csv`, `data/BTCUSDT_15m.csv`, columns `timestamp, open_time_utc, open_time_bkk, open, high, low, close, ...`), run the analyzer instead of eyeballing numbers:

```bash
python .claude/skills/trade-setup/scripts/analyze_chart.py --file data/BTCUSDT_4H.csv
python .claude/skills/trade-setup/scripts/analyze_chart.py --file data/BTCUSDT_15m.csv --bias long
```

On 4H it infers the bias from EMA26 vs EMA50. On 15m, pass the 4H direction with `--bias long|short`; on 15m, ignore the lines tagged `[4H …]` (they describe the 15m EMAs, not the 4H trend). The report includes:
- EMA values, the **Execution checklist** (trend, sideway distance, last completed Zigzag(10) wave, EMAs reached by the pullback, Fib Retracement levels of the wave, Fib Time windows and whether 0.5 has passed, deepest retracement and whether it's ≥ 0.5, triggers and CHoCH since the wave ended)
- recent triggers (Engulfing with rejection-wick %, Inside bar breakout, Doji + Engulfing), Zigzag points, Dow swings, SMC BOS/CHoCH, and Fib of the SMC impulse leg

Options: `--until "YYYY-MM-DD HH:MM:SS"` (UTC) replays the chart as of a past moment — use it for trade reviews and backtests, on both timeframes with the same cut-off. `--zigzag`, `--lookback`, `--swing`, `--json` are available. The analyzer is mechanical — sanity-check its waves and triggers against what a trader would see on the chart, and say when you disagree.

If balance is unknown, still build the setup and express size as "risk = 2% of balance"; ask for the balance only if the user wants an exact size.

### Step 1 — Walk the execution steps in order
Pick Execution 1 or 2 from the 4H EMA26 vs EMA50, check the sideway filter, then go step by step. Stop at the first step not yet satisfied and report **what the setup is waiting for** (e.g. "Waiting for step 7: Fib Time 0.5 passes at 2026-10-01 14:30 BKK; the 0.5 zone is 83,888").

### Step 2 — Plan the trade (fixed rules)
- **Entry:** close of the 15m trigger candle.
- **SL:** previous low (long) / previous high (short).
- **TP:** exactly **3R** → `TP = entry ± 3 × |entry − SL|`.
- **Size:** risk **2%** of portfolio → `size = (balance × 0.02) / |entry − SL|`.
- **Break-even:** when price reaches **2R** in profit, move SL to entry + small buffer on the profit side (above entry for longs, below for shorts).

Use the calculator so the math is exact:

```bash
python .claude/skills/trade-setup/scripts/trade_calc.py --balance 10000 --entry 65000 --sl 64200
```

Options: `--leverage 10` (margin + liquidation-before-SL warning), `--target 67800` (checks whether a structural target allows 3R), `--be-buffer-pct 0.1`, `--contract-size 0.01`.

### Step 3 — Sanity checks
Flag (don't silently override the rules) when:
- A major opposing level (4H swing, EMA200, pattern target) sits before the 3R TP — RR is fixed at 1:3, so a blocked path means reconsider, not a smaller target.
- The SL (previous low/high) is so far away that position size becomes tiny or the 15m trade is really a 4H trade.
- No CHoCH-Retrace or reversal pattern was visible on 15m before the trigger (the notes say you should see one).

## Output format

```
## <SYMBOL> <LONG (Execution 1) / SHORT (Execution 2)> — <status: READY / WAITING for step N / NO TRADE>

**4H:** EMA26 <>/< EMA50 | EMA8–EMA200 distance <x%> (<trending/sideway>) | Wave <from → to> | Pullback reached EMA <list> | Trigger <type @ time / not yet>
**15m:** Wave <from → to> | Fib 0.5 = <price> | Fib Time 0.5 = <time> (<passed/upcoming>) | Retrace <deepest> | CHoCH-Retrace <yes/no> | Trigger <type @ time / not yet>

| Item | Value |
|------|-------|
| Entry | … |
| Stop loss | … (previous low/high @ time) |
| Take profit (3R) | … |
| Risk | 2% = <amount> |
| Position size | <units> (<notional>) |
| Move SL to BE at (2R) | … → new SL … |

**Checklist:**
4H: ✅/❌ 1 EMA26/50 · ✅/❌ Not sideway (≥3%) · ✅/❌ 2 Wave done · ✅/❌ 3 EMA zone · ✅/❌ 4 Trigger
15m: ✅/❌ 5 Wave done · ✅/❌ 6 Fib zone drawn · ✅/❌ 7 Fib Time 0.5 passed · ✅/❌ 8 Retrace ≥ 0.5 · ✅/❌ CHoCH-Retrace / reversal pattern · ✅/❌ 9 Trigger · ✅/❌ 10 Entry/SL/TP set
**Next / invalidation:** <what must happen next, or what kills the setup>
**Assumptions:** <anything you had to assume>
```

If there's no valid setup, say so first, then state what would need to happen next.

## Reviewing a past trade
Rebuild the setup as it looked at entry time (`--until` on both 4H and 15m, only candles up to then), walk the 10 steps plus the sideway filter and CHoCH-Retrace note, and point out which rules were followed or broken — especially trading against 4H EMA26/50, entering before Fib Time 0.5 or before a 0.5 retracement, SL not at the previous low/high, 2% sizing, 3R target, and whether BE was moved at 2R.
