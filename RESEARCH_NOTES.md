# Synthetic Market-Making Research Notes

## Objective

Compare fixed bid–ask quotes with inventory-aware quotes across price volatility levels and quote-skew parameters. This is a **synthetic model**, not a historical backtest or a deployed strategy. No real money was traded.

## Experimental design

- 3 synthetic per-step mid-price shock standard deviations: **5¢, 15¢, 30¢**.
- 4 inventory skew strengths: **0¢, 0.5¢, 1.0¢, 1.5¢ per unit of inventory**.
- 2,000 simulated paths of 250 steps per combination, all under seed **20261121**.
- In every comparison both policies receive the **same generated shocks and order draws**. Fills can differ because quotes differ.
- 12 scenario settings, comprising **24,000 underlying synthetic price/order paths** evaluated under two policies (48,000 policy evaluations).
- Inventories are capped at six units and the sensitivity runner rejects skews that would cross the synthetic mid price at the allowed inventory limit.

## Mean paired P&L difference (inventory-aware minus fixed; illustrative USD per path)

| Skew (¢/share) | Volatility 5¢ | Volatility 15¢ | Volatility 30¢ |
|---:|---:|---:|---:|
| 0.0 | 0.000 | 0.000 | 0.000 |
| 0.5 | +0.247 | +0.201 | +0.131 |
| 1.0 | +0.259 | +0.256 | +0.252 |
| 1.5 | +0.227 | +0.268 | +0.330 |

At 1.0¢ skew:

| Metric | Volatility 5¢ | Volatility 15¢ | Volatility 30¢ |
|---|---:|---:|---:|
| Paired mean P&L difference | +$0.259 | +$0.256 | +$0.252 |
| Approximate 95% Monte Carlo CI on difference | [+0.167, +0.351] | [-0.012, +0.524] | [-0.281, +0.785] |
| Fixed P&L standard deviation | $2.767 | $7.973 | $15.882 |
| Inventory-aware P&L standard deviation | $1.533 | $4.109 | $8.131 |
| Fixed 5th percentile P&L | $1.685 | -$6.800 | -$20.297 |
| Inventory-aware 5th percentile P&L | $4.230 | -$0.161 | -$6.762 |
| Fixed proportion of losing paths | 1.75% | 19.25% | 33.10% |
| Inventory-aware proportion of losing paths | 0.00% | 5.45% | 20.80% |

These are approximate normal confidence intervals based on the **paired difference over 2,000 Monte Carlo runs**. They quantify sampling variation under the simulated data-generating process, not uncertainty about the actual market or parameter selection. Reusing the same seed for parameter sweeps yields dependent scenario estimates.

## Visualizations\n\n![Mean P&L sensitivity](results/sensitivity/mean_delta_by_skew.svg)\n\n![Downside sensitivity](results/sensitivity/tail_pnl_by_skew.svg)\n\n## Interpretation

The inventory-aware policy lowered P&L dispersion, downside exposure, and inventory extremes in these settings. Its estimated mean P&L was slightly higher, but at 15¢ and 30¢ volatility the confidence intervals for the mean *difference* overlap zero. It would be misleading to say that the profit improvement is demonstrated in those settings. At higher volatility, simulated mark-to-market inventory risk becomes much more substantial.

**Do not conclude:** that the strategy is profitable out of sample, that the model beats the overall market, or that the best-performing skew in this grid is optimal in real trading.

## Important modelling shortcomings

- Synthetic order arrivals are independent of subsequent price changes, so **adverse selection is missing**.
- No bid/ask queue dynamics, exchange latency, slippage, transaction fees, hedging or market impact.
- A constant quote spread is assumed; in reality spreads can respond to volatility and liquidity.
- Price shocks are independent Gaussian draws with zero drift, without volatility clustering or jumps.
- The same model is used both to design and evaluate the strategy; this is not out-of-sample validation.
- Even though the skew shifts quotes, the simplistic fill rule is not calibrated to real trading.
- The P&L scale depends on arbitrary simulated order units, spread and horizon.

## Reproduction

```cmd
python -m pip install -r requirements-plot.txt
python -m unittest discover -s tests -v
python sensitivity.py --output results/sensitivity
```

The CSV contains every observation-level summary: [sensitivity.csv](results/sensitivity/sensitivity.csv).

With matplotlib installed, the sensitivity script also saves `mean_delta_by_skew.png` and `tail_pnl_by_skew.png` into `results/sensitivity/`.

## Future work

Evaluate transaction costs and adverse selection first. Then test different quote spreads, inventory limits, order intensity and time horizons. Consider an out-of-sample market-data experiment only after the simulation model is independently validated.
