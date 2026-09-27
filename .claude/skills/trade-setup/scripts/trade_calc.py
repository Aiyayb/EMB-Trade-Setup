"""
trade_calc.py - position size / TP / break-even calculator for the trade-setup rules.

Rules: risk 2% of balance per trade, TP = 3R, move SL to break-even (+buffer) at 2R.

Usage:
  python trade_calc.py --balance 10000 --entry 65000 --sl 64200
  python trade_calc.py --balance 10000 --entry 65000 --sl 64200 --leverage 10 --target 67800
  python trade_calc.py --balance 10000 --entry 65000 --sl 64200 --json
"""

import argparse
import json
import sys


def calc(balance, entry, sl, risk_pct=2.0, rr=3.0, be_at=2.0, be_buffer_pct=0.1,
         leverage=None, mmr_pct=0.5, target=None, contract_size=None):
    if entry <= 0 or sl <= 0 or balance <= 0:
        raise ValueError("balance, entry and sl must be positive")
    if entry == sl:
        raise ValueError("entry and sl cannot be equal")

    side = "LONG" if sl < entry else "SHORT"
    d = 1 if side == "LONG" else -1
    r = abs(entry - sl)
    risk_amount = balance * risk_pct / 100
    size = risk_amount / r
    notional = size * entry

    out = {
        "side": side,
        "entry": entry,
        "stop_loss": sl,
        "R_distance": r,
        "sl_distance_pct": r / entry * 100,
        "risk_pct": risk_pct,
        "risk_amount": risk_amount,
        "position_size_units": size,
        "notional": notional,
        "take_profit": entry + d * rr * r,
        "rr": rr,
        "reward_amount": risk_amount * rr,
        "be_trigger_price": entry + d * be_at * r,
        "be_new_sl": entry * (1 + d * be_buffer_pct / 100),
        "be_buffer_pct": be_buffer_pct,
        "warnings": [],
    }
    if out["take_profit"] <= 0:
        out["warnings"].append("TP at 3R is <= 0 - SL is far too wide for a short.")

    if contract_size:
        out["contracts"] = size / contract_size

    if leverage:
        out["leverage"] = leverage
        out["margin_required"] = notional / leverage
        liq_dist_pct = 100 / leverage - mmr_pct
        out["approx_liq_distance_pct"] = liq_dist_pct
        out["approx_liq_price"] = entry * (1 - d * liq_dist_pct / 100)
        if out["sl_distance_pct"] >= liq_dist_pct:
            out["warnings"].append(
                f"SL distance {out['sl_distance_pct']:.2f}% >= approx liquidation distance "
                f"{liq_dist_pct:.2f}% at {leverage}x - you'd be liquidated before SL. Lower the leverage.")
        if out["margin_required"] > balance:
            out["warnings"].append("Margin required exceeds balance - increase leverage or skip.")

    if target is not None:
        target_rr = d * (target - entry) / r
        out["structural_target"] = target
        out["structural_target_rr"] = target_rr
        if target_rr < rr:
            out["warnings"].append(
                f"Structural target {target} only gives {target_rr:.2f}R (< {rr}R). "
                "By the rules: no trade, or find a tighter SL / better entry.")
    return out


def fmt(x):
    if abs(x) >= 1000:
        return f"{x:,.2f}"
    if abs(x) >= 1:
        return f"{x:,.4f}"
    return f"{x:.6f}"


def print_report(o):
    print(f"=== {o['side']} ===")
    print(f"Entry            : {fmt(o['entry'])}")
    print(f"Stop loss        : {fmt(o['stop_loss'])}   (1R = {fmt(o['R_distance'])}, {o['sl_distance_pct']:.2f}%)")
    print(f"Take profit {o['rr']:g}R   : {fmt(o['take_profit'])}")
    print(f"Risk {o['risk_pct']:g}%          : {fmt(o['risk_amount'])}")
    print(f"Reward           : {fmt(o['reward_amount'])}")
    print(f"Position size    : {fmt(o['position_size_units'])} units   (notional {fmt(o['notional'])})")
    if "contracts" in o:
        print(f"Contracts        : {fmt(o['contracts'])}")
    print(f"Break-even       : when price hits {fmt(o['be_trigger_price'])} (2R) -> move SL to "
          f"{fmt(o['be_new_sl'])} (entry {'+' if o['side'] == 'LONG' else '-'}{o['be_buffer_pct']:g}%)")
    if "leverage" in o:
        print(f"Leverage {o['leverage']:g}x     : margin {fmt(o['margin_required'])}, approx liq "
              f"{fmt(o['approx_liq_price'])} ({o['approx_liq_distance_pct']:.2f}% away)")
    if "structural_target" in o:
        print(f"Structural target: {fmt(o['structural_target'])} = {o['structural_target_rr']:.2f}R")
    for w in o["warnings"]:
        print(f"WARNING: {w}")


def main():
    p = argparse.ArgumentParser(description="Trade-setup position calculator (2% risk, 1:3 RR, BE at 2R)")
    p.add_argument("--balance", type=float, required=True, help="account equity")
    p.add_argument("--entry", type=float, required=True)
    p.add_argument("--sl", type=float, required=True, help="stop loss price (below entry = long, above = short)")
    p.add_argument("--risk-pct", type=float, default=2.0)
    p.add_argument("--rr", type=float, default=3.0)
    p.add_argument("--be-at", type=float, default=2.0, help="R multiple that triggers break-even")
    p.add_argument("--be-buffer-pct", type=float, default=0.1, help="BE SL offset beyond entry, %% (covers fees)")
    p.add_argument("--leverage", type=float)
    p.add_argument("--mmr-pct", type=float, default=0.5, help="maintenance margin rate %% for liq estimate")
    p.add_argument("--target", type=float, help="structural target price to check against 3R")
    p.add_argument("--contract-size", type=float, help="units per contract, e.g. 0.01 for OKX BTC-USDT-SWAP")
    p.add_argument("--json", action="store_true")
    a = p.parse_args()

    try:
        o = calc(a.balance, a.entry, a.sl, a.risk_pct, a.rr, a.be_at, a.be_buffer_pct,
                 a.leverage, a.mmr_pct, a.target, a.contract_size)
    except ValueError as e:
        sys.exit(f"error: {e}")
    if a.json:
        print(json.dumps(o, indent=2))
    else:
        print_report(o)


if __name__ == "__main__":
    main()
