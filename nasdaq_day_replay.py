"""Run an AAPL historical event-by-event market-making replay on Nasdaq ITCH.

Uses real public full-session Nasdaq ITCH 5.0 exchange messages.
All our candidate order fills are STILL counterfactual queue estimates.

Examples:
  python nasdaq_day_replay.py --date 01302019 --output results/itch/01302019
  python nasdaq_day_replay.py --date 01302019 --file data/01302019.NASDAQ_ITCH50.gz
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from nasdaq_itch import ReconstructionStats, download_stream, public_url, replay_aapl_itch
from queue_replay import Config, QueueAgent, save_rows


def strategy_configs() -> list[Config]:
    return [
        Config(skew_ticks=skew, cancel_ahead_fraction=f, latency_ms=10.0,
               refresh_s=2.0, fee_cents=.3, inventory_limit=6)
        for f in (0.0, .5, 1.0) for skew in (0, 1)
    ]


def run_feed(stream, date: str, configs: list[Config] | None = None):
    if configs is None:
        configs = strategy_configs()
    day = datetime.strptime(date, "%m%d%Y").strftime("%Y-%m-%d")
    stats = ReconstructionStats(date)
    agents = [QueueAgent(c) for c in configs]
    previous = None
    count = 0
    for event in replay_aapl_itch(stream, date, depth=5, stats=stats):
        count += 1
        for agent in agents:
            agent.on_event(event, previous)
        previous = event
    if count < 2:
        raise ValueError(f"No meaningful regular-session AAPL events on {day}")
    return [agent.summary(day, count) for agent in agents], stats


def write_run(output: Path, rows: list[dict], stats: ReconstructionStats):
    output.mkdir(parents=True, exist_ok=True)
    save_rows(output / "policy_results.csv", rows)
    meta = dict(
        raw_source=public_url(stats.date),
        symbol="AAPL",
        exchange="Nasdaq",
        format="TotalView-ITCH 5.0",
        date=stats.date,
        all_feed_messages=stats.all_messages,
        aapl_book_events=stats.aapl_book_events,
        regular_session_aapl_book_events=stats.regular_session_events,
        stock_locate=stats.stock_locate,
        market_data_are_historical=True,
        strategy_order_fills_are_hypothetical=True,
        market_source_contains_all_symbols=True,
        market_data_redistributed=False,
        caveat=(
            "One-venue historical order-book replay with hypothetical queue "
            "position, execution, latency, and fees. No market-impact feedback. "
            "No demonstrated profit or investable trading strategy."
        ),
    )
    (output / "provenance.json").write_text(json.dumps(meta, indent=2) + "\n")
    return meta


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--date", required=True, help="MMDDYYYY public Nasdaq date, e.g. 01302019")
    p.add_argument("--file", type=Path, help="Existing original NASDAQ_ITCH50.gz file")
    p.add_argument("--output", type=Path)
    args = p.parse_args()
    dest = args.output or Path("results/nasdaq_public") / args.date
    if args.file:
        with args.file.open("rb") as stream:
            rows, stats = run_feed(stream, args.date)
    else:
        with download_stream(args.date, timeout=180) as stream:
            rows, stats = run_feed(stream, args.date)
    meta = write_run(dest, rows, stats)
    print("Source:", meta["raw_source"], flush=True)
    print(f"Total recorded Nasdaq events: {meta['all_feed_messages']:,}", flush=True)
    print(f"AAPL regular-session events: {meta['regular_session_aapl_book_events']:,}", flush=True)
    for row in rows:
        print(f"queue_cancel={row['cancel_ahead_fraction']:.1f} "
              f"{row['policy']:<13} fills={row['hypothetical_fills']:>6} "
              f"net_marked_usd={row['net_pnl_usd']:+.4f} "
              f"net_liquidated_usd={row['terminal_liquidated_net_usd']} "
              f"mean_inventory={row['average_abs_inventory']:.3f}", flush=True)
    print("Saved derived summary:", dest, flush=True)


if __name__ == "__main__":
    main()
