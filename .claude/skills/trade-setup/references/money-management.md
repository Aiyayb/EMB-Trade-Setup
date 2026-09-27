# Money Management reference

Contents: 10. Risk-to-Reward 1:3 · 11. Risk 2% per trade · 12. Break-even at 2R · Leverage notes · Worked examples

These three rules are fixed. Setups adapt to them — never the other way around.

---

## Definitions

- **R** (1R) = the distance from entry to stop loss: `R = |entry − SL|`.
- Long: SL < entry. Short: SL > entry.

## 10. Risk-to-Reward = 1:3

- `TP = entry + 3R` (long) · `TP = entry − 3R` (short).
- If a structural obstacle (HTF level, EMA200, pattern target, prior swing) sits between entry and the 3R TP, the trade is **not taken**. Do not shrink the target to fit — find a better entry (tighter SL) or skip.
- With 1:3, the break-even win rate is 25% (before fees), so skipping marginal setups is cheap.

## 11. Risk per trade = 2% of portfolio

- `risk_amount = balance × 0.02`
- `position_size (units) = risk_amount / R`
- `notional = position_size × entry`
- Size comes from SL distance. A wider SL → smaller position; the dollar risk stays 2%.
- Use current account equity (not starting balance) each time.
- For contracts (e.g. OKX futures), convert units to contracts with the instrument's contract size (e.g. BTC-USDT-SWAP: 1 contract = 0.01 BTC — verify on the exchange).
- Fees and slippage slightly increase real risk; if precision matters, subtract round-trip fees from risk_amount first.

## 12. Break-even at 2R

- **Trigger:** price moves in the profit direction to **2R** from entry.
  - Long: `BE_trigger = entry + 2R` · Short: `BE_trigger = entry − 2R`.
- **Action:** move SL to entry **plus a small buffer on the profit side**, so the worst case is a small win that covers fees.
  - Long: `new_SL = entry × (1 + buffer)` (above entry) · Short: `new_SL = entry × (1 − buffer)` (below entry).
  - Default buffer = 0.1% (≈ round-trip taker fees). Adjust to the user's fee tier.
- After BE, the trade is "free": risk is ~0, TP stays at 3R.
- Trigger on price *reaching* 2R (touch). If the user prefers a candle close beyond 2R, state that assumption.

## Leverage notes

- Leverage does **not** change risk if size is computed from the 2% rule — it only changes the margin locked up.
- `margin = notional / leverage`.
- **Liquidation check (isolated):** approximate liquidation distance ≈ `1/leverage − maintenance margin rate` (~0.4–0.5% for BTC). If the SL distance % is greater than that, you would be liquidated before the SL is hit → reduce leverage.

## Worked examples

**Long** — balance 10,000 USDT, entry 65,000, SL 64,200
- R = 800 · risk = 200 USDT · size = 200 / 800 = 0.25 BTC · notional = 16,250 USDT
- TP = 65,000 + 2,400 = **67,400** (reward 600 USDT = 3 × 200)
- BE trigger = 65,000 + 1,600 = **66,600** → new SL = 65,000 × 1.001 = **65,065**
- At 10× leverage: margin = 1,625 USDT; SL distance 1.23% < ~9.5% liq distance ✅

**Short** — balance 5,000 USDT, entry 3,000, SL 3,060
- R = 60 · risk = 100 USDT · size = 100 / 60 = 1.667 units · notional ≈ 5,000 USDT
- TP = 3,000 − 180 = **2,820**
- BE trigger = 3,000 − 120 = **2,880** → new SL = 3,000 × 0.999 = **2,997**

Use `scripts/trade_calc.py` to compute these exactly.
