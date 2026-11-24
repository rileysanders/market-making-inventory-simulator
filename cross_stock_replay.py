"""Cross-stock robustness on five Nasdaq stocks, ONE historical day.

Source: official LOBSTER level-5 samples on 2012-06-21.
Historical market messages are real; our fills are all hypothetical.
"""
from __future__ import annotations
import argparse
import json
import urllib.request
from pathlib import Path
from zipfile import ZipFile
from queue_replay import Config, run_day, save_rows

STOCKS = ("AAPL", "AMZN", "GOOG", "INTC", "MSFT")
DAY = "2012-06-21"


def sample_name(ticker: str) -> str:
    if ticker not in STOCKS:
        raise ValueError("Unsupported ticker")
    return f"LOBSTER_SampleFile_{ticker}_{DAY}_5.zip"


def official_url(ticker: str) -> str:
    return "https://php.lobsterdata.com/info/sample/" + sample_name(ticker)


def download(ticker: str, path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        official_url(ticker),
        headers={"User-Agent": "UniversityMarketMicrostructureResearch/1.0"}
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read()
    path.write_bytes(data)
    try:
        with ZipFile(path) as archive:
            if not any(f.endswith("_message_5.csv") for f in archive.namelist()):
                raise ValueError("Invalid LOBSTER level-5 source")
    except Exception:
        path.unlink(missing_ok=True)
        raise


def run(data_dir: Path, output: Path, auto_download: bool) -> list[dict]:
    configs = [
        Config(skew_ticks=s, cancel_ahead_fraction=c, latency_ms=10,
               refresh_s=2, fee_cents=.3, inventory_limit=6)
        for c in (0, .5, 1) for s in (0, 1)
    ]
    rows = []
    for ticker in STOCKS:
        path = data_dir / sample_name(ticker)
        if auto_download:
            download(ticker, path)
        if not path.is_file():
            raise FileNotFoundError(path)
        results = run_day(path, configs, depth=5, day_override=DAY)
        if results[0]["market_events"] < 100:
            raise ValueError("Incomplete sample for " + ticker)
        rows.extend([dict(ticker=ticker, **row) for row in results])
        print(ticker, results[0]["market_events"], "historical book events",flush=True)
        for row in results:
            if row["cancel_ahead_fraction"] == 0:
                print(row["policy"], "hypothetical fills", row["hypothetical_fills"],
                      "net USD", row["net_pnl_usd"],flush=True)
    output.mkdir(parents=True, exist_ok=True)
    save_rows(output / "five_stock_queue_results.csv", rows)
    (output/"provenance.json").write_text(json.dumps({
        "source": "LOBSTER official free samples",
        "historical_date": DAY,
        "distinct_stocks": list(STOCKS),
        "distinct_dates": [DAY],
        "order_book_depth": 5,
        "raw_market_data_distributed": False,
        "source_urls": [official_url(t) for t in STOCKS],
        "candidate_order_fills_are_hypothetical": True,
        "limitations": "One calendar day across five stocks, not five trading days; costs and fill priority are assumptions."
    },indent=2)+"\n")
    return rows


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir",type=Path,default=Path("data/cross_stocks"))
    p.add_argument("--output",type=Path,default=Path("results/cross_stocks"))
    p.add_argument("--download",action="store_true")
    args=p.parse_args()
    rows=run(args.data_dir,args.output,args.download)
    print("Saved",len(rows),"strategy/scenario results to",args.output,flush=True)


if __name__=="__main__":
    main()
