"""Reproducible scenario study for the market-making toy simulator.

Example:
    python sensitivity.py --output results/sensitivity

Both policies share each synthetic price/order path. The reported confidence
interval reflects simulation sampling variability, not real-market validity.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import replace
from pathlib import Path

from simulate import Settings, experiment, percentile


def compare_policies(settings: Settings) -> dict[str, float | int]:
    """Return summary statistics with paired confidence intervals."""
    outcomes, _ = experiment(settings)
    fixed = outcomes["fixed spread"]
    adjusted = outcomes["inventory aware"]
    differences = [a.pnl_dollars - b.pnl_dollars for a, b in zip(adjusted, fixed)]
    n = len(differences)
    mean_difference = statistics.mean(differences)
    sem = statistics.stdev(differences) / math.sqrt(n)
    fixed_pnl = [item.pnl_dollars for item in fixed]
    adjusted_pnl = [item.pnl_dollars for item in adjusted]
    return {
        "volatility_cents": settings.price_shock_sd_cents,
        "skew_cents_per_share": settings.inventory_skew_cents,
        "trials": n,
        "fixed_mean_pnl": round(statistics.mean(fixed_pnl), 4),
        "aware_mean_pnl": round(statistics.mean(adjusted_pnl), 4),
        "paired_mean_delta": round(mean_difference, 4),
        "paired_ci95_low": round(mean_difference - 1.96 * sem, 4),
        "paired_ci95_high": round(mean_difference + 1.96 * sem, 4),
        "fixed_pnl_sd": round(statistics.stdev(fixed_pnl), 4),
        "aware_pnl_sd": round(statistics.stdev(adjusted_pnl), 4),
        "fixed_pnl_p05": round(percentile(fixed_pnl, 5), 4),
        "aware_pnl_p05": round(percentile(adjusted_pnl, 5), 4),
        "fixed_negative_pnl_rate": round(sum(x < 0 for x in fixed_pnl) / n, 4),
        "aware_negative_pnl_rate": round(sum(x < 0 for x in adjusted_pnl) / n, 4),
        "fixed_mean_max_abs_inventory": round(statistics.mean(t.max_abs_inventory for t in fixed), 4),
        "aware_mean_max_abs_inventory": round(statistics.mean(t.max_abs_inventory for t in adjusted), 4),
        "fixed_mean_trades": round(statistics.mean(t.trades for t in fixed), 4),
        "aware_mean_trades": round(statistics.mean(t.trades for t in adjusted), 4),
    }


def sweep(
    base: Settings, volatilities: list[float], skews: list[float]
) -> list[dict[str, float | int]]:
    """Run every requested combination, retaining paired draws within each test."""
    if not volatilities or not skews:
        raise ValueError("Provide at least one volatility and skew.")
    if any(v < 0 or not math.isfinite(v) for v in volatilities):
        raise ValueError("Volatility must be finite and nonnegative.")
    if any(s < 0 or not math.isfinite(s) for s in skews):
        raise ValueError("Skew must be finite and nonnegative.")
    # Without this restriction, strong inventory shifts cross the synthetic mid
    # while the toy fill model still treats both quotes as passive orders.
    if max(skews) * base.inventory_limit >= base.spread_cents / 2:
        raise ValueError("Skew × inventory limit must be below half the spread to avoid crossing the synthetic mid.")
    return [
        compare_policies(replace(base, price_shock_sd_cents=volatility, inventory_skew_cents=skew))
        for volatility in volatilities
        for skew in skews
    ]


def save_results(rows: list[dict[str, float | int]], target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    with (target / "sensitivity.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    volatilities = sorted({row["volatility_cents"] for row in rows})
    fig, ax = plt.subplots(figsize=(8.3, 4.9), dpi=160)
    for volatility in volatilities:
        subset = sorted((r for r in rows if r["volatility_cents"] == volatility), key=lambda r: r["skew_cents_per_share"])
        ax.plot([r["skew_cents_per_share"] for r in subset], [r["paired_mean_delta"] for r in subset], marker="o", label=f"Volatility {volatility:g}¢")
    ax.axhline(0, linewidth=1, linestyle="--")
    ax.set(xlabel="Inventory skew (¢ per share)", ylabel="Mean paired P&L advantage ($)", title="Synthetic sensitivity: inventory-aware minus fixed P&L")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(target / "mean_delta_by_skew.png")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8.3, 4.9), dpi=160)
    for volatility in volatilities:
        subset = sorted((r for r in rows if r["volatility_cents"] == volatility), key=lambda r: r["skew_cents_per_share"])
        ax.plot([r["skew_cents_per_share"] for r in subset], [r["aware_pnl_p05"] for r in subset], marker="o", label=f"Volatility {volatility:g}¢")
    ax.axhline(0, linewidth=1, linestyle="--")
    ax.set(xlabel="Inventory skew (¢ per share)", ylabel="Inventory-aware 5th-percentile P&L ($)", title="Synthetic sensitivity: downside P&L by inventory skew")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(target / "tail_pnl_by_skew.png")
    plt.close(fig)


def float_list(text: str) -> list[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results/sensitivity"))
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--steps", type=int, default=250)
    parser.add_argument("--seed", type=int, default=20261121)
    parser.add_argument("--volatilities", type=float_list, default=[5.0, 15.0, 30.0])
    parser.add_argument("--skews", type=float_list, default=[0.0, 0.5, 1.0, 1.5])
    args = parser.parse_args()
    rows = sweep(Settings(trials=args.trials, steps=args.steps, seed=args.seed), args.volatilities, args.skews)
    save_results(rows, args.output)
    print("vol(cents)  skew  fixed P&L  adjusted P&L  paired advantage [95% Monte Carlo CI]")
    for row in rows:
        print(f"{row['volatility_cents']:>10g} {row['skew_cents_per_share']:>5g} "
              f"{row['fixed_mean_pnl']:>10.3f} {row['aware_mean_pnl']:>13.3f}  "
              f"{row['paired_mean_delta']:+.3f} [{row['paired_ci95_low']:+.3f}, {row['paired_ci95_high']:+.3f}]")
    print(f"Results written to {args.output.resolve()}")


if __name__ == "__main__":
    main()
