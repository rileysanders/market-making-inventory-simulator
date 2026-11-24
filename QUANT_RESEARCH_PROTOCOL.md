# Quantitative Research Protocol — Historical AAPL Market Making

## Status and scientific claim boundary

**Research status:** 24 November 2026. Experimental Python code, historical single-day LOBSTER results, automated unit tests and reproducible workflows exist. A new Nasdaq 2019–2020 *seven different date* evaluation has been launched, but its numerical results **must not be interpreted as verified until the GitHub workflow succeeds and the summary artifact is inspected**.

This is an AI-assisted **research simulator**, not an exchange-validated backtester, executable trading system or proven investment strategy. Our candidate quote and queue fills remain **hypothetical** even when all underlying market orders and quotes originate from actual exchange records.

## Hypotheses specified before examining the new dates

- **H1: Risk exposure.** Inventory-aware quoting will have a lower time-weighted average absolute inventory than fixed best-quote market making.
- **H2: Profitability.** There is no assumption that inventory awareness increases the strategy's realized or hypothetical net profitability.
- **H3: Execution sensitivity.** Changes in assumed cancellation-ahead fraction may materially change fill rates, profit and ranking.
- **H4: Generalisation.** A result from the 2012 LOBSTER AAPL sample need not repeat across later, independent Nasdaq sample dates.

### Fixed, predeclared model settings

- Symbols/venue: AAPL, **Nasdaq exchange only**, not consolidated NBBO
- Historical source: published Nasdaq TotalView-ITCH 5.0 **full-day samples**
- Exact sample dates: 2019-01-30, 2019-03-27, 2019-07-30, 2019-08-30, 2019-10-30, 2019-12-30, 2020-01-30
- Analysis session: 09:30:00–16:00:00 US Eastern; premarket book events used only to initialise the 09:30 starting book
- Quoting: passive join of best bid/ask, two-sided one-share orders, six-share absolute inventory cap
- Strategy: fixed bid/ask versus **one tick per inventory unit** retreat on the inventory-increasing side
- Market-maker quote refresh: every 2 seconds
- Assumed order entry latency: 10 milliseconds
- Queue ahead: entire observed displayed depth at the quote price on placement
- Cancellation ahead sensitivity: 0%, 50%, 100% of historical cancellations/deletions at the same quote price assigned to the estimated ahead queue
- Fill estimate: same-side historical executions at quote price deplete ahead quantity; only volume beyond it grants a hypothetical one-share fill
- Passive fee: assumed 0.3 US cents/share, **not historical Nasdaq fee schedule**
- Daily P&L: hypothetical cash + ending inventory valued at closing midpoint, less passive fees
- Secondary liquidation sensitivity: ending inventory crossed at final historical opposite best bid/ask when displayed depth is adequate, plus assumed 1 US cent/share exit fee

**We will not change these settings after examining the seven-day results**, and we will publish all three cancellation-ahead assumptions whether they favor or disfavor inventory-aware quoting. These settings represent a controlled empirical sensitivity experiment, not a calibrated execution model.

## Event processing, integrity checks, and causal ordering

The new [native Nasdaq binary decoder](nasdaq_itch.py) parses 2-byte-length-prefixed, big-endian TotalView-ITCH 5.0 messages. It identifies AAPL from the exchange's **Stock Directory (R)** event, maintains original limit order reference IDs and displayed price-level quantities, and processes:

- **A / F:** displayed order entry, with or without MPID attribution;
- **E / C:** partial/full execution of the referenced resting order, including execution at a distinct reported price;
- **X:** partial cancellation;
- **D:** full deletion;
- **U:** atomic replacement: original order loses its reference and price-time priority; new ID and quantity enter the book.

The queue replay uses **post-event** book snapshots for new quotes and only processes later market events against those orders. Quotes are not eligible for fills until the configured latency passes. The decoder rejects unknown referenced orders, over-cancellations, nonsensical quantities, time reversals and a detected halt.

The data path does **not** process consolidated trades from other venues as if they executed in Nasdaq's order book. Auction cross/trade messages are not added to the passive displayed book. Non-displayed liquidity and other order attributes remain important sources of execution error.

## Research design and reporting

The independent sampling unit is the **trading day**, not the millions of ITCH messages; individual events are strongly correlated within and across sessions.

We report a table of all **seven distinct historical dates** with:
1. hypothetical net dollars and end-of-day liquidation estimate per policy;
2. average absolute inventory and peak drawdown;
3. count of hypothetical fills, fees and cancellations;
4. sensitivity to the queue-cancellation-ahead assumptions;
5. per-day paired differences, including the number of days each policy is ahead.

The strategy and assumptions are **predefined**. The final two dates (2019-12-30 and 2020-01-30) are separately labelled a descriptive chronological **holdout**, not used to select the strategy. There is **no parameter fitting** from this small sample.

The seven public sample dates are **not a random sample of market history**, cover one venue only, and have limited breadth. **Seven days do not justify a statistically confident profitability claim, annualised Sharpe, robust monthly income estimate or institutional execution claim.** The two-date holdout is particularly underpowered.

No new raw market data should be checked into the public repository; official exchange endpoints and derived small CSV and JSON tables only.

## Known execution-model limitations

- **Hypothetical order placement alters the counterfactual exchange book.** Real market participant responses may differ from the observed tape.
- **Displayed queue depth is a proxy, not validated live queue position.** ITCH contains order IDs that could support a more sophisticated queue accounting model, but the current market-making engine still uses cancellation-ahead sensitivity fractions rather than exact behind/ahead attribution.
- **Order latency is simplified.** Entry latency is modelled; full message propagation, cancel acknowledgement and replace-to-live timing are not independently calibrated.
- **Our orders are one share.** This is not an economically optimised sizing or capital deployment strategy.
- **Historical fees are illustrative.** Nasdaq liquidity rebates, maker/taker tiers, broker fees, venue routing and slippage are not calibrated to the source dates.
- **Midpoint marks are not executable liquidation.** We report an explicitly assumed best-quote exit and extra exit fee as a separate sensitivity.
- **No external hedge, overnight inventory financing, alpha features or realistic order-flow response** is modelled.

Any positive net hypothetical outcome is a **model output**, not an observed profit or an investable arbitrage.

## Evidence hierarchy

1. **Observed:** historical Nasdaq messages, timestamps, executed share volumes, book depth and order IDs.
2. **Reconstructed:** best quotes and historical displayed quantities after processing ITCH events, provided reconstructor invariants hold.
3. **Counterfactual:** our order queue position, order arrival time, fills, fees, inventory, drawdowns and hypothetical P&L.
4. **Unproven:** strategy expected profitability, exchange match rates, market impact and out-of-sample economic value.

## Related literature and methodological differences

- **Avellaneda, M. & Stoikov, S. (2008), "High-frequency trading in a limit order book", Quantitative Finance.** [Publisher / DOI](https://doi.org/10.1080/14697680701381228). Introduces inventory-aware market-making control using reservation prices and optimal spread choices. **Our fixed one-tick inventory quote retreat is a teaching-oriented heuristic, not a calibrated or numerically solved Avellaneda–Stoikov optimal policy.**
- **Cont, R., Stoikov, S. & Talreja, R. (2010), "A Stochastic Model for Order Book Dynamics", Operations Research.** [Publisher / DOI](https://doi.org/10.1287/opre.1090.0780). Motivates the importance of limit-order arrivals, cancellations, execution priority and book-state-dependent fills. **Our replay uses actual event tapes, but approximates hypothetical queue priority rather than fitting the authors' stochastic order-book model.**
- **Gould, M. D. et al. (2013), "Limit order books", Quantitative Finance.** [Publisher / DOI](https://doi.org/10.1080/14697688.2013.803148). A review of market-microstructure data, order-book dynamics and empirical modelling issues. **Our one-venue, seven-date experiment is a narrow illustrative study rather than a comprehensive cross-venue evaluation.**

The related work supports *which mechanisms are worth measuring*, not the accuracy of this simulator's assumed execution model or any implied profitability.

## Required gates before making stronger claims

1. Successful complete run of each of the seven verified public dates; report any failures.
2. Independent audit of reconstructed book invariants, tick units, AAPL identification and full-day session boundaries.
3. Check magnitude and plausibility of calculated fill rates, spreads and drawdowns.
4. Report all daily outcomes and cancellation assumptions without cherry-picking winners.
5. Acquire 30–60+ additional genuinely different historical days, ideally under student/research licence, if seeking credible out-of-sample inference.
6. Improve queue reconstruction with order-level priority tracking, cancellation acknowledgements and stricter latency/fee calibration.
7. Consider independent validation against a second implementation or source for a matching date.

**No historical data purchase is required to examine the seven public Nasdaq sample days.** Further provider-specific historical data must be licensed and quoted before the user spends any money.

## Reproducibility

- [Nasdaq ITCH decoder](nasdaq_itch.py)
- [One-day streaming replay](nasdaq_day_replay.py)
- [Chronological descriptive multi-day report](nasdaq_multiday_report.py)
- [Seven-day GitHub Action](.github/workflows/nasdaq-seven-days.yml)
- [Native ITCH parsing tests](tests/test_nasdaq_itch.py)
- [Multi-day provenance and reporting tests](tests/test_nasdaq_multi_report.py)

Run locally with an independently downloaded full-day Nasdaq ITCH 5.0 file, or use GitHub Actions to stream it without storing the multi-gigabyte source in the repository. Historical market data source: [Nasdaq ITCH](https://emi.nasdaq.com/ITCH/). Protocol reference: [Nasdaq TotalView-ITCH specification](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification_5.0.pdf).
