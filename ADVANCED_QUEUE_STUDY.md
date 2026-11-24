# Advanced AAPL Market-Making Research Protocol

## Scope and evidence status

This document governs the new historical depth-aware queue experiment and future multiple-day AAPL evaluation.

**Current data availability:** LOBSTER provides a **free, public, single historical session** for AAPL on 2012-06-21, at 1, 5 and 10 displayed depth levels. The improved execution model **has been executed successfully** on the Level-5 historical sample, using 301,587 recorded AAPL events; all 31 automated tests passed. [Verified results](QUEUE_RESULTS.md). **This LOBSTER-specific pipeline still awaits additional licensed LOBSTER dates. However, a separate raw-Nasdaq-ITCH decoder has already successfully analysed seven different free Nasdaq AAPL days. See the independent [2019–2020 seven-day results](NASDAQ_MULTI_DAY_RESULTS.md).**

The earlier Experiment 4 used an optimistic price-touch fill rule. Our new implementation is more conservative: a hypothetical order must join a displayed queue and wait for historical executed volume to deplete **an estimated quantity ahead** before the fill is counted.

## Source

- [LOBSTER official AAPL level-5 sample](https://php.lobsterdata.com/info/DataSamples.php) — June 21, 2012, Nasdaq 09:30–16:00
- [LOBSTER message and order-book schema](https://php.lobsterdata.com/info/DataStructure.php)
- Study code: [queue_replay.py](queue_replay.py)
- Multi-day pipeline: [multi_day_research.py](multi_day_research.py)

**Raw market data is not committed to GitHub.** Derived summaries can be published only after verification and in accordance with applicable source terms.

## Execution mechanics

### Timeline and causality

Each LOBSTER message records an order event, with the corresponding **post-event** book state. The engine:

1. Processes event i against outstanding **previously submitted** quotes.
2. Updates queue estimates using actual event type, resting side, price and executed/cancelled size.
3. Marks inventory at the newly observed post-event market midpoint.
4. When a refresh is due, sets replacement quotes from the **newly observed** book.
5. Makes the new quotes eligible for fills only at subsequent events after the chosen latency.

This prevents trading at an event using the book snapshot that the event itself produced.

### Posted prices

- **Fixed baseline:** joins the visible best bid and best ask.
- **Inventory-aware:** if long, lowers its bid by 1 or 2 ticks per inventory unit, thereby reducing the chance of acquiring more stock; if short, raises the ask analogously.
- The experiment posts **one hypothetical share on each side** and caps inventory at ±6 shares.
- Both strategies begin flat with zero cash, experience the same historical order-event tape, and are marked to the same final midpoint.

### Queue-ahead model

When an order is posted, we assume all displayed depth currently at that price is **ahead of our hypothetical order**. This is a deliberately conservative approximation, not knowledge of historical queue position.

- Visible executions (message type **4**) at the same price **and resting side** consume estimated volume ahead.
- If remaining executed size reaches **beyond** that queue estimate, the hypothetical one-share order fills at its posted price.
- Cancellation/deletion messages (types **2/3**) may reduce queue ahead by a predeclared fraction of their reported size. We report **0%, 50% and 100%** ahead-allocation scenarios. We do not know which cancelled historical orders actually preceded our hypothetical order.
- New historical submissions (type **1**) are treated as **behind** our existing queue position, not ahead.
- Hidden executions and auctions are not counted as guaranteed fills against the displayed hypothetical order.
- If the quote's price leaves the visible 5-level book, we cancel it rather than imagine depth beyond the observed levels.

This queue estimate does **not** reproduce exchange-level order IDs/priority, and therefore does not prove an order would really have filled. Deeper market-by-order data would improve it.

### Timing and costs

The single-day sample run fixes:
- 5 displayed book levels
- 10 milliseconds of assumed order-entry latency
- 2 seconds between quote refreshes
- 0.3 US cents per hypothetical fill (illustrative fee, not a 2012 Nasdaq historical fee schedule)
- Queue-cancellation-ahead fractions **0, 0.5, 1**
- Fixed and 1-tick-per-share inventory-aware policies

The multi-day framework additionally tests 50 milliseconds of latency and a second inventory adjustment size (2 ticks/share).

At each event, equity is cash plus marked-to-mid inventory minus fees. A separate optional terminal-liquidation estimate uses displayed best bid/ask quotes where sufficient size is visible, plus an additional illustrative 1-cent/share exit fee. The report includes total hypothetical fills, net/gross P&L, total fee drag, ending and maximum inventory, time-weighted absolute inventory, peak-to-trough marked drawdown, quote refresh counts and cancelled quotes.

**This is a one-venue passive research simulation, not an execution-calibrated production trading system.** It omits queue order identities, hidden/iceberg liquidity, partial-fill priority within multiorder executions, order-cancel acknowledgement timing, dynamic spread selection, cross-venue routing, fees/rebates specific to venues and dates, and the feedback of an inserted order on future historical events.

## Reproduce the level-5 AAPL queue experiment

Windows Command Prompt inside the repository folder:

```cmd
python -m unittest discover -s tests -v
python queue_replay.py --download --output results\queue_replay
```

The script saves:
- `results/queue_replay/queue_sensitivity.csv`
- `results/queue_replay/run_info.json`

An [automated GitHub Actions workflow](.github/workflows/queue-aware-aapl.yml) reproduces the sample run and uploads only derived CSV/JSON outputs.

## Multi-day AAPL study design

The file [multi_day_research.py](multi_day_research.py) accepts a folder of **separate licensed AAPL LOBSTER ZIP archives**, all with the same depth level and message/book schema. Each archive must contain one correctly named and aligned AAPL message/book pair.

**Strict provenance safeguards:**

- Reads the actual date inside each archive, not just the ZIP filename.
- Rejects duplicate trading dates, malformed ZIPs and mixed tickers.
- Requires **at least 12 distinct dates** by default.
- Orders days chronologically; makes a 60% development / 20% validation / 20% holdout test split.
- Chooses between 1-tick and 2-tick inventory skew on the **validation period only** using average daily net P&L at the predeclared reference setting (10 ms latency and 0% cancellation-ahead allocation).
- Locks that choice before inspecting test days.
- Reports the test-days' paired difference against fixed quotes under **all six predeclared execution sensitivities**: 10/50 ms × 0/50/100% cancellation-ahead allocation.
- Uses a **day-level** percentile bootstrap of paired daily P&L differences, not a fictitious standard error based on millions of correlated order events.
- Saves `daily_policy_results.csv`, `holdout_robustness.csv`, and `walk_forward_summary.json`.

To run with **at least 12 separately dated source files** under `data/aapl_days`:

```cmd
python multi_day_research.py --data-dir data\aapl_days --output results\multi_day
```

A dozen trading days provides only a very small holdout sample; for materially more persuasive conclusions, aim for **30–60 independent trading days**, and ideally separate market regimes. All data should originate from the same calibrated historical venue/source, and all assumptions should be fixed before examining test results.

**Important:** Re-running one AAPL day with different random seeds or different depth files does not create independent days. Nor does buying daily OHLCV candles provide enough trade/order-book information for this queue model.

## Data procurement plan (no purchases made)

**Best drop-in fit:** Request additional historical AAPL **LOBSTER Level-5/Level-10 message and order-book files** for 30–60 distinct trading days. Confirm student/academic eligibility, redistribution limits and the price *before* ordering. Single-provider consistency avoids having to implement and independently validate a second data adapter.

**Possible lower-cost alternative:** Databento's historical Nasdaq `XNAS.ITCH` market-by-order (**MBO**) data. Databento's published pricing page currently advertises **USD $125 of introductory historical data credits**, but exact AAPL date-range cost, exchange licence requirements and availability must be checked in their quoting interface. **Databento MBO files are not directly compatible with this LOBSTER ZIP loader** and require a documented order-book reconstruction adapter, instrument metadata and session handling before being used for valid comparisons.

**No actual securities trades are required** to measure historical order book effects or test a research simulator. Paper trading may be a later demonstration but is not a replacement for many days of validated historical microstructure data.

## How to interpret results

If queue-based fills vanish or differ sharply between the 0/50/100% cancellation assumptions, **that is an important robustness failure**, not an instruction to choose the most profitable scenario. Do not select the fill model with the highest P&L after seeing results.

Do not call any positive hypothetical P&L a proven market-making edge. Do not annualise a single-day hypothetical dollar profit; the toy strategy uses a one-share order quantity and no capital financing, so percentage returns and Sharpe ratios are not economically meaningful without further calibration.

## Research claims

Fair: "Developed an AI-assisted event-driven historical order-book replay with depth-constrained queue estimates, latency and cancellation sensitivity, reproducible tests, and a chronology-protected multi-day evaluation pipeline."

Not fair: "Built an institution-grade profitable quant trading system" or "Demonstrated statistically significant real-market alpha" without validation.
