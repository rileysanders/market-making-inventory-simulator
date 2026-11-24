"""Depth-aware, event-driven LOBSTER AAPL queue replay (research, not live trading).

Observes historical order events and displayed depths; simulated FIFO
queue-ahead position is a counterfactual estimate, not an observed fill.
Run: python queue_replay.py --download
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import re
import urllib.request
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path
from typing import Iterator
from zipfile import ZipFile

SCALE = 10_000
TICK = 100
SAMPLE = "LOBSTER_SampleFile_AAPL_2012-06-21_5.zip"
DATA_URL = "https://php.lobsterdata.com/info/sample/" + SAMPLE


@dataclass(frozen=True)
class Event:
    ts: float
    kind: int
    order_id: int
    size: int
    price: int
    side: int
    asks: tuple[tuple[int, int], ...]
    bids: tuple[tuple[int, int], ...]

    def valid(self) -> bool:
        return bool(self.asks and self.bids and 0 < self.bids[0][0] < self.asks[0][0]
                    and self.asks[0][1] > 0 and self.bids[0][1] > 0)

    def mid(self) -> float:
        return (self.asks[0][0] + self.bids[0][0]) / 2

    def depth_at(self, side: int, price: int) -> int | None:
        for p, qty in (self.bids if side == 1 else self.asks):
            if p == price and qty > 0:
                return qty
        return None


def stream_zip(path: Path, depth: int = 5) -> Iterator[Event]:
    """Row i of the LOBSTER book is POST-event i, not a tradable pre-event quote."""
    with ZipFile(path) as archive:
        ms = [x for x in archive.namelist() if x.endswith(f"_message_{depth}.csv")]
        bs = [x for x in archive.namelist() if x.endswith(f"_orderbook_{depth}.csv")]
        if len(ms) != 1 or len(bs) != 1:
            raise ValueError(f"Expected matching LOBSTER level-{depth} message/book CSVs: {path}")
        previous = float("-inf")
        with archive.open(ms[0]) as raw_msg, archive.open(bs[0]) as raw_book:
            msgs = csv.reader(io.TextIOWrapper(raw_msg, encoding="utf-8"))
            books = csv.reader(io.TextIOWrapper(raw_book, encoding="utf-8"))
            for i, (m, b) in enumerate(zip_longest(msgs, books), 1):
                if m is None or b is None or len(m) != 6 or len(b) != depth * 4:
                    raise ValueError(f"Corrupted/misaligned LOBSTER rows at line {i}")
                ts = float(m[0])
                if not math.isfinite(ts) or ts < previous:
                    raise ValueError(f"Nonmonotone timestamp at line {i}")
                kind = int(m[1])
                if kind == 7:
                    raise ValueError(f"LOBSTER trading halt requires separate handling (line {i})")
                if kind not in (1, 2, 3, 4, 5, 6):
                    raise ValueError(f"Unknown event kind at line {i}")
                cols = list(map(int, b))
                asks = tuple((cols[j], cols[j+1]) for j in range(0, depth*4, 4))
                bids = tuple((cols[j+2], cols[j+3]) for j in range(0, depth*4, 4))
                yield Event(ts, kind, int(m[2]), int(m[3]), int(m[4]),
                            int(m[5]), asks, bids)
                previous = ts


def download_sample(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(DATA_URL, headers={"User-Agent": "Mozilla/5.0 academic-research"})
    with urllib.request.urlopen(request, timeout=90) as response:
        body = response.read()
    path.write_bytes(body)
    try:
        with ZipFile(path) as z:
            if not any(x.endswith("_message_5.csv") for x in z.namelist()):
                raise ValueError("Provider did not return an AAPL level-5 sample")
    except Exception:
        path.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class Config:
    skew_ticks: int = 0
    latency_ms: float = 10.0
    refresh_s: float = 2.0
    cancel_ahead_fraction: float = 0.0
    fee_cents: float = 0.3
    inventory_limit: int = 6

    def validate(self) -> None:
        if self.skew_ticks < 0 or self.inventory_limit < 1:
            raise ValueError("Invalid inventory/skew")
        if not 0 <= self.cancel_ahead_fraction <= 1:
            raise ValueError("Cancellation allocation must be in [0,1]")
        if self.latency_ms < 0 or self.refresh_s <= 0 or self.fee_cents < 0:
            raise ValueError("Invalid fee, latency, or refresh")
        if not all(map(math.isfinite, (self.latency_ms, self.refresh_s, self.fee_cents))):
            raise ValueError("Nonfinite parameter")


@dataclass
class RestingQuote:
    side: int
    price: int
    volume_ahead: float
    live_after: float


class QueueAgent:
    def __init__(self, cfg: Config):
        cfg.validate()
        self.cfg = cfg
        self.bid: RestingQuote | None = None
        self.ask: RestingQuote | None = None
        self.cash_raw = 0
        self.inventory = 0
        self.fills = 0
        self.requotes = 0
        self.cancels = 0
        self.fee_raw = 0.0
        self.max_inventory = 0
        self.integral_inventory = 0.0
        self.last_ts: float | None = None
        self.first_ts: float | None = None
        self.next_refresh = float("-inf")
        self.final_mid: float | None = None
        self.final_bid: int | None = None
        self.final_ask: int | None = None
        self.final_bid_size: int = 0
        self.final_ask_size: int = 0
        self.peak_equity = 0.0
        self.max_drawdown = 0.0
        self.invalid_books = 0

    def place(self, pre: Event, side: int, price: int, now: float) -> RestingQuote | None:
        if side == 1 and self.inventory >= self.cfg.inventory_limit:
            return None
        if side == -1 and self.inventory <= -self.cfg.inventory_limit:
            return None
        displayed = pre.depth_at(side, price)
        if displayed is None:
            return None
        return RestingQuote(side, price, float(displayed),
                            now + self.cfg.latency_ms/1000)

    def refresh(self, pre: Event, now: float) -> None:
        self.cancels += int(self.bid is not None) + int(self.ask is not None)
        bid, ask = pre.bids[0][0], pre.asks[0][0]
        # Retreat only the inventory-increasing quote.
        buy_at = bid - max(0, self.inventory) * self.cfg.skew_ticks * TICK
        sell_at = ask + max(0, -self.inventory) * self.cfg.skew_ticks * TICK
        self.bid = self.place(pre, 1, buy_at, now)
        self.ask = self.place(pre, -1, sell_at, now)
        self.requotes += 1
        self.next_refresh = now + self.cfg.refresh_s

    def on_event(self, event: Event, pre: Event | None) -> None:
        if self.first_ts is None:
            self.first_ts = event.ts
        if self.last_ts is not None:
            self.integral_inventory += max(0, event.ts - self.last_ts) * abs(self.inventory)
        self.last_ts = event.ts
        for attr, side in (("bid", 1), ("ask", -1)):
            quote = getattr(self, attr)
            if quote is None or event.ts < quote.live_after:
                continue
            if event.price != quote.price or event.side != side:
                continue
            if event.kind == 4 and event.size > 0:
                ahead_before = quote.volume_ahead
                quote.volume_ahead = max(0.0, ahead_before - event.size)
                if event.size > ahead_before:
                    if (side == 1 and self.inventory < self.cfg.inventory_limit) or (
                        side == -1 and self.inventory > -self.cfg.inventory_limit
                    ):
                        self.inventory += side
                        self.cash_raw -= side * quote.price
                        self.fills += 1
                        self.fee_raw += self.cfg.fee_cents * TICK
                        self.max_inventory = max(self.max_inventory, abs(self.inventory))
                        setattr(self, attr, None)
            elif event.kind in (2, 3) and event.size > 0:
                quote.volume_ahead = max(
                    0.0, quote.volume_ahead - self.cfg.cancel_ahead_fraction * event.size
                )
        if not event.valid():
            self.invalid_books += 1
            self.bid = None
            self.ask = None
            return
        # Drop a quote when its price is no longer shown in our available
        # depth. We never fabricate queue sizes for an unobserved level.
        for attr, side in (("bid", 1), ("ask", -1)):
            quote = getattr(self, attr)
            if quote is not None and event.depth_at(side, quote.price) is None:
                self.cancels += 1
                setattr(self, attr, None)
        self.final_mid = event.mid()
        self.final_bid, self.final_bid_size = event.bids[0]
        self.final_ask, self.final_ask_size = event.asks[0]
        equity = self.cash_raw + self.inventory * self.final_mid - self.fee_raw
        self.peak_equity = max(self.peak_equity, equity)
        self.max_drawdown = max(self.max_drawdown, self.peak_equity - equity)
        # New quotes are placed only AFTER observing this event's book,
        # never eligible to fill on the event that triggered their creation.
        if event.ts >= self.next_refresh:
            self.refresh(event, event.ts)

    def summary(self, day: str, count: int) -> dict[str, object]:
        if self.final_mid is None or self.first_ts is None or self.last_ts is None:
            raise ValueError("No valid market prices")
        gross = (self.cash_raw + self.inventory * self.final_mid) / SCALE
        # Separate optional one-shot terminal liquidation estimate: use
        # displayed opposite-side best quote, assuming enough displayed size.
        # An illustrative ADDITIONAL 1-cent taker fee/share is applied.
        liquidity_ok = (
            self.inventory == 0
            or (self.inventory > 0 and self.final_bid_size >= self.inventory)
            or (self.inventory < 0 and self.final_ask_size >= -self.inventory)
        )
        liquidation = None
        liquidation_spread_drag = None
        if liquidity_ok:
            if self.inventory > 0:
                exit_price = self.final_bid
            elif self.inventory < 0:
                exit_price = self.final_ask
            else:
                exit_price = self.final_mid
            assert exit_price is not None
            exit_raw = self.cash_raw + self.inventory * exit_price - self.fee_raw
            exit_raw -= abs(self.inventory) * TICK  # assumed 1 cent/share taker fee
            liquidation = round(exit_raw / SCALE, 5)
            liquidation_spread_drag = round(
                abs(self.inventory * (self.final_mid - exit_price)) / SCALE, 5
            )
        return dict(
            day=day,
            policy="fixed" if self.cfg.skew_ticks == 0 else f"aware_{self.cfg.skew_ticks}tick",
            cancel_ahead_fraction=self.cfg.cancel_ahead_fraction,
            latency_ms=self.cfg.latency_ms,
            refresh_seconds=self.cfg.refresh_s,
            market_events=count,
            hypothetical_fills=self.fills,
            gross_pnl_usd=round(gross, 5),
            net_pnl_usd=round(gross - self.fee_raw / SCALE, 5),
            total_fees_usd=round(self.fee_raw / SCALE, 5),
            terminal_liquidation_feasible_at_displayed_top=liquidity_ok,
            terminal_liquidated_net_usd=liquidation,
            terminal_liquidation_spread_drag_usd=liquidation_spread_drag,
            terminal_taker_fee_assumption_cents=1.0,
            ending_inventory=self.inventory,
            max_abs_inventory=self.max_inventory,
            average_abs_inventory=round(
                self.integral_inventory/max(1.0, self.last_ts-self.first_ts), 5
            ),
            peak_to_trough_drawdown_usd=round(self.max_drawdown / SCALE, 5),
            quote_refreshes=self.requotes,
            quote_cancellations=self.cancels,
            invalid_book_events=self.invalid_books,
        )


def run_day(path: Path, configurations: list[Config], depth: int = 5, day_override: str | None = None) -> list[dict[str, object]]:
    if not configurations:
        raise ValueError("No strategies specified")
    date_match = re.search(r"(20\d\d-\d\d-\d\d)", str(path))
    day = day_override or (date_match.group(1) if date_match else path.stem)
    agents = [QueueAgent(cfg) for cfg in configurations]
    previous: Event | None = None
    count = 0
    for event in stream_zip(path, depth=depth):
        count += 1
        for agent in agents:
            agent.on_event(event, previous)
        previous = event
    if count < 2:
        raise ValueError(f"Insufficient events in {path}")
    return [agent.summary(day, count) for agent in agents]


def save_rows(file: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError("No results")
    file.parent.mkdir(parents=True, exist_ok=True)
    with file.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", type=Path, default=Path("data") / SAMPLE)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("results/queue_replay"))
    args = parser.parse_args()
    if args.download:
        download_sample(args.zip)
    settings = [Config(skew_ticks=skew, cancel_ahead_fraction=f)
                for f in (0.0, 0.5, 1.0) for skew in (0, 1)]
    results = run_day(args.zip, settings, depth=5)
    save_rows(args.output / "queue_sensitivity.csv", results)
    (args.output / "run_info.json").write_text(json.dumps({
        "source": DATA_URL, "historical_days": 1, "depth_levels": 5,
        "event_count": results[0]["market_events"],
        "all_order_fills_hypothetical": True,
        "queue_ahead_proxy": "entire displayed depth at posting",
        "vendor_raw_data_distributed": False
    }, indent=2) + "\n")
    for row in results:
        print(f"cancel={row['cancel_ahead_fraction']:.1f} {row['policy']:<12} "
              f"fills={row['hypothetical_fills']:>5} net_USD={row['net_pnl_usd']:+.3f} "
              f"peak_inventory={row['max_abs_inventory']}")
    print(f"Saved: {args.output.resolve()}")


if __name__ == "__main__":
    main()
