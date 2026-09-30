# Trading Strategy

The user's mechanical trading strategies on BTCUSDT and the backtest that replays them over historical candles: EMA Pullback (4H trend + 15m entry; its Variant search failed) and Trend Breakout (4H trend-following, being designed).

## EMA Pullback

**EMA Pullback**:
The user's first strategy: in a 4H trend, wait for a pullback into the EMA Zone and enter on an Entry Timeframe Trigger inside the Entry Zone, with SL at the previous low/high and TP at 3R.
_Avoid_: Execution strategy, the Setup, trade-setup (that is its skill)

**Execution**:
One of EMA Pullback's two fixed step lists — Execution 1 (Long) or Execution 2 (Short) — chosen by the 4H EMA26 vs EMA50.
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

## Trend Breakout

**Trend Breakout**:
The user's second strategy: 4H trend-following that enters on a breakout of a price channel and rides the trend with a trailing exit, taking Long and Short Trades on BTCUSDT perpetuals.
_Avoid_: Donchian strategy, Turtle (those name its textbook ancestors)

**Breakout**:
A 4H candle that closes beyond the 20-candle Channel on the side the Side Filter allows; Trend Breakout's only entry signal.
_Avoid_: Signal, Trigger (that is EMA Pullback's)

**Channel**:
The highest high and lowest low of the last N closed 4H candles — N = 20 for a Breakout, 10 for the Trailing Stop.
_Avoid_: Donchian, range, box

**Side Filter**:
Trend Breakout takes Long Breakouts only above the 4H EMA200 and Short Breakouts only below it.
_Avoid_: Trend filter, bias

**Initial Stop**:
The stop placed at entry, 2 × ATR(14) of 4H away from the entry price; it defines the Trade's R.
_Avoid_: SL (EMA Pullback's term), hard stop

**Trailing Stop**:
Trend Breakout's only exit: the more protective of the Initial Stop and the opposite 10-candle Channel, moved only toward profit and only when a 4H candle closes.
_Avoid_: Trailing exit, chandelier, Break-even

**Funding**:
The periodic payment between Long and Short holders of a perpetual future; every Funding event a Trade is open across is paid or received and counts as a cost.
_Avoid_: Swap, carry, financing

## Trade & money management

**Trade**:
One position of one strategy, from entry to exit, sized so that losing R costs the chosen risk % of equity; each strategy holds at most one open Trade at a time (EMA Pullback also at most one per Wave).
_Avoid_: Order, position (as a count)

**R**:
The distance between a Trade's entry and its first stop — the SL in EMA Pullback, the Initial Stop in Trend Breakout; results are measured in multiples of it.
_Avoid_: Risk unit, stop distance

**Break-even (BE)**:
Moving a Trade's SL to entry plus a small buffer on the profit side once price reaches 2R.
_Avoid_: Trailing stop

**Win**:
A Trade that closes with net R above zero after fees, slippage and Funding; win rate is Wins over all Trades. In EMA Pullback a Break-even exit nets below zero, so its Wins are exactly its TP exits.
_Avoid_: Profitable trade, winner (before costs)

**RR**:
The planned ratio of a Trade's TP distance to its R — fixed at 1:3 in EMA Pullback; Trend Breakout has no TP and so no RR.
_Avoid_: Payoff (that is the realized ratio)

**Payoff**:
The realized ratio of average winning R to average losing R over a set of Trades; reported for every strategy, targeted by none.
_Avoid_: RR, reward-to-risk (those are planned)

**Profit Factor (PF)**:
Gross winning R divided by gross losing R over a set of Trades, measured net of fees, slippage and Funding.
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
A strategy's reference rule set, kept unchanged, that its Variants are compared against — Execution 1/2 for EMA Pullback, the textbook Breakout / Initial Stop / Trailing Stop rules for Trend Breakout.
_Avoid_: Original, v1

**Variant**:
The Baseline with a named set of changes applied; it is a candidate until it passes the Acceptance Bar on the Holdout Period.
_Avoid_: Version, new strategy

**Lever**:
One named, separately testable change to a strategy's Baseline; a Variant is a set of Levers.
_Avoid_: Tweak, setting, parameter

**Filter**:
A Lever that only removes Trades the Baseline would take, leaving the remaining Trades unchanged.
_Avoid_: Condition, rule (too broad)

**Search Budget**:
The cap on how many Variants of one strategy may be run on the Tuning Period (20) before that strategy's Variant approach is declared failed.
_Avoid_: Iterations, attempts

**Acceptance Bar**:
The results a Variant must reach, net of costs, to be adopted: for Trend Breakout, PF of at least 2 and Max Drawdown below 15% at the risk the drawdown budget allows, with at least 100 Trades on the Tuning Period and each side (Long, Short) profitable on its own; win rate and Payoff are reported but not targeted. (EMA Pullback's bar was PF 1.5 with RR 1:3.)
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
