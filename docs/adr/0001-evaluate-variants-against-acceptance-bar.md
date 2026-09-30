# Evaluate Variants against a ranked Acceptance Bar with a single-use Holdout Period

The user asked for PF 3, a 50–60% win rate, RR 1:3, Max Drawdown under 15% and 2% risk per Trade. These targets conflict. At a fixed 1:3, PF 3 is the same target as a 50% win rate. Even at a 50% win rate, 2% risk keeps Max Drawdown under 15% in only about 43% of 500-trade Monte Carlo paths. The Baseline itself makes 23.6% wins and PF 0.65 after costs. We therefore ranked the targets:

- **Hard limits:** Max Drawdown under 15% and a planned RR of 1:3.
- **Pass mark:** PF ≥ 1.5 after costs. PF 3 is a Stretch Target.
- **Win rate:** reported, not targeted.
- **Risk %:** an output, not a fixed input. It is the largest of {0.5, 0.75, 1, 1.5, 2}% whose resampled 95th-percentile Max Drawdown stays below 15%.

Variants are built only from pre-declared Levers, with at most 3 threshold values each. They are compared on the Tuning Period (2021-10 → 2024-12) under a Search Budget of 20 Variants. Exactly one Finalist is run once on the Holdout Period (2025-01 onward). If it fails there, the Variant approach is abandoned in favour of a new strategy, with no retry using the runner-up. The reason is that each extra Variant and each look at the Holdout Period makes a lucky history-fit result more likely.

## Outcome (2026-09-30)

The Variant approach failed. Twelve single-Lever Variants (V01–V12) were run on the Tuning Period, and none reached the Acceptance Bar. The best after-cost PF was 0.79; the Baseline's was 0.65. Before costs, expectancy stayed between −0.35R and +0.09R, so there was no edge left to combine. The user declared the approach failed without using the remaining Search Budget. The Holdout Period is still unused. Work moves to a completely new strategy.

## Considered Options

- **Keep 2% risk and target PF 3 directly:** rejected. The two targets conflict with the Max Drawdown limit, and tuning towards PF 3 on five years of one symbol would mostly fit noise.
- **Measure before costs:** rejected. Costs are about 0.23R per Trade at 15m stop widths, which is larger than the Baseline's whole before-cost edge (+0.06R).

## Consequences

- Once the Holdout Period has been used, it cannot be used again. Any later strategy work must either use data collected after 2026-09 or accept that it has no clean test period.
- A Variant that passes becomes the `trade-setup` Execution 1/2 only after a paper-trade period of at least 30 Trades or 3 months, whichever is later. The Baseline stays documented.
