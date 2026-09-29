# Trading Strategy

The user's personal discretionary-turned-mechanical trading strategy (4H trend + 15m entry on BTCUSDT) and the backtest that replays it over historical candles.

## Strategy

**Execution**:
One of the two fixed step lists of the strategy — Execution 1 (Long) or Execution 2 (Short) — chosen by the 4H EMA26 vs EMA50.
_Avoid_: Strategy mode, direction plan

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
The 15m area defined by the Wave's Fib Retracement (from 0.5 up to, but not beyond, 1.0) and Fib Time (from 0.5 onward).
_Avoid_: Fib zone, OTE

**Trigger**:
A closed candle pattern that permits the next step: Rejection + Engulfing, Inside bar breakout, or Doji + Engulfing, in the trade direction. A 4H Trigger must touch the EMA Zone; a 15m Trigger must form inside the Entry Zone.
_Avoid_: Signal, confirmation candle

**Rejection**:
A candle whose wick on the rejection side (lower for longs, upper for shorts) is at least half its range; an Engulfing without one is not a Trigger.
_Avoid_: Pin bar (a narrower pattern), wick

**CHoCH-Retrace**:
A 15m structure where the Wave itself breaks structure with a CHoCH in the trade direction, then price retraces into the Entry Zone; recommended before entry but not required.
_Avoid_: Structure shift, MSS

**Sideway**:
Market state where the 4H distance between EMA8 and EMA200 is below 3% of EMA200; no Setup may progress while Sideway.
_Avoid_: Range, chop, consolidation

**Setup Expiry**:
The end of a Setup without a Trade — 4H EMA26/50 flips, the market turns Sideway, a new 4H Trigger replaces it, or the 15m pullback retraces past 1.0.
_Avoid_: Cancel, invalidation (for the whole Setup)

## Trade & money management

**Trade**:
A position opened at the close of a 15m Trigger candle, with SL at the previous low/high and TP at 3R; at most one Trade per 15m Wave and one open Trade at a time.
_Avoid_: Order, position (as a count)

**R**:
The distance between entry and SL of a Trade; results are measured in multiples of it.
_Avoid_: Risk unit, stop distance

**Break-even (BE)**:
Moving a Trade's SL to entry plus a small buffer on the profit side once price reaches 2R.
_Avoid_: Trailing stop

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

**Regime**:
The 4H market state (trending or Sideway) used to break down backtest results.
_Avoid_: Market condition
