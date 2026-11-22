"""A small, reproducible market-making experiment using synthetic data.

This is a simulation, not a backtest of real prices or a profitable strategy.
Run: python simulate.py --output results
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    trials: int = 2000
    steps: int = 250
    seed: int = 20261121
    initial_mid_cents: float = 10_000.0
    price_shock_sd_cents: float = 5.0
    spread_cents: float = 20.0
    fill_scale: float = 0.55
    fill_decay_per_cent: float = 0.14
    inventory_limit: int = 6
    inventory_skew_cents: float = 1.0


@dataclass(frozen=True)
class TrialResult:
    pnl_dollars: float
    max_abs_inventory: int
    terminal_inventory: int
    trades: int


def fill_probability(distance_from_mid_cents: float, settings: Settings) -> float:
    """Greater distance from mid means fewer synthetic customer orders."""
    return min(1.0, settings.fill_scale * math.exp(-settings.fill_decay_per_cent * max(0.0, distance_from_mid_cents)))


def simulate_path(
    events: list[tuple[float, float, float]], settings: Settings, skew_cents_per_share: float
) -> TrialResult:
    """Apply a quoting policy to the same shocks and fill draws as its peer."""
    mid = settings.initial_mid_cents
    cash_cents = 0.0
    inventory = 0
    max_abs_inventory = 0
    trades = 0
    half_spread = settings.spread_cents / 2.0

    for price_shock, bid_draw, ask_draw in events:
        # When long, lower both quotes. A lower ask helps reduce inventory.
        quote_shift = -skew_cents_per_share * inventory
        bid = mid - half_spread + quote_shift
        ask = mid + half_spread + quote_shift
        assert bid < ask

        bid_fill = inventory < settings.inventory_limit and bid_draw < fill_probability(mid - bid, settings)
        ask_fill = inventory > -settings.inventory_limit and ask_draw < fill_probability(ask - mid, settings)
        if bid_fill:
            inventory += 1
            cash_cents -= bid
            trades += 1
        if ask_fill:
            inventory -= 1
            cash_cents += ask
            trades += 1
        max_abs_inventory = max(max_abs_inventory, abs(inventory))
        mid += price_shock

    # Mark any remaining inventory at the final synthetic mid price.
    pnl = (cash_cents + inventory * mid) / 100.0
    return TrialResult(pnl, max_abs_inventory, inventory, trades)


def percentile(numbers: list[float], percentage: float) -> float:
    ordered = sorted(numbers)
    position = (len(ordered) - 1) * percentage / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def experiment(settings: Settings) -> tuple[dict[str, list[TrialResult]], list[dict[str, float | str]]]:
    if settings.trials < 2 or settings.steps < 1 or settings.inventory_limit < 1:
        raise ValueError("Use at least two trials, one step and an inventory limit of one.")
    rng = random.Random(settings.seed)
    outcomes: dict[str, list[TrialResult]] = {"fixed spread": [], "inventory aware": []}
    for _ in range(settings.trials):
        # Both policies see exactly the same synthetic price shocks and fill draws.
        events = [
            (rng.gauss(0.0, settings.price_shock_sd_cents), rng.random(), rng.random())
            for _ in range(settings.steps)
        ]
        outcomes["fixed spread"].append(simulate_path(events, settings, 0.0))
        outcomes["inventory aware"].append(
            simulate_path(events, settings, settings.inventory_skew_cents)
        )

    summary: list[dict[str, float | str]] = []
    for name, trials in outcomes.items():
        pnls = [t.pnl_dollars for t in trials]
        summary.append(
            {
                "policy": name,
                "mean_pnl_dollars": round(statistics.mean(pnls), 3),
                "pnl_sd_dollars": round(statistics.stdev(pnls), 3),
                "fifth_percentile_pnl_dollars": round(percentile(pnls, 5), 3),
                "mean_max_abs_inventory": round(statistics.mean(t.max_abs_inventory for t in trials), 3),
                "mean_trades": round(statistics.mean(t.trades for t in trials), 3),
            }
        )
    return outcomes, summary


def write_results(
    output: Path, settings: Settings, outcomes: dict[str, list[TrialResult]], summary: list[dict[str, float | str]]
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "settings.json").write_text(json.dumps(asdict(settings), indent=2) + "\n")
    with (output / "summary.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(8.2, 4.5), dpi=170)
    for name, trials in outcomes.items():
        ax.hist([x.pnl_dollars for x in trials], bins=48, alpha=0.53, density=True, label=name)
    ax.set_title("Synthetic market-making experiment: terminal P&L")
    ax.set_xlabel("Terminal marked-to-mid P&L (USD)")
    ax.set_ylabel("Density")
    ax.legend(frameon=False)
    ax.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    fig.savefig(output / "pnl_distribution.png")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("results"))
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--steps", type=int, default=250)
    parser.add_argument("--seed", type=int, default=20261121)
    args = parser.parse_args()
    settings = Settings(trials=args.trials, steps=args.steps, seed=args.seed)
    outcomes, summary = experiment(settings)
    write_results(args.output, settings, outcomes, summary)
    for row in summary:
        print(row)
    print(f"Saved results in {args.output.resolve()}")


if __name__ == "__main__":
    main()
