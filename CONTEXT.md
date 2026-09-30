# Trading Strategy

The user's personal discretionary-turned-mechanical trading strategy (4H trend + 15m or 1H entry on BTCUSDT) and the backtest that replays it over historical candles.

## Strategy

**Execution**:
One of the two fixed step lists of the strategy — Execution 1 (Long) or Execution 2 (Short) — chosen by the 4H EMA26 vs EMA50.
_Avoid_: Strategy mode, direction plan

**Entry Timeframe**:
The timeframe on which Waves, the Entry Zone, entry Triggers and the SL are read — 15m in the Baseline, 15m or 1H in a Variant, with every entry rule unchanged between them.
_Avoid_: LTF, execution timeframe

**Setup**:
One pass through an Execution's steps, from the 4H trend condition up to (but not including) entry; it is either still waiting on a step, expired, or produced a Trade.
_Avoid_: Signal, opportunity

**HTF Setup**:
The 4H part of a Setup (steps 1–4: trend, completed 4H Wave, pullback into the EMA Zone, 4H Trigger).
_Avoid_: 4H signal

**Wave**:
A completed Zigzag(10) leg in the trade direction — complete once Zigzag has printed the opposite point after it.
_Avoid_: Swing, impulse, leg (when meaning the Zigzag wave)

**EMA Zone**:
The price area between EMA8 and EMA200 on 4H; the pullback has entered it once price reaches EMA8.
_Avoid_: Value zone, pullback zone

**Entry Zone**:
The Entry Timeframe area defined by the Wave's Fib Retracement (from 0.5 up to, but not beyond, 1.0) and Fib Time (from 0.5 onward).
_Avoid_: Fib zone, OTE

**Trigger**:
A closed candle pattern that permits the next step: Rejection + Engulfing, Inside bar breakout, or Doji + Engulfing, in the trade direction. A 4H Trigger must touch the EMA Zone; an Entry Timeframe Trigger must form inside the Entry Zone.
_Avoid_: Signal, confirmation candle

**Rejection**:
A candle whose wick on the rejection side (lower for longs, upper for shorts) is at least half its range; an Engulfing without one is not a Trigger.
_Avoid_: Pin bar (a narrower pattern), wick

**CHoCH-Retrace**:
An Entry Timeframe structure where the Wave itself breaks structure with a CHoCH in the trade direction, then price retraces into the Entry Zone; recommended before entry but not required.
_Avoid_: Structure shift, MSS

**Sideway**:
Market state where the 4H distance between EMA8 and EMA200 is below 3% of EMA200; no Setup may progress while Sideway.
_Avoid_: Range, chop, consolidation

**Setup Expiry**:
The end of a Setup without a Trade — 4H EMA26/50 flips, the market turns Sideway, a new 4H Trigger replaces it, or the Entry Timeframe pullback retraces past 1.0.
_Avoid_: Cancel, invalidation (for the whole Setup)

## Trade & money management

**Trade**:
A position opened at the close of an Entry Timeframe Trigger candle, with SL at the previous low/high (a Variant may add a buffer) and TP at 3R; at most one Trade per Wave and one open Trade at a time.
_Avoid_: Order, position (as a count)

**R**:
The distance between entry and SL of a Trade; results are measured in multiples of it.
_Avoid_: Risk unit, stop distance

**Break-even (BE)**:
Moving a Trade's SL to entry plus a small buffer on the profit side once price reaches 2R.
_Avoid_: Trailing stop

**Win**:
A Trade that exits at its TP; a Break-even or SL exit is a non-win, and win rate is Wins over all Trades.
_Avoid_: Profitable trade (a BE exit can be slightly profitable)

**RR**:
The planned ratio of a Trade's TP distance to its R, fixed at 1:3 — not the realized ratio of average win to average loss.
_Avoid_: Payoff ratio (that is the realized one)

**Profit Factor (PF)**:
Gross winning R divided by gross losing R over a set of Trades, measured net of fees and slippage.
_Avoid_: Gain ratio

**Max Drawdown**:
The largest peak-to-trough fall of account equity, as a percent of the peak.
_Avoid_: Max DD in R (that is a different measure, reported separately)

## Backtest

**Backtest Run**:
One replay of the strategy over a date range with a fixed set of rules, costs and Assumptions, producing a Trade Log, statistics and an equity report.
_Avoid_: Simulation, test

**Trade Log**:
The per-Trade record of a Backtest Run, including the state of every Execution step at entry so each Trade can be audited against the rules.
_Avoid_: Journal (reserved for live trades)

**Assumption**:
An interpretation the backtest makes where the user's rules are silent; every Backtest Run lists the Assumptions it used.
_Avoid_: Setting, parameter

**Baseline**:
The strategy exactly as defined by Execution 1/2, kept unchanged as the reference every Variant is compared against.
_Avoid_: Original, v1

**Variant**:
The Baseline with a named set of changes applied; it is a candidate until it passes the Acceptance Bar on the Holdout Period.
_Avoid_: Version, new strategy

**Lever**:
One named, separately testable change to the Baseline — a Filter, the Entry Timeframe, SL placement, or the Break-even rule; a Variant is a set of Levers.
_Avoid_: Tweak, setting, parameter

**Filter**:
A Lever that only removes Trades the Baseline would take, leaving entries, SL and TP of the remaining Trades unchanged.
_Avoid_: Condition, rule (too broad)

**Search Budget**:
The cap on how many Variants may be run on the Tuning Period (20) before the Variant approach is declared failed.
_Avoid_: Iterations, attempts

**Acceptance Bar**:
The results a Variant must reach, net of costs, to be adopted: Max Drawdown below 15% with RR 1:3 and PF of at least 1.5; PF 3 is the Stretch Target, and win rate is reported but not targeted.
_Avoid_: KPI, goal

**Finalist**:
The single Variant that passed the Acceptance Bar on the Tuning Period with the highest PF (fewer Levers breaks a tie within 0.1 PF); the only Variant ever run on the Holdout Period.
_Avoid_: Winner, champion

**Tuning Period**:
The date range (2021-10 to 2024-12) on which Variants may be designed and compared.
_Avoid_: In-sample, training set

**Holdout Period**:
The date range (2025-01 onward) that no Variant is tuned on; each finalist is run on it once.
_Avoid_: Out-of-sample, test set, forward test

**Regime**:
The 4H market state (trending or Sideway) used to break down backtest results.
_Avoid_: Market condition
