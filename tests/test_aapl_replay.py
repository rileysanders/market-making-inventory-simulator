import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from aapl_replay import (
    Event, load_pairs, measure_real_markouts, print_crosses_order,
    proposed_quotes, read_zip, replay, run, save,
)


class AaplReplayTests(unittest.TestCase):
    def fixture(self):
        # LOBSTER prices = dollars x 10000: $100 bid, $100.02 ask.
        return [
            Event(34200, 1, 1, 1_000_000, 1, 1_000_200, 100, 1_000_000, 100),
            Event(34201, 4, 1, 1_000_000, 1, 1_000_200, 100, 999_900, 100),
            Event(34202, 4, 1, 1_000_200, -1, 1_000_300, 100, 1_000_000, 100),
            Event(34203, 1, 1, 1_000_000, 1, 1_000_300, 100, 1_000_000, 100),
            Event(34207, 1, 1, 1_000_000, 1, 1_000_300, 100, 1_000_000, 100),
        ]

    def test_no_future_book_lookahead(self):
        rows = self.fixture()
        # Buy print is at previous bid ($100). Post-event bid is $99.99.
        result = replay(rows, "touch", False, fee_cents=0)
        self.assertEqual(result["executed_shares"], 2)
        self.assertAlmostEqual(result["gross_pnl_usd"], 0.02)

    def test_touch_vs_trade_through(self):
        rows = self.fixture()
        self.assertEqual(replay(rows, "touch", False)["executed_shares"], 2)
        self.assertEqual(replay(rows, "through", False)["executed_shares"], 0)

    def test_fees_subtracted_from_each_fill(self):
        clean = replay(self.fixture(), "touch", False, fee_cents=0)
        paid = replay(self.fixture(), "touch", False, fee_cents=1)
        self.assertAlmostEqual(clean["net_pnl_usd"] - paid["net_pnl_usd"], .02)

    def test_skew_retreats_on_risky_side(self):
        pre = self.fixture()[0]
        self.assertEqual(proposed_quotes(pre, 2, True), (999_800, 1_000_200))
        self.assertEqual(proposed_quotes(pre, -2, True), (1_000_000, 1_000_400))
        self.assertEqual(proposed_quotes(pre, 2, False), (1_000_000, 1_000_200))

    def test_execution_direction_and_kind(self):
        event = self.fixture()[1]
        self.assertEqual(print_crosses_order(event, 1_000_000, 1_000_200, "touch"), 1)
        self.assertEqual(print_crosses_order(event, 1_000_000, 1_000_200, "through"), 0)
        self.assertEqual(print_crosses_order(self.fixture()[3], 1_000_000, 1_000_200, "touch"), 0)

    def test_historical_markout_sign_and_horizon(self):
        result = measure_real_markouts(self.fixture(), 1)
        self.assertEqual(result["observed_visible_executions"], 2)
        self.assertEqual(result["observed_executed_shares"], 2)
        # Buy at $100 -> future mid $100.015; sell at $100.02 -> future mid $100.015.
        self.assertAlmostEqual(result["passive_execution_price_markout_usd_per_share"], .01)

    def test_reject_mismatched_files(self):
        messages = io.StringIO("34200,1,1,1,1000000,1\n34201,4,2,1,1000000,1\n")
        books = io.StringIO("1000200,10,1000000,20\n")
        with self.assertRaisesRegex(ValueError, "differ"):
            load_pairs(messages, books)

    def test_zip_parser_and_csv_export(self):
        rows = self.fixture()
        messages = "\n".join(
            f"{r.timestamp},{r.kind},10,{r.size},{r.trade_price},{r.direction}"
            for r in rows
        ) + "\n"
        books = "\n".join(
            f"{r.ask},{r.ask_size},{r.bid},{r.bid_size}" for r in rows
        ) + "\n"
        with tempfile.TemporaryDirectory() as temp:
            archive_path = Path(temp) / "sample.zip"
            with ZipFile(archive_path, "w") as archive:
                archive.writestr("AAPL_message_1.csv", messages)
                archive.writestr("AAPL_orderbook_1.csv", books)
            parsed = read_zip(archive_path)
            self.assertEqual(parsed, rows)
            policies, markouts = run(parsed)
            save(Path(temp) / "results", parsed, policies, markouts, 0.3)
            self.assertTrue((Path(temp) / "results" / "policy_replay.csv").exists())
            self.assertTrue((Path(temp) / "results" / "observed_markouts.csv").exists())


if __name__ == "__main__":
    unittest.main()
