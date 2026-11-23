# Experiment 4: historical AAPL order-book replay

**Status (23 November 2026): the code and synthetic fixtures have been tested; the full real AAPL sample has NOT yet been executed and independently verified in the development environment. There is intentionally no claimed historical P&L result in this repository.** Running the sample produces genuine historical *observations* and separately labelled hypothetical execution scenarios.

## Research question

Would the earlier fixed-quote and inventory-aware market-making policies behave differently when exposed to **recorded Nasdaq AAPL order events and displayed best quotes** rather than generated price moves?

This is a first real-data replay, not a validated executable market-making backtest.

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

The real AAPL replay was not run in the environment authoring this update because the provider archive couldn't be retrieved there. To publish quantitative claims, first run the script on the complete local vendor ZIP, check event counts and any anomalous prices, review the generated outputs, and upload the summary-only files or send them for analysis.

Afterward, investigate actual markouts by buy/sell direction and spread; add queue-size models; compare market conditions across multiple independent days; and test with chronologically held-out market data.

Developed with AI assistance. Code is for education and research, not live trading.
