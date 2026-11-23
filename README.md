# Market-Making Inventory Simulator

A reproducible, **synthetic** Python experiment comparing fixed bid–ask quotes with inventory-aware quotes. This is a learning project, not a live trading system, historical backtest, or demonstration of a profitable real-world strategy.

**Status:** Working introductory prototype (November 2026).

## New: volatility and inventory-skew sensitivity research (November 2026)

The extended experiment tests 12 volatility/skew settings (2,000 synthetic paths per setting), with paired policy comparisons, downside-risk metrics, and approximate 95% Monte Carlo confidence intervals. It found lower simulated inventory risk with inventory-aware quotes, but a mean-profit advantage is not statistically clear at the higher volatility levels.

- **[Read research notes and interpretation](RESEARCH_NOTES.md)**
- **[Download the scenario-results CSV](results/sensitivity/sensitivity.csv)**
- [View mean-P&L sensitivity chart](results/sensitivity/mean_delta_by_skew.svg) and [downside sensitivity chart](results/sensitivity/tail_pnl_by_skew.svg).\n- Run locally with `python sensitivity.py --output results/sensitivity`.
- This script generates two comparison charts locally when matplotlib is installed.

**Status:** This is a validated reproducible toy simulation, **not** a real-market backtest, and has no claim of live trading performance.

![Mean P&L by skew and volatility](results/sensitivity/mean_delta_by_skew.svg)\n\n![Downside P&L by skew and volatility](results/sensitivity/tail_pnl_by_skew.svg)\n\n## Research question

Does shifting both sides of a dealer's quote in response to inventory change simulated profitability, downside risk and maximum inventory relative to keeping quotes symmetric around the mid-price?

## Method

Each policy trades in **2,000 paired synthetic price/order paths**, with **250 steps per path**. Both policies are evaluated on identical random price shocks and order draws, so comparisons are less affected by differences in simulated market conditions.

- **Fixed quotes:** a bid and ask at a constant spread around the synthetic mid-price.
- **Inventory-aware quotes:** lower both quotes when inventory is positive, and raise them when inventory is negative, to encourage fills that reduce exposure.
- Order fill probability falls with the quote's distance from mid. Inventory is capped at six units.
- Ending P&L combines cash from executed simulated trades and the remaining inventory marked at the final mid-price.

The random price process has zero expected drift and does **not** link price changes to customer order flow. That is a major simplification.

## Reproduce the experiment

Requires Python 3.10+; simulation and tests need no third-party packages:

```bash
python simulate.py --output results
python -m unittest discover -s tests -v
```

Optional chart output:

```bash
python -m pip install -r requirements-plot.txt
python simulate.py --output results
```

The experiment writes `results/summary.csv`, `results/settings.json`, and (when matplotlib is installed) `results/pnl_distribution.png`. A reference PNG is supplied in the original project archive but must be added separately to GitHub; running the script recreates it.

## Seeded example: 2,000 synthetic paths

| Policy | Mean P&L | P&L standard deviation | 5th percentile P&L | Mean max. absolute inventory | Mean trades |
|---|---:|---:|---:|---:|---:|
| Fixed quotes | $6.406 | $2.767 | $1.685 | 5.704 | 64.576 |
| Inventory-aware | $6.665 | $1.533 | $4.230 | 4.066 | 70.067 |

The inventory-aware policy showed slightly higher mean simulated P&L, lower P&L dispersion and lower maximum inventory **under these particular assumptions**. These P&L numbers are in illustrative US dollars per simulated path, not percentage investment returns. They do not establish expected real-world earnings or statistical significance.

## Important limitations

This toy order-arrival rule is not calibrated to exchange data. It excludes adverse selection, queue position, latency, fees, market impact and volatility clustering. Both policies receive the same random draws, but **not necessarily identical executed trades** since their quotes differ. The model also assumes immediate fills when its artificial order rule triggers. Outcomes may change materially under different assumptions.

## Next experiments

1. Vary inventory-skew strength, spreads, volatility, order-arrival rates and inventory limits.
2. Measure the **paired per-path P&L differences** and their uncertainty, not just the two separate distributions.
3. Test an order-flow / price-impact model with adverse selection and transaction costs.
4. Write a short research note explaining conditions under which inventory skew helps, hurts or has no discernible effect.

## Interview summary

"I built an AI-assisted Python prototype to compare fixed and inventory-aware quotes in a simplified market-making simulation. I used identical synthetic price and order random draws across 2,000 paths, then compared terminal marked-to-mid P&L and inventory risk. My initial result favoured inventory-aware quoting under the toy assumptions, but this isn't historical evidence or a live trading claim. My next step is to stress-test the model under more realistic order flow."

## Attribution

Developed with AI assistance. The code, assumptions, results and limitations are exposed for review; prospective users should run and independently validate the experiment before drawing conclusions.
