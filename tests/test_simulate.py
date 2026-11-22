import unittest

from simulate import Settings, experiment, simulate_path


class SimulatorChecks(unittest.TestCase):
    def test_cash_inventory_and_marking_after_one_fill(self):
        settings = Settings(initial_mid_cents=10_000.0, spread_cents=20.0)
        result = simulate_path([(0.0, 0.0, 1.0)], settings, 0.0)
        self.assertEqual(result.terminal_inventory, 1)
        self.assertEqual(result.trades, 1)
        self.assertAlmostEqual(result.pnl_dollars, 0.10)

    def test_inventory_limit_is_enforced(self):
        settings = Settings(inventory_limit=2, initial_mid_cents=10_000.0)
        result = simulate_path([(0.0, 0.0, 1.0)] * 10, settings, 0.0)
        self.assertEqual(result.max_abs_inventory, 2)
        self.assertEqual(result.terminal_inventory, 2)
        self.assertEqual(result.trades, 2)

    def test_fixed_seed_reproduces_results(self):
        settings = Settings(trials=20, steps=30, seed=123)
        first, first_summary = experiment(settings)
        second, second_summary = experiment(settings)
        self.assertEqual(first, second)
        self.assertEqual(first_summary, second_summary)


if __name__ == "__main__":
    unittest.main()
