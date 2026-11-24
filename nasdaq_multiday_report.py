"""Aggregate different AAPL Nasdaq ITCH days with provenance checks.

All candidate order fills are hypothetical. One market message is not one
independent observation; daily performance is the appropriate analysis unit.
"""
from __future__ import annotations
import argparse
import csv
import json
import math
import statistics
from datetime import datetime
from pathlib import Path

CANCELLATIONS = (0.0, 0.5, 1.0)
POLICIES = ("fixed", "aware_1tick")


def load_days(folder: Path) -> list[dict]:
    seen, days = set(), []
    for path in sorted(folder.glob("*/policy_results.csv")):
        prov_file = path.with_name("provenance.json")
        if not prov_file.exists():
            raise ValueError("Missing provenance for " + str(path))
        prov = json.loads(prov_file.read_text())
        if (prov.get("symbol") != "AAPL" or prov.get("exchange") != "Nasdaq"
            or not prov.get("market_data_are_historical")
            or not prov.get("strategy_order_fills_are_hypothetical")
            or prov.get("regular_session_aapl_book_events", 0) < 2):
            raise ValueError("Unverified or mixed data source: " + str(path))
        day = datetime.strptime(prov["date"], "%m%d%Y").date().isoformat()
        if day in seen:
            raise ValueError("Duplicate historical trading day: " + day)
        seen.add(day)
        with path.open(newline="") as fh:
            rows = list(csv.DictReader(fh))
        policies = {}
        for row in rows:
            if row["day"] != day:
                raise ValueError("Date mismatch in " + str(path))
            key = (float(row["cancel_ahead_fraction"]), row["policy"])
            if key in policies:
                raise ValueError("Repeated policy on " + day)
            policies[key] = row
        if set(policies) != {(f, p) for f in CANCELLATIONS for p in POLICIES}:
            raise ValueError("Incomplete strategy/scenario grid on " + day)
        days.append(dict(date=day, policies=policies, source=prov))
    return sorted(days, key=lambda d: d["date"])


def summarise(days: list[dict]) -> dict:
    if len(days) < 3:
        raise ValueError("Need at least three distinct historical dates, not repeated paths")
    dates = [d["date"] for d in days]
    # For 7+ days, reserve final two dates for a descriptive untouched holdout.
    groups = [("all_dates", days)]
    if len(days) >= 7:
        groups.append(("chronological_last_two", days[-2:]))
    results = []
    for label, group in groups:
        for cancel in CANCELLATIONS:
            def numbers(policy, metric):
                vals = [float(d["policies"][(cancel, policy)][metric]) for d in group]
                if not all(math.isfinite(v) for v in vals):
                    raise ValueError("Nonfinite or missing " + metric)
                return vals
            fixed = numbers("fixed", "terminal_liquidated_net_usd")
            aware = numbers("aware_1tick", "terminal_liquidated_net_usd")
            diff = [a - f for a, f in zip(aware, fixed)]
            results.append(dict(
                sample=label,
                cancel_ahead_fraction=cancel,
                distinct_days=len(group),
                fixed_mean_liquidated_usd=round(statistics.mean(fixed), 5),
                aware_mean_liquidated_usd=round(statistics.mean(aware), 5),
                aware_minus_fixed_mean_usd=round(statistics.mean(diff), 5),
                paired_median_usd=round(statistics.median(diff), 5),
                aware_beats_fixed_days=sum(x > 0 for x in diff),
                fixed_losing_days=sum(x < 0 for x in fixed),
                aware_losing_days=sum(x < 0 for x in aware),
                fixed_mean_abs_inventory=round(statistics.mean(numbers("fixed", "average_abs_inventory")), 5),
                aware_mean_abs_inventory=round(statistics.mean(numbers("aware_1tick", "average_abs_inventory")), 5),
            ))
    return dict(
        source="Official public Nasdaq TotalView-ITCH 5.0 sample files",
        ticker="AAPL",
        actual_independent_dates=dates,
        number_of_distinct_days=len(days),
        prespecified_comparison="fixed versus inventory-aware 1-tick; all 0/50/100% queue cancellation-ahead fractions",
        sample_dates_not_randomly_selected=True,
        candidate_fills_are_hypothetical=True,
        inferential_status="Descriptive only; no Sharpe, annualized alpha, statistical significance, or confidence intervals for this tiny nonrandom sample",
        results=results,
    )


def write(days_folder: Path, output: Path) -> dict:
    data = summarise(load_days(days_folder))
    output.mkdir(parents=True, exist_ok=True)
    (output / "multi_day_summary.json").write_text(json.dumps(data, indent=2) + "\n")
    with (output / "multi_day_table.csv").open("w", newline="") as fh:
        fields = list(data["results"][0])
        writer = csv.DictWriter(fh, fields)
        writer.writeheader()
        writer.writerows(data["results"])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", type=Path, default=Path("results/nasdaq_public"))
    parser.add_argument("--output", type=Path, default=Path("results/nasdaq_multi_day"))
    a = parser.parse_args()
    result = write(a.results_dir, a.output)
    print("Independent AAPL days:", result["number_of_distinct_days"])
    print("Dates:", ", ".join(result["actual_independent_dates"]))
    for row in result["results"]:
        print(row)
    print("Saved", a.output)


if __name__ == "__main__":
    main()
