import csv
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from zipfile import ZipFile

from multi_day_research import analyse, discover_days, partition_days
from queue_replay import Config, Event, QueueAgent, run_day, stream_zip


def event(ts, kind=1, size=0, price=1_000_000, side=1,
          bid=1_000_000, ask=1_000_200, bid_qty=3, ask_qty=3):
    return Event(
        ts=ts, kind=kind, order_id=int(ts * 1000) + 1,
        size=size, price=price, side=side,
        bids=((bid, bid_qty),) * 5,
        asks=((ask, ask_qty),) * 5,
    )


def make_zip(path, date, depth=5):
    rows = [
        event(34200),
        event(34200.02, 4, 2, 1_000_000, 1, bid_qty=1),
        event(34200.03, 4, 2, 1_000_000, 1, bid_qty=1),
    ]
    stem = f"AAPL_{date}_34200000_57600000"
    with ZipFile(path, "w") as z:
        m = "\n".join(f"{e.ts},{e.kind},{e.order_id},{e.size},{e.price},{e.side}" for e in rows) + "\n"
        def book_line(e):
            parts = []
            for _ in range(depth):
                parts.extend((e.asks[0][0], e.asks[0][1], e.bids[0][0], e.bids[0][1]))
            return ",".join(map(str, parts))
        b = "\n".join(book_line(e) for e in rows) + "\n"
        z.writestr(f"{stem}_message_{depth}.csv", m)
        z.writestr(f"{stem}_orderbook_{depth}.csv", b)


class QueueModelTests(unittest.TestCase):
    def test_queues_only_fill_after_consuming_existing_depth(self):
        agent = QueueAgent(Config(latency_ms=0, refresh_s=10, fee_cents=0))
        rows = [
            event(0), event(.02, 4, 2, 1_000_000, 1, bid_qty=1),
            event(.03, 4, 2, 1_000_000, 1, bid_qty=1),
        ]
        for i, e in enumerate(rows):
            agent.on_event(e, rows[i-1] if i else None)
        self.assertEqual(agent.fills, 1)
        self.assertEqual(agent.inventory, 1)
        self.assertEqual(agent.cash_raw, -1_000_000)

    def test_quotes_never_fill_on_their_placement_event(self):
        agent = QueueAgent(Config(latency_ms=0, refresh_s=10))
        first = event(0, kind=4, size=500, price=1_000_000, side=1)
        agent.on_event(first, None)
        self.assertEqual(agent.fills, 0)
        self.assertIsNotNone(agent.bid)
        self.assertEqual(agent.bid.volume_ahead, 3)

    def test_latency_blocks_fill(self):
        agent = QueueAgent(Config(latency_ms=50, refresh_s=10))
        events = [
            event(0),
            event(.01, 4, 100, 1_000_000, 1),
            event(.07, 4, 100, 1_000_000, 1),
        ]
        for i, e in enumerate(events):
            agent.on_event(e, events[i-1] if i else None)
        self.assertEqual(agent.fills, 1)

    def test_cancellation_allocation_is_a_sensitivity_not_a_fact(self):
        rows = [
            event(0, bid_qty=100),
            event(.02, 2, 60, 1_000_000, 1, bid_qty=40),
            event(.03, 4, 71, 1_000_000, 1, bid_qty=1),
        ]
        low = QueueAgent(Config(latency_ms=0, refresh_s=10, cancel_ahead_fraction=0))
        high = QueueAgent(Config(latency_ms=0, refresh_s=10, cancel_ahead_fraction=.5))
        for i, e in enumerate(rows):
            low.on_event(e, rows[i-1] if i else None)
            high.on_event(e, rows[i-1] if i else None)
        self.assertEqual(low.fills, 0)
        self.assertEqual(high.fills, 1)

    def test_accounting_fee_and_final_mark(self):
        agent = QueueAgent(Config(latency_ms=0, refresh_s=10, fee_cents=1))
        rows = [event(0), event(.02, 4, 5, 1_000_000, 1)]
        for i, e in enumerate(rows):
            agent.on_event(e, rows[i-1] if i else None)
        outcome = agent.summary("2012-06-21", len(rows))
        self.assertEqual(outcome["hypothetical_fills"], 1)
        self.assertAlmostEqual(outcome["gross_pnl_usd"], .01)
        self.assertAlmostEqual(outcome["net_pnl_usd"], 0.0)

    def test_terminal_liquidation_uses_bid_and_exit_fee(self):
        agent = QueueAgent(Config(latency_ms=0, refresh_s=10, fee_cents=1))
        rows = [event(0), event(.02, 4, 5, 1_000_000, 1)]
        for i, e in enumerate(rows):
            agent.on_event(e, rows[i-1] if i else None)
        outcome = agent.summary("2012-06-21", len(rows))
        self.assertTrue(outcome["terminal_liquidation_feasible_at_displayed_top"])
        self.assertAlmostEqual(outcome["net_pnl_usd"], 0.0)
        self.assertAlmostEqual(outcome["terminal_liquidated_net_usd"], -.02)
        self.assertAlmostEqual(outcome["terminal_liquidation_spread_drag_usd"], .01)

    def test_lobster_post_event_alignment_and_csv_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / "sample.zip"
            make_zip(file, "2012-06-21")
            loaded = list(stream_zip(file))
            self.assertEqual(len(loaded), 3)
            self.assertEqual(loaded[0].bids[0][0], 1_000_000)
            results = run_day(file, [Config(latency_ms=0, refresh_s=10, fee_cents=0)])
            self.assertEqual(results[0]["hypothetical_fills"], 1)

    def test_duplicate_days_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for x in ("first.zip", "second.zip"):
                make_zip(Path(temp) / x, "2012-06-21")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                discover_days(Path(temp))

    def test_chronology_and_minimum_day_count(self):
        dates = [f"2026-10-{i:02d}" for i in range(1, 13)]
        split = partition_days(dates)
        self.assertEqual([len(split[k]) for k in ("development","validation","holdout_test")], [7,2,3])
        self.assertTrue(max(split["validation"]) < min(split["holdout_test"]))
        with self.assertRaisesRegex(ValueError, "ONE day"):
            partition_days(["2012-06-21"])

    def test_selection_locked_to_validation_not_holdout(self):
        split = dict(development=["d1","d2"], validation=["v1","v2"],
                     holdout_test=["t1","t2"])
        rows = []
        for day in sum(split.values(), []):
            for name, pnl in [
                ("fixed", 0),
                ("aware_1tick", 3 if day[0]=="t" else 1),
                ("aware_2tick", -10 if day[0]=="t" else 2),
            ]:
                rows.append(dict(day=day, policy=name, latency_ms=10.0,
                                 cancel_ahead_fraction=0.0, net_pnl_usd=pnl))
        result = analyse(rows, split)
        self.assertEqual(result["locked_selected_policy"], "aware_2tick")
        self.assertEqual(result["holdout_robustness"][0]["paired_mean_delta_usd"], -10)


if __name__ == "__main__":
    unittest.main()
