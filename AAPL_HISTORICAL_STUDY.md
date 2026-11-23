# Experiment 4: historical AAPL order-book replay

**Status (23 November 2026): Successfully executed on the complete LOBSTER AAPL Level-1 historical sample in GitHub Actions. 118,497 recorded events were loaded; all 20 Python unit tests passed. Verified derived outputs are checked into this repository. These figures are still hypothetical strategy replays, NOT validated historical executions or a real trading track record.** Running the sample produces genuine historical *observations* and separately labelled hypothetical execution scenarios.

## Research question

Would the earlier fixed-quote and inventory-aware market-making policies behave differently when exposed to **recorded Nasdaq AAPL order events and displayed best quotes** rather than generated price moves?

This is a first real-data replay, not a validated executable market-making backtest.

## Verified run and numerical results (23 November 2026)

[GitHub Actions successful source run](https://github.com/rileysanders/market-making-inventory-simulator/actions/runs/45173977177) and [downloadable summary artifact](https://github.com/rileysanders/market-making-inventory-simulator/actions/runs/45173977177/artifacts).

**Recorded data processed:** 118,497 LOBSTER AAPL Level-1 events; first timestamp 34200.004241176 and last 57599.913117637 seconds after midnight (09:30 to 16:00 Eastern time). The raw vendor data was downloaded by the GitHub runner directly from the official provider URL, then read as paired message and post-event order-book records.

### Historical executed-trade markouts — observations, not hypothetical orders

| Horizon | Eligible actual visible executions | Executed shares | Passive execution-price markout per share | Signed post-trade midpoint move per share |
|---|---:|---:|---:|---:|
| 1 second | 23,646 | 1,845,152 | +$0.003027 | −$0.046534 |
| 5 seconds | 23,628 | 1,842,613 | −$0.005443 | −$0.055034 |

The observed execution-price markout measures the passive trader's price against a later midpoint. At 1 second, the volume-weighted observation is a +0.3027-cent advantage per executed share; at 5 seconds it is a −0.5443-cent disadvantage. The separate midpoint-move metric measures the direction of subsequent midpoint changes relative to the preceding midpoint (not an order fill or a P&L forecast).

### Historical quote replay — hypothetical fills only

| Policy | Assumed fill rule | Hypothetical shares traded | Peak absolute inventory | Gross P&L | Net P&L after illustrative fees |
|---|---|---:|---:|---:|---:|
| Fixed | Touch | 12,833 | 6 | −$36.105 | **−$74.604** |
| Inventory-aware | Touch | 5,504 | 1 | −$25.480 | **−$41.992** |
| Fixed | Trade-through | 0 | 0 | $0 | $0 |
| Inventory-aware | Trade-through | 0 | 0 | $0 | $0 |

Net P&L subtracts a **0.3 US-cent fee per hypothetical trade**. Under optimistic **touch fills**, inventory awareness lost **$32.612 less** than fixed quotes, but both net results were negative. The inventory-aware policy quoted more conservatively, executed fewer trades, and reached only a 1-share peak inventory. The strategies do **not** use identical quote adjustment rules to the earlier synthetic experiments.

**Crucial methodological finding:** The stricter **trade-through assumption produces no qualifying executions** in this dataset using these particular rules. Its $0 P&L is a no-trade outcome, **not** evidence of a profitable zero-risk strategy. Zero executions reveal this replay's lack of useful sensitivity coverage at strict fill assumptions and the need for a calibrated execution/queue model. Touch fills are optimistic and cannot establish realizable execution counts.

Verified derived files:
- [run_info.json](results/aapl/run_info.json)
- [observed_markouts.csv](results/aapl/observed_markouts.csv)
- [policy_replay.csv](results/aapl/policy_replay.csv)

**No annualised return, Sharpe ratio or statistical significance is claimed** from this single historical session and uncalibrated hypothetical fill model.

## Historical data

- **Issuer and symbol:** Apple Inc. (AAPL).
- **Date:** 21 June 2012, regular Nasdaq session, approximately 09:30–16:00 US Eastern.
- **Source:** LOBSTER's Level-1 sample, reconstructed from Nasdaq historical TotalView-ITCH events.
- **Files:** `AAPL_2012-06-21_34200000_57600000_message_1.csv` and `AAPL_2012-06-21_34200000_57600000_orderbook_1.csv` inside `LOBSTER_SampleFile_AAPL_2012-06-21_1.zip`.
- **Recorded fields:** timestamp, event type, order identifier, order size, event price and direction; best ask, ask depth, best bid and bid depth.
- **Price convention:** original unadjusted historical USD values represented in units of 1/10,000 USD; **do not treat these as today's split-adjusted Apple share prices**.

Data information and direct sample access:
- [LOBSTER's official sample downloads](https://php.lobsterdata.com/info/DataSamples.php).
- [Mirrored original AAPL sample CSV files](https://huggingface.co/datasets/totalorganfailure/lobster-data/tree/main/LOBSTER_SampleFile_AAPL_2012-06-21_1).

The raw vendor data remains on your computer in `data/`, **not redistributed in this repository**. Users should follow the provider's licensing terms.

## How to run on Windows, without VS Code

1. Download a fresh ZIP of this GitHub project and extract it. **Easiest option:** double-click `run_aapl_windows.bat` in the extracted folder; it runs the same command and opens the graph if available.
2. In File Explorer, open the folder containing `aapl_replay.py`. Press **Ctrl+L**, type **cmd**, press Enter.
3. Run:

```cmd
python -m pip install -r requirements-plot.txt
python -m unittest discover -s tests -v
python aapl_replay.py --download --output results\aapl
```

The `--download` flag first tries official LOBSTER sample URLs and then a third-party mirror. These endpoints may change or require manual access. If downloads fail, get the **AAPL Level 1** ZIP from the [official sample page](https://php.lobsterdata.com/info/DataSamples.php), place the file in `data/`, and run:

```cmd
python aapl_replay.py --output results\aapl
```

Do **not extract the sample ZIP**; the script reads it directly.

After a successful run:

```cmd
start results\aapl\hypothetical_pnl.png
```

The new folder contains:
- `run_info.json`: source identification and loaded event count.
- `observed_markouts.csv`: **retrospective market observations**: visible historical executions and their 1-second / 5-second subsequent price markouts.
- `policy_replay.csv`: **hypothetical** net and gross P&L, trades, end inventory and peak inventory for fixed vs inventory-aware policies.
- `hypothetical_pnl.png`: chart of hypothetical replay P&L (with matplotlib).

## What counts as an observation vs an assumption?

### A. Actual observed passive-execution markouts

For a recorded **visible** execution, we find the first observed midpoint at or after 1 or 5 seconds following that trade.

- Resting **buy** (`direction=1`): markout = future midpoint minus actual execution price.
- Resting **sell** (`direction=-1`): markout = actual execution price minus future midpoint.
- Aggregate as volume-weighted USD per executed share.

These results describe **the actual trades recorded in this one historical sample**, not trades executed by our simulated strategy. The calculation can show adverse price moves experienced by passive traders in that period; it cannot identify their motives or whether trades were informed.

### B. Hypothetical quote replay

Quotes at event `i` are decided exclusively from the **book after event `i-1`** to avoid using future information. Each candidate fill corresponds to an actual recorded *visible execution event* (`type=4`), with the execution direction defined by the **resting order** in LOBSTER's convention.

- **Fixed quotes:** post the historical best bid and best ask from the preceding event.
- **Inventory-aware quotes:** when long, lower the bid by one tick per unit of inventory; when short, raise the ask similarly. The other quote remains at the preceding best. This is a deliberately simple *passive retreat* rule, **not mathematically identical to the two-sided skew used in Experiments 1–3**.
- **Touch scenario (optimistic):** a printed trade at our quote price or beyond generates a one-share hypothetical fill, ignoring other resting orders ahead of us in the queue.
- **Through scenario (stricter):** only a visible trade at least one cent past our hypothetical order price generates a one-share fill.
- **Fee:** 0.3 US cents per hypothetical fill by default, chosen illustratively, **not a historical venue-specific fee schedule**.
- **Inventory cap:** 6 shares on either side. Remaining inventory is marked at the final recorded midpoint.
- **Quote updates:** assumed instant after each event. No order latency, queue priority, market impact or hedging.

Both fill scenarios are **counterfactual and model-dependent**. Even the stricter trade-through rule is not proof that an inserted historical order would have executed; adding orders could change subsequent activity. The optimistic and stricter scenarios are sensitivity checks, not statistically justified upper/lower bounds on real P&L.

## Methodological strengths

- Uses real contemporaneous bid/ask snapshots **and** execution events rather than daily OHLC prices.
- Correctly treats the LOBSTER order-book row as **post-event** and uses the preceding row to make a quote decision.
- Distinguishes historical observed markouts from hypothetical strategy fills.
- Uses integer fixed-point prices, retaining cent precision and avoiding split-adjustment mistakes.
- Tests timestamp alignment, direction, the fill assumptions, fees, ZIP input and CSV output.
- Refuses malformed or mismatched CSV pairs and unsupported trading-halt indicators rather than silently mislabelling them.

## Main limitations

One **historical trading day** is not enough to establish expected returns or an out-of-sample advantage. A single deterministic replay does not support Monte Carlo confidence intervals or annualised returns. Historical order-book data cannot directly reveal the true queue position of a hypothetical order, and we assume instantaneous quote updates. Level-1 snapshots omit deeper liquidity and hidden executions. Recorded market events don't model how an additional order would affect the rest of the book.

**Please don't write 'profitable AAPL backtest' on a résumé** from these results. It is more accurate to say you implemented an event-driven historical order-book replay with explicit execution assumptions and observed markout measurements.

## Reproducibility and next steps

The complete historical sample was successfully downloaded and processed in GitHub Actions (run 45173977177); the console outputs and uploaded summary artifact were independently inspected and matched the derived CSV and JSON files committed above. The execution conclusions remain speculative because this is a counterfactual replay with unvalidated fills.

Afterward, investigate actual markouts by buy/sell direction and spread; add queue-size models; compare market conditions across multiple independent days; and test with chronologically held-out market data.

Developed with AI assistance. Code is for education and research, not live trading.
