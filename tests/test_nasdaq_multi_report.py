import csv
import json
import tempfile
import unittest
from pathlib import Path

from nasdaq_multiday_report import load_days, summarise, write


def fixture(folder: Path, day: str, aapl_events=100):
    day_dir = folder / day
    day_dir.mkdir(parents=True)
    dt = day[5:7] + day[8:10] + day[:4]
    (day_dir / "provenance.json").write_text(json.dumps({
        "date": dt,
        "symbol": "AAPL",
        "exchange": "Nasdaq",
        "regular_session_aapl_book_events": aapl_events,
        "market_data_are_historical": True,
        "strategy_order_fills_are_hypothetical": True
    }))
    with (day_dir/"policy_results.csv").open("w",newline="") as f:
        fields=["day","cancel_ahead_fraction","policy",
                "terminal_liquidated_net_usd","average_abs_inventory"]
        writer=csv.DictWriter(f, fields)
        writer.writeheader()
        for cancel in (0,.5,1):
            for policy in ("fixed","aware_1tick"):
                writer.writerow(dict(
                    day=day,cancel_ahead_fraction=cancel,policy=policy,
                    terminal_liquidated_net_usd=(10 if policy=="fixed" else 8),
                    average_abs_inventory=(4 if policy=="fixed" else 1)
                ))


class NativeMultiDayReports(unittest.TestCase):
    def test_genuine_distinct_day_reporting_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"daily";root.mkdir()
            for d in range(1,8):
                fixture(root, f"2019-01-{d:02d}")
            output=Path(temp)/"report"
            result=write(root,output)
            self.assertEqual(result["number_of_distinct_days"],7)
            self.assertEqual(len(result["results"]),6)
            self.assertEqual(result["results"][0]["aware_minus_fixed_mean_usd"],-2)
            self.assertEqual(result["results"][3]["distinct_days"],2)
            self.assertTrue((output/"multi_day_table.csv").exists())
            self.assertTrue((output/"multi_day_summary.json").exists())

    def test_duplicate_date_rejected_even_for_distinct_filenames(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fixture(root,"2019-01-01")
            duplicated=root/"different_archive"
            duplicated.mkdir()
            for filename in ("provenance.json","policy_results.csv"):
                (duplicated/filename).write_bytes((root/"2019-01-01"/filename).read_bytes())
            with self.assertRaisesRegex(ValueError,"Duplicate"):
                load_days(root)

    def test_not_confuse_one_day_with_multi_day(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fixture(root,"2019-01-01")
            with self.assertRaisesRegex(ValueError,"three distinct"):
                summarise(load_days(root))

    def test_mixed_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            fixture(root,"2019-01-01")
            p=root/"2019-01-01"/"provenance.json"
            data=json.loads(p.read_text())
            data["symbol"]="MSFT"
            p.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError,"Mixed|Unverified|mixed"):
                load_days(root)


if __name__=="__main__":
    unittest.main()
