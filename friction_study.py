"""Synthetic market-making study with fees and adverse order-flow signals.

Run: python friction_study.py --output results/frictions

A toy experiment: NOT a backtest, calibrated microstructure model, or claim
of live profitability. The price tape is exogenous and shared by both policies.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import statistics
from dataclasses import dataclass
from pathlib import Path

from simulate import Settings, percentile, simulate_path


@dataclass(frozen=True)
class FrictionSettings:
    trials: int = 2000
    steps: int = 250
    seed: int = 20261121
    price_shock_sd_cents: float = 15.0
    spread_cents: float = 20.0
    inventory_limit: int = 6
    inventory_skew_cents: float = 1.0
    toxic_signal_probability: float = 0.08
    adverse_move_cents: float = 0.0
    fee_cents_per_trade: float = 0.0

    def validate(self) -> None:
        if self.trials < 2 or self.steps < 1:
            raise ValueError('Use at least two trials and one step')
        if not (0 <= self.toxic_signal_probability <= 1):
            raise ValueError('toxic_signal_probability must be in [0, 1]')
        for label in ('price_shock_sd_cents', 'spread_cents', 'inventory_skew_cents',
                      'adverse_move_cents', 'fee_cents_per_trade'):
            value = getattr(self, label)
            if not math.isfinite(value) or value < 0:
                raise ValueError(f'{label} must be finite and nonnegative')
        if self.inventory_limit < 1 or self.spread_cents <= 0:
            raise ValueError('Positive spread and inventory limit required')
        if self.inventory_skew_cents * self.inventory_limit >= self.spread_cents / 2:
            raise ValueError('Skew × inventory limit must be below half the spread')


def experiment(settings: FrictionSettings) -> dict[str, object]:
    """Evaluate both policies on the same exogenous order opportunities.

    Each time step has two synthetic order-opportunity uniforms: lower bid
    draw = a more aggressive customer SELL (bad future price for dealer long),
    lower ask draw = aggressive customer BUY (bad future price for dealer short).
    If a draw falls below the toxic threshold, a fixed signed mid-price
    adjustment occurs after the quotes execute even if this dealer does not fill.
    This is intentionally a COMMON price tape, not price impact caused by us.
    """
    settings.validate()
    rng = random.Random(settings.seed)
    base = Settings(
        trials=settings.trials, steps=settings.steps, seed=settings.seed,
        price_shock_sd_cents=settings.price_shock_sd_cents,
        spread_cents=settings.spread_cents, inventory_limit=settings.inventory_limit,
        inventory_skew_cents=settings.inventory_skew_cents,
    )
    fixed_net: list[float] = []
    skew_net: list[float] = []
    fixed_trades: list[int] = []
    skew_trades: list[int] = []
    fixed_inventory: list[int] = []
    skew_inventory: list[int] = []
    for _ in range(settings.trials):
        events = []
        for _ in range(settings.steps):
            shock = rng.gauss(0, settings.price_shock_sd_cents)
            bid_draw, ask_draw = rng.random(), rng.random()
            toxic_bid = int(bid_draw < settings.toxic_signal_probability)
            toxic_ask = int(ask_draw < settings.toxic_signal_probability)
            # Customer sell => future price down; buy => future price up.
            # This price adjustment is exogenous and identical for both policies.
            shock += settings.adverse_move_cents * (toxic_ask - toxic_bid)
            events.append((shock, bid_draw, ask_draw))
        fixed = simulate_path(events, base, 0.0)
        adjusted = simulate_path(events, base, settings.inventory_skew_cents)
        fixed_net.append(fixed.pnl_dollars - fixed.trades * settings.fee_cents_per_trade / 100.0)
        skew_net.append(adjusted.pnl_dollars - adjusted.trades * settings.fee_cents_per_trade / 100.0)
        fixed_trades.append(fixed.trades)
        skew_trades.append(adjusted.trades)
        fixed_inventory.append(fixed.max_abs_inventory)
        skew_inventory.append(adjusted.max_abs_inventory)

    paired = [a - b for a, b in zip(skew_net, fixed_net)]
    mean_delta = statistics.mean(paired)
    se = statistics.stdev(paired) / math.sqrt(settings.trials)

    return {
        'fee_cents': settings.fee_cents_per_trade,
        'adverse_move_cents': settings.adverse_move_cents,
        'toxic_probability': settings.toxic_signal_probability,
        'volatility_cents': settings.price_shock_sd_cents,
        'trials': settings.trials,
        'fixed_mean_net_pnl': round(statistics.mean(fixed_net), 4),
        'aware_mean_net_pnl': round(statistics.mean(skew_net), 4),
        'paired_mean_delta': round(mean_delta, 4),
        'paired_ci95_low': round(mean_delta - 1.96 * se, 4),
        'paired_ci95_high': round(mean_delta + 1.96 * se, 4),
        'fixed_pnl_sd': round(statistics.stdev(fixed_net), 4),
        'aware_pnl_sd': round(statistics.stdev(skew_net), 4),
        'fixed_pnl_p05': round(percentile(fixed_net, 5), 4),
        'aware_pnl_p05': round(percentile(skew_net, 5), 4),
        'fixed_loss_rate': round(sum(x < 0 for x in fixed_net)/settings.trials, 4),
        'aware_loss_rate': round(sum(x < 0 for x in skew_net)/settings.trials, 4),
        'fixed_mean_trades': round(statistics.mean(fixed_trades), 4),
        'aware_mean_trades': round(statistics.mean(skew_trades), 4),
        'fixed_max_inventory_mean': round(statistics.mean(fixed_inventory), 4),
        'aware_max_inventory_mean': round(statistics.mean(skew_inventory), 4),
    }


def grid(base: FrictionSettings, fees: list[float], adverse_moves: list[float]) -> list[dict[str, object]]:
    from dataclasses import replace
    if not fees or not adverse_moves:
        raise ValueError('At least one fee and adverse-move setting required')
    return [experiment(replace(base, fee_cents_per_trade=fee, adverse_move_cents=adverse))
            for adverse in adverse_moves for fee in fees]


def write_results(rows: list[dict[str, object]], output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    with (output / 'friction_grid.csv').open('w', newline='', encoding='utf-8') as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    adverse_moves = sorted(set(r['adverse_move_cents'] for r in rows))
    for move in adverse_moves:
        subset = sorted((r for r in rows if r['adverse_move_cents'] == move), key=lambda r: r['fee_cents'])
        ax.plot([r['fee_cents'] for r in subset], [r['fixed_mean_net_pnl'] for r in subset], marker='o', linestyle='--', label=f'Fixed, adverse {move:g}¢')
        ax.plot([r['fee_cents'] for r in subset], [r['aware_mean_net_pnl'] for r in subset], marker='s', label=f'Inventory-aware, adverse {move:g}¢')
    ax.axhline(0, linewidth=1, color='gray')
    ax.set(xlabel='Fee per executed share (¢)', ylabel='Mean net P&L per path ($)', title='Synthetic net profitability under costs and adverse selection')
    ax.legend(fontsize=8, ncol=2)
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(output / 'mean_net_pnl.png', dpi=180)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('results/frictions'))
    parser.add_argument('--trials', type=int, default=2000)
    parser.add_argument('--steps', type=int, default=250)
    parser.add_argument('--seed', type=int, default=20261121)
    parser.add_argument('--volatility-cents', type=float, default=15.0)
    parser.add_argument('--toxic-probability', type=float, default=0.08)
    parser.add_argument('--fees', type=lambda s: [float(x.strip()) for x in s.split(',')], default=[0.0, 4.0, 8.0])
    parser.add_argument('--adverse-moves', type=lambda s: [float(x.strip()) for x in s.split(',')], default=[0.0, 5.0, 10.0, 20.0])
    args = parser.parse_args()
    base = FrictionSettings(trials=args.trials, steps=args.steps, seed=args.seed,
                            price_shock_sd_cents=args.volatility_cents,
                            toxic_signal_probability=args.toxic_probability)
    rows = grid(base, args.fees, args.adverse_moves)
    write_results(rows, args.output)
    print('fee(¢) adverse(¢) fixed_net($) aware_net($) paired_delta($) [95% MC interval]')
    for r in rows:
        print(f"{r['fee_cents']:>6g} {r['adverse_move_cents']:>10g} "
              f"{r['fixed_mean_net_pnl']:>12.3f} {r['aware_mean_net_pnl']:>12.3f} "
              f"{r['paired_mean_delta']:>+12.3f} [{r['paired_ci95_low']:+.3f}, {r['paired_ci95_high']:+.3f}]")
    print(f'Results: {args.output.resolve()}')


if __name__ == '__main__':
    main()
