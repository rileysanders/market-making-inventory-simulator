# Data acquisition for extending the completed AAPL multi-day study

**Completed without purchase:** Seven **different** historical Nasdaq TotalView-ITCH 5.0 full-day samples (2019–2020) were downloaded and analysed successfully. [Read the verified seven-day results](NASDAQ_MULTI_DAY_RESULTS.md). **No user money was spent.**

**Further goal:** for stronger inference obtain **at least 30 independently dated AAPL trading sessions**, preferably 60 or more, with event-by-event order and displayed book information. Purchase *historical market data*, not shares. Do not spend money on a brokerage account or live trading for this project.

## Option 1: LOBSTER historical AAPL, level 5 (additional paid days)

Official service: https://php.lobsterdata.com/

Request:
- Ticker: **AAPL**
- 30–60 **distinct business days** in a single research period (avoid cherry-picking only volatile or profitable days)
- Nasdaq regular hours **09:30–16:00 America/New_York**
- **5 displayed price levels** (matching the free sample already tested)
- Paired **message and order-book** CSV files per date, preferably zipped separately per day
- A student/academic personal-use licence, if available
- Written confirmation of what **derived summary metrics and figures** you may publish publicly on GitHub

Cost: **not yet quoted**. No purchase has been made. Check whether your university has a research subscription first.

## Alternative: Databento Nasdaq TotalView-ITCH MBO

Official product: https://databento.com/datasets/XNAS.ITCH
Pricing: https://databento.com/pricing

Databento advertises **USD $125 of introductory historical-data credits** for eligible new signups. Obtain a **precise quote for 30–60 days of AAPL MBO events** and confirm eligibility, historical coverage, exchange fees, access permissions, and personal nonprofessional licensing *before* paying.

**Important compatibility warning:** Databento DBN/MBO data is NOT LOBSTER CSV. The existing `multi_day_research.py` cannot load it without a separately developed and tested adapter that maintains per-order event chronology and reconstructs order-book depth. Do not rename or directly convert it to LOBSTER CSV without reconstructing the corresponding book.

## How to run the multi-day pipeline once LOBSTER ZIPs are licensed

Put all original vendor ZIPs in a local directory:

```text
data/
  aapl_days/
    AAPL-day-01.zip
    AAPL-day-02.zip
    ...
```

ZIP filenames can vary, but the *contents* must contain exactly one matched `AAPL_YYYY-MM-DD_..._message_5.csv` and `AAPL_YYYY-MM-DD_..._orderbook_5.csv` pair.

In Windows Command Prompt inside the project folder:

```cmd
python -m unittest discover -s tests -v
python multi_day_research.py --data-dir data\aapl_days --output results\multi_day
```

Expected results:
- `daily_policy_results.csv` — each strategy, date, latency and queue-assumption setting.
- `walk_forward_summary.json` — chronological development/validation/test splits and policy chosen *before* inspection of holdout days.
- `holdout_robustness.csv` — paired holdout daily P&L differences and exploratory uncertainty intervals.

The program rejects duplicate dates and does not treat repeated simulations of the free AAPL sample as additional market days.

## Protocol for credibility

1. Fix the date period and source before analysing the results.
2. Audit every file for chronological timestamps, halt sessions and valid book integrity.
3. Use the same market period for both quote policies.
4. Select any strategy parameter only on the **validation** days.
5. Report **all** queue and latency assumption settings on completely untouched test dates.
6. Show *both* marked-to-mid and terminal-liquidation sensitivity. Neither constitutes a guaranteed executable fill.
7. Report failures, lack of fills, contradictory scenarios, and limitations prominently.

**Current status:** free single-day AAPL Level-5 execution study completed. Multi-day **framework exists but has not been applied to a licensed 30–60-day sample**. We cannot responsibly publish multi-day AAPL Sharpe ratios or statistically significant edges without those dates.
