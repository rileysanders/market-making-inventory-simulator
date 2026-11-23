"""Experiment 4: historical AAPL best-quote/event replay (LOBSTER, 2012-06-21).

Usage:
    python aapl_replay.py --download --output results/aapl
    python aapl_replay.py --zip path/to/LOBSTER_SampleFile_AAPL_2012-06-21_1.zip

The recorded trades, quotes, sizes and timestamps are historical; our quotes
and fills are hypothetical. This is NOT a validated executable strategy or a
backtest with order-level execution priority.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import urllib.request
from bisect import bisect_left
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import TextIO
from zipfile import ZipFile

PRICE_SCALE = 10_000  # LOBSTER raw prices are dollars * 10,000.
TICK = 100             # 100 raw price units = 1 cent.
STEM = "AAPL_2012-06-21_34200000_57600000"
SAMPLE_FILENAME = "LOBSTER_SampleFile_AAPL_2012-06-21_1.zip"
SOURCES = (
    "https://php.lobsterdata.com/info/sample/" + SAMPLE_FILENAME,
    "https://data.lobsterdata.com/info/sample/" + SAMPLE_FILENAME,
)
MIRROR_BASE = (
    "https://huggingface.co/datasets/totalorganfailure/lobster-data/"
    "resolve/main/LOBSTER_SampleFile_AAPL_2012-06-21_1/"
)


@dataclass(frozen=True)
class Event:
    timestamp: float
    kind: int
    size: int
    trade_price: int
    direction: int
    ask: int
    ask_size: int
    bid: int
    bid_size: int

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def valid_book(self) -> bool:
        return 0 < self.bid < self.ask and self.ask_size > 0 and self.bid_size > 0


def load_pairs(messages: TextIO, books: TextIO) -> list[Event]:
    """Pair LOBSTER message row i with the POST-event best book state i."""
    message_reader, book_reader = csv.reader(messages), csv.reader(books)
    results: list[Event] = []
    for index, (m, b) in enumerate(zip_longest(message_reader, book_reader), 1):
        if m is None or b is None:
            raise ValueError(f"Message/book row counts differ at line {index}")
        if len(m) != 6 or len(b) != 4:
            raise ValueError(
                f"Expected 6 message and 4 L1 book columns at line {index}"
            )
        timestamp = float(m[0])
        if not math.isfinite(timestamp) or (
            results and timestamp < results[-1].timestamp
        ):
            raise ValueError(f"Nonmonotone/invalid event timestamp at line {index}")
        event = Event(
            timestamp, int(m[1]), int(m[3]), int(m[4]), int(m[5]),
            int(b[0]), int(b[1]), int(b[2]), int(b[3]),
        )
        if event.kind == 7:
            raise ValueError(
                "Trading halt indicator present: halt-aware replay not implemented"
            )
        results.append(event)
    if len(results) < 2:
        raise ValueError("Need at least two historical events for pre-event quotes")
    return results


def read_zip(path: Path) -> list[Event]:
    if not path.is_file():
        raise FileNotFoundError(
            f"Cannot find {path}; use --download or download LOBSTER sample ZIP"
        )
    with ZipFile(path) as archive:
        msg_paths = [
            x for x in archive.namelist() if x.endswith("_message_1.csv")
        ]
        book_paths = [
            x for x in archive.namelist() if x.endswith("_orderbook_1.csv")
        ]
        if len(msg_paths) != 1 or len(book_paths) != 1:
            raise ValueError(
                "Expected one *_message_1.csv and one *_orderbook_1.csv in ZIP"
            )
        with archive.open(msg_paths[0]) as raw_messages:
            with archive.open(book_paths[0]) as raw_books:
                with io.TextIOWrapper(raw_messages, encoding="utf-8") as m:
                    with io.TextIOWrapper(raw_books, encoding="utf-8") as b:
                        return load_pairs(m, b)


def download_sample(path: Path) -> None:
    """Download the vendor sample locally only; never commit the raw data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    errors = []
    for url in SOURCES:
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 educational research"}
            )
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read()
            path.write_bytes(body)
            with ZipFile(path) as archive:
                if not any(
                    name.endswith("_message_1.csv") for name in archive.namelist()
                ):
                    raise ValueError(
                        "Wrong ZIP or provider returned an HTML document"
                    )
            print(f"Downloaded LOBSTER AAPL sample from {url}")
            return
        except Exception as error:
            path.unlink(missing_ok=True)
            errors.append(f"{url}: {error}")

    # The secondary mirror contains the original sample CSVs, not a backtest.
    try:
        from zipfile import ZIP_DEFLATED
        payload = {}
        for type_ in ("message", "orderbook"):
            name = f"{STEM}_{type_}_1.csv"
            request = urllib.request.Request(
                MIRROR_BASE + name, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                payload[name] = response.read()
        with ZipFile(path, "w", ZIP_DEFLATED) as archive:
            for name, body in payload.items():
                archive.writestr(name, body)
        print("Downloaded LOBSTER sample CSVs from the secondary data mirror")
        return
    except Exception as error:
        path.unlink(missing_ok=True)
        errors.append(f"Mirror: {error}")
    raise RuntimeError(
        "Sample download failed. Manually download from the LOBSTER sample page.\n"
        + "\n".join(errors)
    )


@dataclass
class ReplayState:
    cash_raw: int = 0
    inventory: int = 0
    trades: int = 0
    max_abs_inventory: int = 0
    eligible_prints: int = 0


def proposed_quotes(
    pre: Event, inventory: int, inventory_aware: bool, tick: int = TICK
) -> tuple[int, int]:
    """Passive quoting: no crossing and no improving inside the best quotes.

    Long inventory -> bid lower. Short inventory -> ask higher. This
    risk-reduction rule is DISTINCT from the earlier continuous quote shift.
    """
    bid = pre.bid - (
        max(inventory, 0) * tick if inventory_aware else 0
    )
    ask = pre.ask + (
        max(-inventory, 0) * tick if inventory_aware else 0
    )
    return bid, ask


def print_crosses_order(
    event: Event, bid_quote: int, ask_quote: int, mode: str, tick: int = TICK
) -> int:
    """+1 buy, -1 sell, or zero when no historical execution qualifies.

    'touch' assumes a fill at an equal-price print (optimistic; FIFO ignored).
    'through' requires the executed trade to pass our price by at least a tick.
    LOBSTER direction refers to the RESTING order's side.
    """
    if event.kind != 4 or event.size < 1:
        return 0
    if mode not in ("touch", "through"):
        raise ValueError("mode must be touch or through")
    gap = 0 if mode == "touch" else tick
    if event.direction == 1 and event.trade_price <= bid_quote - gap:
        return 1
    if event.direction == -1 and event.trade_price >= ask_quote + gap:
        return -1
    return 0


def replay(
    events: list[Event],
    mode: str,
    inventory_aware: bool,
    fee_cents: float = 0.3,
    inventory_limit: int = 6,
    tick: int = TICK,
) -> dict[str, object]:
    if mode not in ("touch", "through"):
        raise ValueError("mode must be touch or through")
    if not math.isfinite(fee_cents) or fee_cents < 0:
        raise ValueError("Fee must be finite and nonnegative")
    if inventory_limit < 1 or tick < 1:
        raise ValueError("Inventory limit and tick must be positive")
    state = ReplayState()
    valid_prev = None
    last_valid_mid = None

    # For event i, decide using ONLY the post-event snapshot from i-1.
    for event in events:
        if event.valid_book:
            last_valid_mid = event.mid
        if valid_prev is not None and event.kind == 4:
            bid, ask = proposed_quotes(
                valid_prev, state.inventory, inventory_aware, tick
            )
            action = print_crosses_order(event, bid, ask, mode, tick)
            if action:
                state.eligible_prints += 1
            if action == 1 and state.inventory < inventory_limit:
                state.cash_raw -= bid
                state.inventory += 1
                state.trades += 1
            elif action == -1 and state.inventory > -inventory_limit:
                state.cash_raw += ask
                state.inventory -= 1
                state.trades += 1
            state.max_abs_inventory = max(
                state.max_abs_inventory, abs(state.inventory)
            )
        valid_prev = event if event.valid_book else None

    if last_valid_mid is None:
        raise ValueError("No valid book snapshots")
    gross = (state.cash_raw + state.inventory * last_valid_mid) / PRICE_SCALE
    net = gross - state.trades * fee_cents / 100.0
    return {
        "policy": "inventory aware" if inventory_aware else "fixed quotes",
        "fill_assumption": mode,
        "executed_shares": state.trades,
        "eligible_prints": state.eligible_prints,
        "ending_inventory": state.inventory,
        "peak_abs_inventory": state.max_abs_inventory,
        "gross_pnl_usd": round(gross, 4),
        "net_pnl_usd": round(net, 4),
    }


def measure_real_markouts(
    events: list[Event], seconds: float
) -> dict[str, object]:
    """Volume-weighted markouts of ACTUAL displayed historical executions.

    Reference price is the actual execution price; future midpoint is first
    historical snapshot at or after the horizon. This is observational, not
    a hypothetical fill or strategy return.
    """
    if seconds <= 0:
        raise ValueError("Markout horizon must be positive")
    times = [e.timestamp for e in events]
    eligible = 0
    volume = 0
    edge_raw = 0.0
    change_raw = 0.0
    for idx in range(1, len(events)):
        event = events[idx]
        pre = events[idx - 1]
        if (
            event.kind != 4 or event.size <= 0
            or event.direction not in (-1, 1)
            or not pre.valid_book
        ):
            continue
        future_idx = bisect_left(
            times, event.timestamp + seconds, lo=idx + 1
        )
        if future_idx >= len(events):
            continue
        future = events[future_idx]
        if not future.valid_book:
            continue
        eligible += 1
        volume += event.size
        edge_raw += (
            event.direction * (future.mid - event.trade_price) * event.size
        )
        change_raw += (
            event.direction * (future.mid - pre.mid) * event.size
        )
    return {
        "markout_horizon_seconds": seconds,
        "observed_visible_executions": eligible,
        "observed_executed_shares": volume,
        "passive_execution_price_markout_usd_per_share": (
            round(edge_raw / volume / PRICE_SCALE, 6) if volume else None
        ),
        "post_trade_mid_move_usd_per_share": (
            round(change_raw / volume / PRICE_SCALE, 6) if volume else None
        ),
    }


def run(
    events: list[Event], fee_cents: float = 0.3, inventory_limit: int = 6
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    policies = [
        replay(events, mode, aware, fee_cents, inventory_limit)
        for mode in ("touch", "through")
        for aware in (False, True)
    ]
    markouts = [
        measure_real_markouts(events, horizon) for horizon in (1.0, 5.0)
    ]
    return policies, markouts


def save(
    output: Path,
    events: list[Event],
    policies: list[dict[str, object]],
    markouts: list[dict[str, object]],
    fee_cents: float,
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for filename, rows in [
        ("policy_replay.csv", policies),
        ("observed_markouts.csv", markouts),
    ]:
        with (output / filename).open(
            "w", newline="", encoding="utf-8"
        ) as file:
            writer = csv.DictWriter(file, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    (output / "run_info.json").write_text(
        json.dumps(
            {
                "source": "LOBSTER NASDAQ Historical TotalView-ITCH sample",
                "ticker": "AAPL",
                "date": "2012-06-21",
                "events": len(events),
                "first_timestamp_seconds": events[0].timestamp,
                "last_timestamp_seconds": events[-1].timestamp,
                "fee_cents_per_fill": fee_cents,
                "source_data_in_repository": False,
                "note": (
                    "Actual observed trades and quotes; "
                    "simulated hypothetical fills only."
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return
    labels = [
        "Fixed / touch",
        "Aware / touch",
        "Fixed / through",
        "Aware / through",
    ]
    values = [p["net_pnl_usd"] for p in policies]
    fig, ax = plt.subplots(figsize=(8.5, 4.7))
    ax.bar(labels, values)
    ax.axhline(0, color="gray", linewidth=1)
    ax.set(
        ylabel="Hypothetical net P&L (USD)",
        title="AAPL 2012-06-21: execution-assumption sensitivity",
    )
    fig.tight_layout()
    fig.savefig(output / "hypothetical_pnl.png", dpi=170)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip", dest="zip_path", type=Path,
        default=Path("data") / SAMPLE_FILENAME,
    )
    parser.add_argument(
        "--download", action="store_true",
        help="Download sample ZIP locally if missing",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("results/aapl")
    )
    parser.add_argument("--fee-cents", type=float, default=0.3)
    parser.add_argument("--inventory-limit", type=int, default=6)
    args = parser.parse_args()

    if args.download:
        download_sample(args.zip_path)
    events = read_zip(args.zip_path)
    policies, markouts = run(events, args.fee_cents, args.inventory_limit)
    save(args.output, events, policies, markouts, args.fee_cents)
    print(f"Historical AAPL events loaded: {len(events):,} (2012-06-21)")
    print("Observed historical market trades (actual execution markouts):")
    for row in markouts:
        print(row)
    print("HYPOTHETICAL quote replay (NOT actual historical fills):")
    for row in policies:
        print(row)
    print(f"Saved outputs: {args.output.resolve()}")


if __name__ == "__main__":
    main()
