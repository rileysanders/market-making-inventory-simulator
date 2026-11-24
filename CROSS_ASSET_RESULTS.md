# Cross-sectional historical market-making robustness: five stocks, one day

**Verified 24 November 2026:** [Successful GitHub Actions run](https://github.com/rileysanders/market-making-inventory-simulator/actions/runs/45325240016) processed five **distinct Nasdaq stocks** from the official **LOBSTER Level-5 sample on 21 June 2012**. The full derived 30-scenario CSV and provenance manifest were uploaded as an Actions artifact; [a 10-row conservative-case CSV](results/cross_stocks/summary_conservative.csv) is stored permanently in the repository.

**Important:** these are **five stocks observed on exactly ONE historical day**, not five independent historical dates. All our candidate trading fills and P&L figures remain **hypothetical**.

## Research setup

The same depth-aware event replay was run without refitting parameters on AAPL, AMZN, GOOG, INTC, and MSFT. Every policy uses a 10 ms assumed order-entry latency, 2-second refresh interval, 0.3 US cents per passive fill, one-share hypothetical order size, and ±6-share inventory limit.

The comparison is fixed quoting versus a one-tick-per-inventory-unit retreat of the inventory-increasing quote. Cancellation-ahead fractions of 0%, 50%, and 100% are tested; raw historical market events and displayed quote depth are observations, not simulated.

Source: [LOBSTER official sample downloads](https://php.lobsterdata.com/info/DataSamples.php). Data are not redistributed here.

![Five-stock historical queue model net P&L](results/cross_stocks/stock_pnl.svg)

## Verified one-day results: 0% cancellation assumed ahead

| Ticker | Actual LOBSTER level-5 events | Fixed net midpoint P&L | Inventory-aware net midpoint P&L | Fixed average abs. inventory | Aware average abs. inventory |
|---|---:|---:|---:|---:|---:|
| AAPL | 301,587 | **+$27.714** | +$6.558 | 4.254 | **1.027** |
| AMZN | 155,935 | **+$14.984** | +$2.702 | 2.823 | **1.334** |
| GOOG | 112,673 | **+$51.590** | +$29.146 | 4.675 | **2.530** |
| INTC | 581,030 | −$2.314 | **−$1.062** | 3.551 | **0.680** |
| MSFT | 595,800 | **+$2.496** | −$0.212 | 2.397 | **0.657** |

Inventory-aware quoting reduced **time-weighted absolute inventory exposure in all five of these single-day examples**, but had higher hypothetical net profit for only **one of the five stocks (INTC)** under the conservative 0% cancellation-ahead setting.

### Profit sensitivity across cancellation assumptions

| Ticker | 0% fixed / aware | 50% fixed / aware | 100% fixed / aware |
|---|---|---|---|
| AAPL | +$27.71 / +$6.56 | +$36.60 / +$9.23 | +$26.49 / +$5.26 |
| AMZN | +$14.98 / +$2.70 | +$10.59 / +$4.60 | +$13.19 / +$4.42 |
| GOOG | +$51.59 / +$29.15 | +$47.14 / +$21.79 | +$55.42 / +$27.64 |
| INTC | −$2.31 / −$1.06 | −$2.37 / −$1.42 | −$3.00 / −$2.35 |
| MSFT | +$2.50 / −$0.21 | −$1.58 / −$0.50 | −$3.55 / −$2.54 |

Net P&L in this table is **marked at the final historical midpoint**, not an executable portfolio liquidation. The underlying CSV artifact additionally includes hypothetical fill counts, realised cash/fee components, closing-inventory exit sensitivity and drawdown.

## Interpretation

These findings do **not** imply that one strategy is reliably more profitable across the market. All five instruments share a single date, with different absolute prices, spreads, liquidity and queue dynamics. The strategies use fixed **one-share** order size, and the dollar profits are **not risk-adjusted or comparable as investment returns** across all five instruments.

The strongest observation is qualitative: **inventory management systematically reduced modelled exposure, but its incremental hypothetical profit depended on stock and queue assumptions.** Some policies lost money after our illustrative fees. That illustrates the importance of robustness checks, not evidence of exploitable arbitrage.

## What comes next

The genuinely independent-date experiment is the [Nasdaq 2019–2020 seven-day workflow](https://github.com/rileysanders/market-making-inventory-simulator/actions/workflows/nasdaq-seven-days.yml), which uses a distinct binary ITCH order-ID reconstructor and reports results separately by real trading day.

Even after seven nonrandom sample dates, this is still early-stage evidence. Claims of robust expected profitability require additional independent dates, better execution/queue calibration, and a formal out-of-sample evaluation.

Source code: [cross_stock_replay.py](cross_stock_replay.py). Original public data remain with the vendor. Developed with AI assistance.
