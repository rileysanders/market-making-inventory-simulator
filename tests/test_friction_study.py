import tempfile
import unittest
from pathlib import Path

from friction_study import FrictionSettings, experiment, grid, write_results
from sensitivity import compare_policies
from simulate import Settings


class FrictionStudyTests(unittest.TestCase):
    def test_zero_frictions_reproduces_original_simulation(self):
        original = compare_policies(Settings(trials=25, steps=40, seed=555,
                                            price_shock_sd_cents=15))
        updated = experiment(FrictionSettings(trials=25, steps=40, seed=555,
                                               adverse_move_cents=0,
                                               fee_cents_per_trade=0))
        self.assertEqual(updated['fixed_mean_net_pnl'], original['fixed_mean_pnl'])
        self.assertEqual(updated['aware_mean_net_pnl'], original['aware_mean_pnl'])
        self.assertEqual(updated['paired_mean_delta'], original['paired_mean_delta'])

    def test_fees_reduce_pnl_by_number_of_fills(self):
        base = FrictionSettings(trials=20, steps=40, seed=88)
        clean = experiment(base)
        paid = experiment(FrictionSettings(trials=20, steps=40, seed=88,
                                            fee_cents_per_trade=4))
        self.assertAlmostEqual(clean['fixed_mean_net_pnl'] - paid['fixed_mean_net_pnl'],
                               clean['fixed_mean_trades'] * 0.04, places=3)
        self.assertAlmostEqual(clean['aware_mean_net_pnl'] - paid['aware_mean_net_pnl'],
                               clean['aware_mean_trades'] * 0.04, places=3)
        self.assertEqual(clean['fixed_mean_trades'], paid['fixed_mean_trades'])

    def test_zero_skew_produces_identical_policies_under_toxic_flow(self):
        result = experiment(FrictionSettings(trials=20, steps=50,
                                              inventory_skew_cents=0.0,
                                              adverse_move_cents=10,
                                              fee_cents_per_trade=4))
        self.assertEqual(result['fixed_mean_net_pnl'], result['aware_mean_net_pnl'])
        self.assertEqual(result['paired_mean_delta'], 0.0)

    def test_invalid_settings_rejected(self):
        for bad in [FrictionSettings(toxic_signal_probability=1.1),
                    FrictionSettings(fee_cents_per_trade=-0.5),
                    FrictionSettings(adverse_move_cents=-1),
                    FrictionSettings(inventory_skew_cents=2)]:
            with self.assertRaises(ValueError):
                experiment(bad)

    def test_same_seed_same_results_and_csv_written(self):
        settings = FrictionSettings(trials=10, steps=25, seed=777)
        a = grid(settings, [0, 4], [0, 10])
        b = grid(settings, [0, 4], [0, 10])
        self.assertEqual(a, b)
        self.assertEqual(len(a), 4)
        with tempfile.TemporaryDirectory() as path:
            write_results(a, Path(path))
            self.assertIn('paired_ci95_low', (Path(path)/'friction_grid.csv').read_text())


if __name__ == '__main__':
    unittest.main()
