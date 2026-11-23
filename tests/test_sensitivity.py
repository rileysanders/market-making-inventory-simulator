import tempfile
import unittest
from pathlib import Path

from simulate import Settings
from sensitivity import compare_policies, save_results, sweep


class SensitivityTests(unittest.TestCase):
    def test_no_skew_matches_fixed_policy(self):
        result = compare_policies(Settings(trials=25, steps=60, inventory_skew_cents=0.0))
        self.assertEqual(result["paired_mean_delta"], 0.0)
        self.assertEqual(result["paired_ci95_low"], 0.0)
        self.assertEqual(result["paired_ci95_high"], 0.0)
        self.assertEqual(result["fixed_mean_pnl"], result["aware_mean_pnl"])

    def test_sweep_is_reproducible(self):
        settings = Settings(trials=12, steps=30)
        first = sweep(settings, [5.0, 15.0], [0.0, 1.0])
        second = sweep(settings, [5.0, 15.0], [0.0, 1.0])
        self.assertEqual(first, second)

    def test_avoids_mid_crossing_assumption(self):
        with self.assertRaisesRegex(ValueError, "crossing"):
            sweep(Settings(trials=4, steps=4), [5.0], [2.0])

    def test_writes_csv(self):
        rows = sweep(Settings(trials=4, steps=4), [5.0], [0.0])
        with tempfile.TemporaryDirectory() as temp:
            save_results(rows, Path(temp))
            self.assertIn("paired_ci95_low", (Path(temp) / "sensitivity.csv").read_text())


if __name__ == "__main__":
    unittest.main()
