---
name: backtest-setup
description: Backtest the user's trade-setup strategy (4H EMA26/50 trend + 15m Zigzag/Fib/Engulfing entry, RR 1:3, 2% risk, BE at 2R) over the BTCUSDT candle files in data/ — bar by bar with no look-ahead — and report win rate, expectancy in R (gross and net of fees/slippage), drawdown, and breakdowns by side, year, regime, CHoCH-Retrace and trigger, plus an auditable per-trade log. Use whenever the user wants to backtest / test / validate / measure the strategy or Execution 1/2 on history, asks "how did the setup perform in 2024", wants to compare costs or sides, asks why a backtest trade entered/exited where it did, or wants to check the engine against the chart analyzer — even if they don't say "backtest".
---

# Backtest Setup

Replays the trade-setup strategy over historical 4H + 15m candles and reports how it would have done. The **rules live in the `trade-setup` skill** (Execution 1/2, filters, money management) — never restate or change them here; if a rule needs interpreting, it belongs in the run's Assumptions. Vocabulary (Setup, HTF Setup, Wave, Entry Zone, Trigger, Sideway, Setup Expiry, R, Backtest Run, Trade Log, Regime) is defined in `CONTEXT.md` at the repo root.

You are not a financial advisor: present results as "how your rules performed on this data", not as a recommendation to trade. Reply in the user's language (Thai or English), keeping technical terms in English.

## Flow

```
data/BTCUSDT_4H.csv + BTCUSDT_15m.csv
 → walk every 15m bar; only closed 4H bars are visible
 → 4H: trend (EMA26/50) · Sideway filter · Wave · EMA Zone · 4H Trigger in the zone  = HTF Setup
 → 15m: Wave completes after the 4H Trigger · Fib Time 0.5 · retrace 0.5–1.0 · Trigger in the Entry Zone
 → Trade: entry at Trigger close, SL previous low/high, TP 3R, size 2% of equity, BE at 2R
 → manage bar by bar (SL checked first) → Trade Log + stats + report
```

## Run it

```bash
python .claude/skills/backtest-setup/scripts/backtest.py --from 2021-10-01 --to 2026-09-26
```

| Option | Default | Meaning |
|---|---|---|
| `--from` / `--to` | 2021-10-01 / end of data | window for **entries** (UTC dates); earlier data is indicator warm-up (EMA200 on 4H needs ~33 days) |
| `--side` | both | `long`, `short` or `both` (reports always split Long/Short) |
| `--balance` | 10000 | starting equity; risk compounds on current equity |
| `--risk-pct` | 2 | risk per Trade |
| `--fee-pct` / `--slippage-pct` | 0.05 / 0.02 | per side, on entry and every exit |
| `--be-buffer-pct` | 0.1 | BE stop = entry ± this % |
| `--leverage` | 10 | only flags Trades whose SL is beyond the approx. liquidation distance |
| `--out` | `backtests/<timestamp>-<side>` | output folder (gitignored) |

Runs in a few seconds. To test costs, run again with `--fee-pct 0 --slippage-pct 0` (or compare the gross vs net columns already in every report).

## Outputs (in the run folder)

- `trades.csv` — one row per Trade: entry/exit, SL/TP/BE levels, R result (net `r_multiple` and `gross_r`), exit reason (SL / TP / BE / END), and the checklist state at entry: 4H trend, Sideway distance, 4H Wave, EMAs touched, 4H Trigger, 15m Wave, Fib 0.5, Fib Time bars, deepest retrace, 15m Trigger, CHoCH-Retrace tag.
- `summary.json` — all stats: overall, by side, year, Regime (EMA8–EMA200 distance at entry), CHoCH-Retrace, trigger type, exit reason; % of 4H time in uptrend / downtrend / Sideway per year.
- `report.html` — self-contained page: stat tiles, equity curve (log), cumulative R gross vs net, breakdown tables, full Trade Log, Assumptions. View it with the `backtest-reports` preview server (`.claude/launch.json`) at `http://localhost:8765/<run folder>/report.html`, or open the file directly.
- `assumptions.md` — parameters and every rule interpretation the run used.

## Presenting results

Lead with the verdict in R: trades, win rate, **net and gross expectancy**, profit factor, max drawdown, final equity. Then point out what stands out in the breakdowns — Long vs Short, stable or unstable across years, Regime, whether CHoCH-Retrace trades do better, cost drag (gross − net expectancy ≈ costs per Trade in R; tight 15m stops make costs large in R). Link the report. Don't suggest rule changes as if they were the user's rules; if the user wants to experiment, keep the rules fixed on the first 3 years and confirm on the last 2 (in-sample / out-of-sample) and say so.

## Explaining a single backtest trade

Take the row from `trades.csv`, then rebuild the chart at entry with the trade-setup analyzer on both timeframes, using the **open time of the entry candle** (15m `trigger_time`) and the last closed 4H bar:

```bash
python .claude/skills/trade-setup/scripts/analyze_chart.py --file data/BTCUSDT_4H.csv --until "<last closed 4H open time>"
python .claude/skills/trade-setup/scripts/analyze_chart.py --file data/BTCUSDT_15m.csv --bias long --until "<trigger_time>"
```

Walk the 10 steps (trade-setup "Reviewing a past trade") and compare with the row's checklist columns.

## Verifying the engine

```bash
python -m unittest discover -s .claude/skills/backtest-setup/scripts -p "test_*.py"
python .claude/skills/backtest-setup/scripts/parity_check.py --random 20 --entries 10
```

- Unit tests: incremental Zigzag = batch Zigzag at every bar, trigger detection, fill/BE/cost rules.
- Parity check: at random bars and real entry bars, the engine's 4H/15m state must equal a fresh `analyze_chart` run cut at that moment (and the 4H bar used must be closed). Run it after any change to `analyze_chart.py` or the engine; any mismatch means look-ahead or drift.

## Engine conventions (also listed in every run's Assumptions)

Conservative fills: SL before TP/2R in the same bar; BE takes effect the bar after 2R; a bar opening through the stop fills at the open; costs on every exit. One open Trade at a time, one Trade per 15m Wave; open Trades run to SL/TP/BE even if the 4H trend flips. 15m Trigger must touch the Fib 0.5 level (pattern low/high), Engulfing needs a Rejection wick ≥ 50%, 4H Trigger must touch EMA8. HTF Setup expires on EMA26/50 flip, Sideway, or a newer 4H Trigger.
