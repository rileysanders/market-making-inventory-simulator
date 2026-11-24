"""Tests for raw Nasdaq ITCH AAPL reconstruction on small synthetic messages.

No historical-data performance claims result from these fixtures.
"""
import gzip
import io
import random
import struct
import unittest
from nasdaq_itch import PriceBook, ReconstructionStats, frames, replay_aapl_itch
from nasdaq_day_replay import run_feed
from queue_replay import Config

NS = 1_000_000_000


def header(t, ns, locator=13):
    return t.encode() + struct.pack(">HH", locator, 0) + ns.to_bytes(6, "big")


def record(type, ts, contents=b"", locator=13):
    return header(type, int(ts * NS), locator) + contents


def frame(body):
    return struct.pack(">H", len(body)) + body


def directory(ts=8*3600, locate=13):
    return record("R", ts, b"AAPL    " + b"\x00"*20, locate)


def add(ts, ref, qty, price, side="B", kind="A"):
    value=struct.pack(">QcI8sI", ref, side.encode(), qty, b"AAPL    ", price)
    if kind=="F":
        value+=b"XXXX"
    return record(kind, ts, value)


def execute(ts, ref, qty, kind="E", actual_price=0):
    value=struct.pack(">QI Q", ref, qty, 1)
    if kind=="C":
        value += b"Y" + struct.pack(">I", actual_price)
    return record(kind, ts, value)


def cancel(ts, ref, qty):
    return record("X", ts, struct.pack(">QI", ref, qty))


def delete(ts, ref):
    return record("D", ts, struct.pack(">Q", ref))


def replace(ts, old, new, qty, price):
    return record("U", ts, struct.pack(">QQII", old, new, qty, price))


def stream(*msgs):
    return io.BytesIO(gzip.compress(b"".join(map(frame, msgs))))


class NativeItchTests(unittest.TestCase):
    def test_binary_chunk_framing(self):
        msgs=[directory(),add(9*3600, 1, 5, 1_000_000),
              add(9*3600, 2, 5, 1_000_200, "S", "F")]
        raw=b"".join(map(frame,msgs))
        self.assertEqual(list(frames(io.BytesIO(raw), chunk_size=7)),msgs)
        with self.assertRaisesRegex(ValueError, "Incomplete"):
            list(frames(io.BytesIO(raw[:-1]), chunk_size=4))

    def test_book_deducts_only_original_resting_price(self):
        book=PriceBook()
        book.process(add(9*3600,1,10,1_000_000))
        book.process(add(9*3600,2,6,1_000_200,"S"))
        event=book.process(execute(9*3600+1,1,5,"C",999_900))
        self.assertEqual((event.kind,event.price,event.size,event.side),
                         (4,1_000_000,5,1))
        self.assertEqual(event.bids[0],(1_000_000,5))
        self.assertEqual(book.orders[1],(1,5,1_000_000))

    def test_replace_is_atomic_and_loses_queue(self):
        book=PriceBook()
        book.process(add(9*3600,1,10,1_000_000))
        book.process(add(9*3600,2,10,1_000_200,"S"))
        event=book.process(replace(9*3600+1,1,3,4,999_900))
        self.assertEqual(event.kind,3)
        self.assertEqual(book.orders[3],(1,4,999_900))
        self.assertEqual(event.bids[0],(999_900,4))
        self.assertNotIn(1,book.orders)

    def test_orphaned_events_rejected(self):
        with self.assertRaisesRegex(ValueError,"Orphaned"):
            PriceBook().process(cancel(34200,7,1))

    def test_randomized_order_book_conservation(self):
        # Independent aggregate recomputation checks an invariant after
        # randomized real ITCH-type operations on synthetic order messages.
        rng = random.Random(20261124)
        book = PriceBook()
        live = {}
        next_ref = 1
        ts = 34200
        for _ in range(500):
            ts += 1
            if not live or rng.random() < 0.52:
                ref = next_ref
                next_ref += 1
                side = rng.choice(["B", "S"])
                price = rng.choice([999_800, 999_900, 1_000_000] if side == "B"
                                   else [1_000_100, 1_000_200, 1_000_300])
                qty = rng.randint(1, 200)
                book.process(add(ts, ref, qty, price, side))
                live[ref] = (1 if side == "B" else -1, qty, price)
            else:
                ref = rng.choice(list(live))
                side, qty, price = live[ref]
                choice = rng.choice(["cancel", "exec", "delete", "replace"])
                if choice == "delete":
                    book.process(delete(ts, ref))
                    del live[ref]
                elif choice == "replace":
                    new_ref = next_ref
                    next_ref += 1
                    size = rng.randint(1, 200)
                    new_price = price + rng.choice((-100, 0, 100))
                    book.process(replace(ts, ref, new_ref, size, new_price))
                    del live[ref]
                    live[new_ref] = (side, size, new_price)
                else:
                    removed = rng.randint(1, qty)
                    book.process(cancel(ts, ref, removed) if choice == "cancel"
                                 else execute(ts, ref, removed))
                    if removed == qty:
                        del live[ref]
                    else:
                        live[ref] = (side, qty-removed, price)
            expected = {1: {}, -1: {}}
            for side, quantity, price in live.values():
                expected[side][price] = expected[side].get(price, 0) + quantity
            self.assertEqual(book.orders, live)
            self.assertEqual(book.levels, expected)
            for side in (1, -1):
                self.assertEqual(book.prices[side], sorted(expected[side]))
            asks, bids = book.top()
            self.assertEqual(bids, tuple(
                (p, expected[1][p]) for p in sorted(expected[1], reverse=True)[:5]
            ))
            self.assertEqual(asks, tuple(
                (p, expected[-1][p]) for p in sorted(expected[-1])[:5]
            ))

    def test_reconstruction_preserves_premarket_and_excludes_after_hours(self):
        msgs=[
            directory(),
            add(9*3600,1,10,1_000_000),
            add(9*3600,2,10,1_000_200,"S"),
            cancel(9*3600+5,1,2),
            execute(34201,1,3),
            execute(34202,2,4),
            delete(57601,1),
        ]
        stats=ReconstructionStats("01302019")
        result=list(replay_aapl_itch(stream(*msgs),"01302019",stats=stats))
        self.assertEqual(len(result),2)
        self.assertEqual(stats.regular_session_events,2)
        self.assertEqual(result[0].bids[0],(1_000_000,5))
        self.assertEqual(result[1].asks[0],(1_000_200,6))

    def test_research_pipeline_end_to_end_on_fixture_only(self):
        msgs=[
            directory(),
            add(9*3600,1,20,1_000_000),
            add(9*3600,2,20,1_000_200,"S"),
            execute(34201,1,10),
            execute(34203,2,10),
            execute(34205,1,10),
            execute(34207,2,10),
        ]
        rows,stats=run_feed(stream(*msgs),"01302019",
                           [Config(latency_ms=0,refresh_s=20,
                                   cancel_ahead_fraction=0,fee_cents=0)])
        self.assertEqual(stats.regular_session_events,4)
        self.assertEqual(rows[0]["market_events"],4)
        self.assertEqual(rows[0]["day"],"2019-01-30")


if __name__=="__main__":
    unittest.main()
