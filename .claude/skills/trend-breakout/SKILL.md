---
name: trend-breakout
description: The user's second strategy, Trend Breakout — 4H BTCUSDT-perp trend-following. A 4H close beyond the 20-candle Channel, on the side of the 4H EMA200 (Side Filter), enters at that close. The Initial Stop is 2 × ATR(14) and defines R. A Trailing Stop on the opposite 10-candle Channel is the only exit (no TP). Stops are checked on 15m candles, and size is risk % from a 15% max-drawdown budget (about 0.5–1%). Also contains the backtest engine (fees, slippage, real Funding, mark-to-market drawdown) and the pre-registered Variant runner with a one-time Holdout lock. Use whenever the user asks whether there is a breakout or trend trade now, where the stop or trailing stop is, how big a Trend Breakout position should be, wants to backtest, compare or improve Trend Breakout, asks about PF 2 / drawdown targets, Donchian / Turtle / channel breakouts on BTC, or mentions the Finalist or the Holdout Period — even if they don't name the skill. For the old EMA-pullback setup (Execution 1/2, Fib, Engulfing) use trade-setup / backtest-setup instead.
---

# Trend Breakout

The user's second mechanical strategy, designed on 2026-09-30 to reach **PF ≥ 2 and Max Drawdown < 15%** after all costs (docs/adr/0002). Vocabulary is defined in `CONTEXT.md`: Breakout, Channel, Side Filter, Initial Stop, Trailing Stop, Funding, Win, Payoff, Baseline, Variant, Lever, Filter, Acceptance Bar, Tuning Period, Holdout Period, Finalist and Search Budget. Its sibling strategy, EMA Pullback, lives in `trade-setup` and `backtest-setup`; don't mix the two rule sets.

You are not a financial advisor. Present everything as "by your Trend Breakout rules…". Never place or manage orders; the user trades on OKX themselves. Reply in the user's language (Thai or English), keeping technical terms in English.

## Rules (Baseline)

| Step | Rule |
|---|---|
| Breakout | A **closed** 4H candle closes above the highest high (Long) or below the lowest low (Short) of the **previous 20** closed 4H candles |
| Side Filter | Long only if that close is above 4H **EMA200**; Short only if below |
| Entry | At the Breakout candle's close. One Trade at a time; after an exit, the next Breakout may enter again |
| Initial Stop | Entry ∓ **2 × ATR(14)** (Wilder) of that candle. This distance is **R** |
| Trailing Stop | The only exit (no TP). After each 4H close it moves to the lowest low (Long) / highest high (Short) of the last **10** closed candles, but only toward profit and never looser than the Initial Stop |
| Stops | Checked on 15m candles. A candle opening through the stop fills at its open |
| Size | units = equity × risk % ÷ R, with notional ≤ 3× equity. Risk % comes from the drawdown budget (below), **not** 2% |
| Costs | Fee 0.05% + slippage 0.02% per side, plus Funding on every event held across (Binance BTCUSDT perp history as proxy) |

These rules stay fixed until a Variant passes the Holdout Period. After that, the Finalist's Levers become the rules here (see "Status").

## Live chart check

```bash
python .claude/skills/trend-breakout/scripts/check.py --equity <equity> --risk <risk %>
python .claude/skills/trend-breakout/scripts/check.py --open long --entry <price> --since "YYYY-MM-DD HH:MM"
python .claude/skills/trend-breakout/scripts/check.py --until "YYYY-MM-DD HH:MM"      # the chart as it was then
```

The check reports:
- the last closed 4H candle and how old the data is,
- EMA200 and which side is allowed,
- the 20-candle Channel,
- whether this candle is a Breakout; if so, the entry, Initial Stop, R and position size,
- if not, the exact close the next candle needs.

Trailing Stops are shown side by side for the **Baseline** (10-candle Channel) and **T05** (best close since entry ∓ 3 × ATR, read from `VARIANTS`), because both are being paper-traded. Entry and Initial Stop are the same for both. With `--open` it replays both Trailing Stops from the Breakout candle (the open time, in UTC) to now, and warns if a stop has already been hit.

**Always refresh data first**: `python fetch_btc_data.py --tf 15m 4H 1D` and `python fetch_funding.py`. The check warns when data is more than 4 h old. It uses the same rule functions as the backtest (`engine.py`), and a test confirms every backtest entry is a Breakout the check sees at that candle.

When presenting a live check, give: the verdict (Breakout Long / Short / none), entry and Initial Stop, R as % of price, and size at the user's risk. Mention the Trailing Stop plan (10-candle Channel). If Funding is unusually high (≥ 0.03% per 8h), note it as context; it only filters Trades if the Finalist includes that Lever.

## Backtest

```bash
python .claude/skills/trend-breakout/scripts/backtest.py --to 2024-12-31                 # Baseline, Tuning Period
python .claude/skills/trend-breakout/scripts/backtest.py --to 2024-12-31 --adx-min 20    # with a Lever
```

| Option | Default | Meaning |
|---|---|---|
| `--from` / `--to` | 2021-10-01 / end of data | entry window (UTC); earlier data is warm-up |
| `--risk-pct` | 0.75 | risk per Trade (the report also shows what the DD budget allows) |
| `--fee-pct` / `--slippage-pct` / `--no-funding` | 0.05 / 0.02 / off | costs |
| `--side` | both | long / short / both (both is the rule; the others are for inspection only) |
| Levers | off | `--entry-n --exit-n --stop-atr --chandelier-atr --d1-ema --adx-min --funding-max --pyramid` |

Any run with a Lever that reaches 2025-01-01 or later is refused: that period is the Holdout Period.

Each run writes `backtests/tb-<timestamp>/` containing:
- `trades.csv`: every Trade with entry, Initial Stop, exit, R before and after costs, Funding R, and the indicator values at entry,
- `summary.json`: overall stats; by side, year, side × year and exit reason; the risk budget; the Assumptions,
- `report.html`,
- `assumptions.md`.

Max Drawdown is **mark-to-market**: open Trades are valued at every 4H close, because trend Trades give back open profit before the Trailing Stop catches up.

## Variants, the Acceptance Bar and the Holdout Period

```bash
python .claude/skills/trend-breakout/scripts/variants.py                 # Baseline + all registered, Tuning Period
python .claude/skills/trend-breakout/scripts/variants.py --holdout <ID>  # the single Finalist run — once, ever
```

- **Registered Variants.** `VARIANTS` in `variants.py` lists T01–T11, fixed before any run. The list is append-only: add combinations below T11, never edit a row that has already run. The Search Budget is 20.
- **Pass (Tuning Period, after all costs).** All of the following:
  - PF ≥ 2,
  - mark-to-market Max DD < 15% at the risk the DD budget picks (the largest of {0.5, 0.75, 1, 1.5, 2}% whose actual and bootstrap-95th-percentile DD are both < 15%),
  - ≥ 100 Trades,
  - Long PF ≥ 1 and Short PF ≥ 1.
- **Finalist.** The highest PF among passes; within 0.1 PF, fewer Levers wins; then higher PF.
- **`--holdout`.** It first re-runs the whole Tuning Period and refuses unless the ID is the Finalist. It then runs 2025-01-01 → end at the Finalist's Tuning risk and writes `docs/holdout-ledger.json`. That ledger is shared with EMA Pullback: **the Holdout Period can be used once, by one strategy.**
- **Before `--holdout`, always get the user's explicit go-ahead.** It cannot be undone.
- **Output.** `backtests/tb-variants-<timestamp>/leaderboard.html` links each Variant's report.

## Status (2026-09-30)

- **Baseline** on the Tuning Period: 165 Trades, PF 1.72, Payoff 2.52, win 40.6%, +0.33R per Trade, risk budget 0.5%, MTM DD 6.5%. It fails PF ≥ 2.
- **Registered run: 3 of 11 Variants pass.** T05 (Chandelier 3 ATR, PF 2.18), T07 (1D EMA50 agrees, PF 2.15), T08 (ADX ≥ 20, PF 2.10).
- **Finalist T05 failed the Holdout Period** (run 2026-09-30, 2025-01 → 2026-09):
  - PF 1.47 vs 2.18 on the Tuning Period,
  - 87 Trades, Payoff 2.52, +0.26R per Trade,
  - Long / Short PF 1.48 / 1.45, mark-to-market DD 6.1%, CAGR 6.2% at 0.5% risk.

  It is profitable after costs but below the PF 2 target. The Holdout Period is used up (`docs/holdout-ledger.json`), and there is no retry with the runner-up (docs/adr/0002 Outcome).
- **The rules above remain the Baseline.** None of the Variants has been adopted. The next step (forward-test on new data, lower the target, or redesign) is the user's decision.

## Verifying the engine

```bash
python -m unittest discover -s .claude/skills/trend-breakout/scripts -p "test_*.py"
```

The tests cover:
- no look-ahead in any indicator,
- Channel excludes the current candle,
- Side Filter,
- Trailing Stop only toward profit,
- chandelier,
- gap fills,
- notional cap,
- costs and R,
- Funding sign and timing,
- Filters only remove Trades,
- mark-to-market drawdown,
- every backtest entry matches the live check's view of that candle.
