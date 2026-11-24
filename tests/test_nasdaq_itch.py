"""Tests for raw Nasdaq ITCH AAPL reconstruction on small synthetic messages.

No historical-data performance claims result from these fixtures.
"""
import gzip
import io
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
