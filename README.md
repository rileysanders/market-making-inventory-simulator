# Market-Making Inventory Simulator

**Python | Monte Carlo simulation | Market microstructure | Risk analysis**

A reproducible, **AI-assisted educational project** investigating whether inventory-aware bid–ask quotes change a market maker's profit distribution and inventory risk. The study compares fixed quotes against quotes adjusted for the dealer's current inventory.

> **This is a synthetic, deliberately simplified model.** It is not historical backtesting, live trading, or proof that a real-world strategy is profitable.

## Research at a glance

| Experiment | Research question | Results |
|---|---|---|
| **1. Original quoting simulator** | Does inventory-sensitive quoting change P&L and exposure under simple order arrivals? | [Initial results](results/summary.csv) |
| **2. Volatility × skew sweep** | Does the effect depend on market volatility and how aggressively quotes adjust? | [Research notes](RESEARCH_NOTES.md) · [CSV](results/sensitivity/sensitivity.csv) |
| **3. Fees + adverse selection** | Does the original advantage survive trading costs and adverse price moves following aggressive customer flow? | **[Research note](FRICTION_STUDY.md)** · [CSV](results/frictions/friction_grid.csv) |

### Latest finding: the apparent profit advantage is fragile

Adding per-trade fees and a simple adverse-selection mechanism reduced simulated net earnings and sometimes reversed the performance ranking. Higher inventory-adjustment intensity can reduce inventory risk **without** increasing net expected profit.

![Average net P&L under adverse selection](results/frictions/net_pnl_vs_adverse.svg)

For example, with 4¢ per-share execution fees and a 20¢ adverse move associated with selected synthetic order opportunities, both strategies had negative **mean simulated P&L**:

| Policy | Average net P&L per path | 5th-percentile net P&L |
|---|---:|---:|
| Fixed quotes | -$2.755 | -$18.652 |
| Inventory-aware | -$3.098 | -$11.279 |

This is **not a prediction** of real trading results. Every fee, adverse move and order-arrival rate is hypothetical. The inventory-aware policy has worse mean net profit here but less severe downside in the model.

### Earlier volatility sensitivity

![Mean P&L advantage under skew and volatility](results/sensitivity/mean_delta_by_skew.svg)

![Downside P&L under skew and volatility](results/sensitivity/tail_pnl_by_skew.svg)

## Model overview

1. Draw synthetic mid-price shocks and customer order opportunities.
2. Quote a bid and ask around the mid-price.
3. Compare **fixed quotes** with **inventory-aware quotes** that move lower when the dealer owns more shares and higher when short.
4. Record simulated fills, cash and the outstanding inventory, marked at the final mid-price.
5. Compare P&L distributions, extreme inventory, downside outcomes and **paired** policy differences.

Both policies see the same generated market/order opportunities *within each scenario*. Which orders actually fill may differ because the quotes differ.

In Experiment 3, a small subset of synthetic buy/sell opportunities is **associated by construction** with a later price movement in the direction unfavourable to a market maker. This represents a toy **adverse-selection proxy**, not empirical calibration or price impact caused by the dealer.

## Run on Windows (Notepad + Command Prompt works)

Install Python **3.10 or later** and open Command Prompt in the folder containing `simulate.py`.

```cmd
python -m pip install -r requirements-plot.txt
python -m unittest discover -s tests -v
```

Run the original version:

```cmd
python simulate.py --output results\original
```

Run the volatility/skew sensitivity experiment:

```cmd
python sensitivity.py --output results\sensitivity
```

Run the **new fees + adverse-selection experiment**:

```cmd
python friction_study.py --output results\frictions
```

Example with custom assumptions:

```cmd
python friction_study.py --fees 0,2,6 --adverse-moves 0,5,15 --trials 3000 --output results\my_experiment
```

The study writes a CSV of summary results and (if matplotlib is installed) a PNG plot. All simulation and unit-test logic otherwise uses the Python standard library.

## Methodological cautions

- Customer arrivals are synthetic, not calibrated to limit-order-book data.
- Orders, adverse price signals and fills are simplified. No queue position, latency, actual hedging, market impact, spread dynamics or volatility clustering.
- **Transaction fees are fixed per fill**, with no jurisdiction-, venue- or product-specific calibration.
- Confidence intervals describe **Monte Carlo sampling error within the toy model**, not uncertainty about real markets or whether the model is economically correct.
- Different parameter combinations reuse a common random seed; they are not independent trials.
- An attractive simulated result does not establish a profitable executable strategy.

See the full [fees and adverse-selection study](FRICTION_STUDY.md) for exact assumptions, test design and limitations.

## What I would improve next

1. Vary the toxic-order threshold instead of treating it as known.
2. Calibrate realistic customer order-flow and fees, where possible, using a documented data source.
3. Model queue dynamics, adverse selection and spread changes more realistically.
4. Run parameter robustness and out-of-sample validation before drawing economic conclusions.

## Attribution

Developed with **AI assistance**. The simulator, tests, model assumptions and saved outputs are provided transparently so others can reproduce and scrutinise the results. No real transactions were made.
