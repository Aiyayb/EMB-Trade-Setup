# Build Trend Breakout as a new strategy with PF 2, no fixed RR, and costs that include Funding

The Execution 1/2 Variants failed (ADR 0001, Outcome). The user asked for a completely new strategy targeting PF 2 and Max Drawdown below 15%. Published research and 13 textbook probes on the Tuning Period pointed to one family: 4H trend-following breakouts. The best probe, a Donchian 20/10 with a 2-ATR initial stop and an EMA200 side filter, reached PF 1.84 after costs, with only about 0.05R of costs per Trade. Mean-reversion, overnight-seasonality and 1H versions all failed after costs.

We decided:
- **Acceptance Bar:** PF ≥ 2 and Max Drawdown < 15%, after costs.
- **RR 1:3 dropped:** a fixed 3R TP cut the probe's PF from 1.84 to 1.45, because trend-following earns from a few large winners.
- **Risk % still comes from the drawdown budget,** capped at 2%. Expect about 0.75%.
- **Win rate is not a target.**
- **Separate from the old strategy:** Trend Breakout gets its own skill, glossary section and engine.
- **Same Holdout Period** (2025-01 onward, still unused), with a fresh Search Budget of 20.
- **Costs include real Funding.** Binance BTCUSDT perpetual history is the proxy, because OKX publishes only about 3 months.

Later rounds added the following:
- **Baseline:** the textbook rules exactly as probed.
  - Breakout: a 4H close beyond the 20-candle Channel.
  - Side Filter: EMA200 on 4H.
  - Initial Stop: 2 × ATR(14).
  - Trailing Stop: the opposite 10-candle Channel.
- **Both sides are kept always.** Long-only is not allowed as a Lever.
- **Win** means net R > 0.
- **Execution:** stops are checked on 15m candles.
- **Sizing:** fixed risk %, no pyramiding, notional capped at 3× equity.
- **Extra pass checks:** at least 100 Trades, and each side's PF ≥ 1.
- **Pre-registered Levers:** eleven (T01–T11).
- **The old strategy is renamed EMA Pullback.**

## Considered Options

- **Keep RR 1:3 and 2% risk as the user first asked:** rejected. Both conflict with PF 2 and DD < 15% on the evidence above.
- **Long-only, which has the better numbers:** left open for the design. Long PF was 2.26 but 1.02 in the 2022 bear market. Short PF was 1.21, and 1.41 in 2022.

## Consequences

- The 13 probes that chose this family were run on the Tuning Period and are not counted against the Search Budget. The single Holdout run is the only correction for that selection.
- `backtest-setup/scripts/risk.py` and the cost model are shared by both strategies. Nothing else in the Execution 1/2 engine is.
