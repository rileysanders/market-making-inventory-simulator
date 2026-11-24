"""Stream NASDAQ TotalView-ITCH 5.0 and rebuild one AAPL order book.

Original public sample dates 2019-01-30 ... 2020-01-30.
ITCH documentation: https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification_5.0.pdf

This is an independent *AAPL-only* L3 book reconstructor. It ignores off-book
trades and does not reconstruct a consolidated multi-venue NBBO. We do not
redistribute raw exchange data. Intended for research/validation only.
"""
from __future__ import annotations

import bisect
import gzip
import io
import math
import struct
import urllib.request
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from queue_replay import Event

PUBLIC_DATES = ("01302019", "03272019", "07302019", "08302019",
                "10302019", "12302019", "01302020")
NS = 1_000_000_000
OPEN_NS = 9 * 3600 * NS + 30 * 60 * NS
CLOSE_NS = 16 * 3600 * NS
ALLOWED_TYPES = {ord(x) for x in "AFECXDU"}
TARGET = b"AAPL    "
EXPECTED_LEN = {ord("A"): 36, ord("F"): 40, ord("E"): 31,
                ord("C"): 36, ord("X"): 23, ord("D"): 19, ord("U"): 35}


def public_url(date: str) -> str:
    if date not in PUBLIC_DATES:
        raise ValueError(f"Date must be a documented Nasdaq public sample: {PUBLIC_DATES}")
    return "https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/" + date + ".NASDAQ_ITCH50.gz"


def frames(stream: BinaryIO, chunk_size: int = 1 << 22) -> Iterator[bytes]:
    """Read ITCH's 2-byte big-endian length prefix, including chunk boundaries."""
    carry = b""
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            if carry:
                raise ValueError("Incomplete ITCH message at EOF")
            break
        data = carry + chunk
        pos, limit = 0, len(data)
        while pos + 2 <= limit:
            msg_len = struct.unpack_from(">H", data, pos)[0]
            if msg_len == 0:
                raise ValueError("Unexpected zero-length binary ITCH message")
            end = pos + 2 + msg_len
            if end > limit:
                break
            yield data[pos + 2:end]
            pos = end
        carry = data[pos:]


class PriceBook:
    """Market-by-order IDs with aggregate displayed quantity per price/side."""
    def __init__(self):
        self.orders: dict[int, tuple[int, int, int]] = {}
        self.levels: dict[int, dict[int, int]] = {1: {}, -1: {}}
        self.prices: dict[int, list[int]] = {1: [], -1: []}
        self.event_counts: Counter = Counter()
        self.total_executed = 0
        self.total_cancelled = 0

    def modify_level(self, side: int, price: int, delta: int):
        levels = self.levels[side]
        prices = self.prices[side]
        old = levels.get(price, 0)
        new = old + delta
        if new < 0:
            raise ValueError(f"Negative book quantity at {side}/{price}: {old} + {delta}")
        if old == 0 and new:
            bisect.insort(prices, price)
        if new == 0:
            if old:
                idx = bisect.bisect_left(prices, price)
                if idx >= len(prices) or prices[idx] != price:
                    raise AssertionError("Price index out of sync")
                prices.pop(idx)
            levels.pop(price, None)
        else:
            levels[price] = new

    def add(self, ref: int, side: int, shares: int, price: int):
        if ref in self.orders or shares <= 0 or price <= 0 or side not in (1, -1):
            raise ValueError(f"Invalid or duplicate add order: ref={ref}")
        self.orders[ref] = (side, shares, price)
        self.modify_level(side, price, shares)
        self.event_counts["adds"] += 1

    def deduct(self, ref: int, shares: int):
        if ref not in self.orders:
            raise ValueError(f"Orphaned order modification: {ref}")
        side, remaining, price = self.orders[ref]
        if shares <= 0 or shares > remaining:
            raise ValueError(f"Invalid executed/cancelled shares for {ref}: {shares}/{remaining}")
        if shares == remaining:
            del self.orders[ref]
        else:
            self.orders[ref] = (side, remaining - shares, price)
        self.modify_level(side, price, -shares)
        return side, price, shares

    def delete(self, ref: int):
        if ref not in self.orders:
            raise ValueError(f"Orphaned order deletion: {ref}")
        side, shares, price = self.orders.pop(ref)
        self.modify_level(side, price, -shares)
        self.event_counts["deletes"] += 1
        return side, price, shares

    def top(self, depth: int = 5):
        bp = reversed(self.prices[1][-depth:])
        ap = self.prices[-1][:depth]
        bids = tuple((p, self.levels[1][p]) for p in bp)
        asks = tuple((p, self.levels[-1][p]) for p in ap)
        return asks, bids

    def process(self, msg: bytes, depth: int = 5) -> Event:
        typ = msg[0]
        if typ not in ALLOWED_TYPES:
            raise ValueError("Non-order ITCH message passed to book")
        if len(msg) != EXPECTED_LEN[typ]:
            raise ValueError(f"Unexpected ITCH message size: {chr(typ)} {len(msg)}")
        ts = int.from_bytes(msg[5:11], "big") / NS
        ref = struct.unpack_from(">Q", msg, 11)[0]
        side = 0
        price = 0
        size = 0
        kind = 0
        if typ in (ord("A"), ord("F")):
            side = 1 if msg[19] == ord("B") else -1
            if msg[19] not in (ord("B"), ord("S")):
                raise ValueError("Invalid A/F buy/sell indicator")
            size = struct.unpack_from(">I", msg, 20)[0]
            price = struct.unpack_from(">I", msg, 32)[0]
            self.add(ref, side, size, price)
            kind = 1
        elif typ in (ord("E"), ord("C"), ord("X")):
            size = struct.unpack_from(">I", msg, 19)[0]
            side, price, size = self.deduct(ref, size)
            kind = 4 if typ in (ord("E"), ord("C")) else 2
            if kind == 4:
                self.total_executed += size
                # A C execution may print at a different price. The
                # referenced RESTING order price determines queue depletion.
                if typ == ord("C"):
                    self.event_counts["different_print_price_executions"] += 1
            else:
                self.total_cancelled += size
        elif typ == ord("D"):
            side, price, size = self.delete(ref)
            kind = 3
            self.total_cancelled += size
        elif typ == ord("U"):
            # Replace is atomic: remove old ref, add new ref; represent
            # old queue cancellation only, not an executable trade.
            new_ref = struct.unpack_from(">Q", msg, 19)[0]
            new_shares, new_price = struct.unpack_from(">II", msg, 27)
            side, price, size = self.delete(ref)
            self.add(new_ref, side, new_shares, new_price)
            kind = 3
            self.total_cancelled += size
            self.event_counts["replaces"] += 1
        self.event_counts[chr(typ)] += 1
        asks, bids = self.top(depth)
        return Event(ts, kind, ref, size, price, side, asks, bids)


@dataclass
class ReconstructionStats:
    date: str
    all_messages: int = 0
    aapl_book_events: int = 0
    regular_session_events: int = 0
    stock_locate: int = 0
    last_ts_ns: int = 0


def replay_aapl_itch(
    gz_stream: BinaryIO, date: str, depth: int = 5,
    stats: ReconstructionStats | None = None,
) -> Iterator[Event]:
    """Market data messages are chronological; emit one post-event AAPL book event.

    Reconstruct premarket AAPL orders but expose only regular-hours events.
    Unknown-symbol messages are skipped by stock-locate ID.
    """
    if stats is None:
        stats = ReconstructionStats(date)
    book = PriceBook()
    locator = None
    last_ts = -1
    with gzip.GzipFile(fileobj=gz_stream, mode="rb") as stream:
        for body in frames(stream):
            stats.all_messages += 1
            typ = body[0]
            locate = struct.unpack_from(">H", body, 1)[0]
            if typ == ord("R") and body[11:19] == TARGET:
                locator = locate
                stats.stock_locate = locate
            if locate != locator or locator is None:
                continue
            ts = int.from_bytes(body[5:11], "big")
            if ts < last_ts:
                raise ValueError("AAPL event timestamps are not monotonic")
            last_ts = ts
            stats.last_ts_ns = ts
            if typ == ord("H") and body[19:20] == b"H" and OPEN_NS <= ts < CLOSE_NS:
                raise ValueError("AAPL trading halt found: stop and handle explicitly")
            if typ not in ALLOWED_TYPES:
                continue
            event = book.process(body, depth=depth)
            stats.aapl_book_events += 1
            if OPEN_NS <= ts < CLOSE_NS:
                stats.regular_session_events += 1
                yield event
    if locator is None or stats.regular_session_events < 2:
        raise ValueError(f"Missing AAPL locate or insufficient market events for {date}")


def download_stream(date: str, timeout: float = 60.0):
    request = urllib.request.Request(
        public_url(date),
        headers={"User-Agent": "UniversityMarketMicrostructureResearch/1.0"},
    )
    return urllib.request.urlopen(request, timeout=timeout)
