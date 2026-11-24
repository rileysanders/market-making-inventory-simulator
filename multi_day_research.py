"""Walk-forward, paired multi-day research for licensed LOBSTER AAPL ZIPs.

Requires multiple DISTINCT historical trading days; never silently repeats the
single free sample as if it were independent data.

Example:
  python multi_day_research.py --data-dir data/aapl_days --min-days 12
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import re
import statistics
from collections import defaultdict
from pathlib import Path
from zipfile import ZipFile

from queue_replay import Config, run_day, save_rows


def discover_days(folder: Path, depth: int = 5) -> list[tuple[str, Path]]:
    if not folder.is_dir():
        raise FileNotFoundError(f"Data folder not found: {folder}")
    found: dict[str, Path] = {}
    for path in sorted(folder.glob("*.zip")):
        try:
            with ZipFile(path) as archive:
                names = archive.namelist()
        except Exception as error:
            raise ValueError(f"Invalid ZIP: {path}") from error
        msgs = [name for name in names if name.endswith(f"_message_{depth}.csv")]
        books = [name for name in names if name.endswith(f"_orderbook_{depth}.csv")]
        if len(msgs) != 1 or len(books) != 1:
            continue
        if not Path(msgs[0]).name.startswith("AAPL_") or not Path(books[0]).name.startswith("AAPL_"):
            raise ValueError(f"Only AAPL is accepted in this study: {path}")
        day_m = re.search(r"AAPL_(\d{4}-\d{2}-\d{2})_", msgs[0])
        day_b = re.search(r"AAPL_(\d{4}-\d{2}-\d{2})_", books[0])
        if not day_m or not day_b or day_m.group(1) != day_b.group(1):
            raise ValueError(f"Missing or mismatched AAPL dates: {path}")
        day = day_m.group(1)
        if day in found:
            raise ValueError(f"Duplicate historical trading date {day}: {path} and {found[day]}")
        found[day] = path
    return sorted(found.items())


def partition_days(dates: list[str], min_days: int = 12) -> dict[str, list[str]]:
    if dates != sorted(set(dates)):
        raise ValueError("Dates must be strictly increasing and unique")
    if len(dates) < min_days or len(dates) < 5:
        raise ValueError(
            f"Need at least {max(5, min_days)} distinct AAPL days, got {len(dates)}. "
            "The free 2012-06-21 sample is ONE day, not a multi-day backtest."
        )
    n = len(dates)
    n_train = int(n * 0.6)
    n_validation = int(n * 0.2)
    if min(n_train, n_validation, n - n_train - n_validation) < 2:
        raise ValueError("Each chronological split must contain at least two days")
    return {
        "development": dates[:n_train],
        "validation": dates[n_train:n_train+n_validation],
        "holdout_test": dates[n_train+n_validation:],
    }


def bootstrap_interval(values: list[float], n_samples: int = 2000, seed: int = 20261124) -> tuple[float, float]:
    """Exploratory day-level percentile bootstrap; not an exchange-model CI."""
    if len(values) < 2:
        raise ValueError("Bootstrap requires at least two distinct trading days")
    rng = random.Random(seed)
    estimates = sorted(
        statistics.mean(rng.choices(values, k=len(values)))
        for _ in range(n_samples)
    )
    return estimates[int(.025*n_samples)], estimates[min(n_samples - 1, int(.975*n_samples))]


def analyse(rows: list[dict[str, object]], split: dict[str, list[str]],
            reference_latency: float = 10.0, reference_cancel: float = 0.0) -> dict[str, object]:
    """Lock skew selection on validation days; never inspect test for selection."""
    lookup = {(str(x["day"]), float(x["latency_ms"]), float(x["cancel_ahead_fraction"]),
               str(x["policy"])): x for x in rows}
    def net(day: str, policy: str, latency: float, cancel: float) -> float:
        return float(lookup[(day, latency, cancel, policy)]["net_pnl_usd"])

    candidates = ("aware_1tick", "aware_2tick")
    selected = max(
        candidates,
        key=lambda policy: statistics.mean(
            net(day, policy, reference_latency, reference_cancel)
            for day in split["validation"]
        )
    )

    # Report across *every* prespecified execution model as a robustness grid.
    scenarios = sorted({(float(r["latency_ms"]), float(r["cancel_ahead_fraction"])) for r in rows})
    summaries = []
    for latency, cancel in scenarios:
        diffs = [
            net(day, selected, latency, cancel) - net(day, "fixed", latency, cancel)
            for day in split["holdout_test"]
        ]
        ci = bootstrap_interval(diffs)
        summaries.append({
            "latency_ms": latency,
            "cancel_ahead_fraction": cancel,
            "selected_policy": selected,
            "holdout_days": len(diffs),
            "fixed_mean_net_usd": round(statistics.mean(
                net(day, "fixed", latency, cancel) for day in split["holdout_test"]
            ), 5),
            "aware_mean_net_usd": round(statistics.mean(
                net(day, selected, latency, cancel) for day in split["holdout_test"]
            ), 5),
            "paired_mean_delta_usd": round(statistics.mean(diffs), 5),
            "day_bootstrap_ci_low": round(ci[0], 5),
            "day_bootstrap_ci_high": round(ci[1], 5),
            "positive_delta_days": sum(x > 0 for x in diffs),
        })
    return {
        "locked_selected_policy": selected,
        "selection_method": "highest mean daily net P&L on chronological validation split",
        "reference_execution_assumptions": {
            "latency_ms": reference_latency, "cancel_ahead_fraction": reference_cancel
        },
        "splits": split,
        "holdout_robustness": summaries,
        "warning": (
            "Results measure hypothetical historical queue estimates, not actual executions. "
            "Day-level bootstrap assumes exchangeability and is not a calibrated confidence interval. "
            "No guaranteed out-of-sample trading profit; multiple execution assumptions reported."
        ),
    }


def run_many(directory: Path, output: Path, depth: int = 5, min_days: int = 12) -> dict[str, object]:
    dates_and_files = discover_days(directory, depth)
    dates = [day for day, _ in dates_and_files]
    split = partition_days(dates, min_days)
    configs = [
        Config(skew_ticks=skew, latency_ms=latency, cancel_ahead_fraction=cancel)
        for latency in (10.0, 50.0)
        for cancel in (0.0, 0.5, 1.0)
        for skew in (0, 1, 2)
    ]
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for day, path in dates_and_files:
        print(f"Replaying AAPL {day} from {path.name}", flush=True)
        daily = run_day(path, configs, depth, day_override=day)
        if any(x["day"] != day for x in daily):
            raise ValueError(f"Date mismatch in {path}")
        rows.extend(daily)
    save_rows(output / "daily_policy_results.csv", rows)
    summary = analyse(rows, split)
    summary["provenance"] = {
        "ticker": "AAPL", "depth": depth, "trading_days": len(dates),
        "files": [{"day": day, "zip_filename": path.name} for day, path in dates_and_files],
        "vendor_raw_data_distributed": False,
        "model": "Displayed-depth FIFO estimate with cancellation fraction sensitivity"
    }
    (output / "walk_forward_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    save_rows(output / "holdout_robustness.csv", summary["holdout_robustness"])
    return summary


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", type=Path, default=Path("data/aapl_days"))
    p.add_argument("--output", type=Path, default=Path("results/multi_day"))
    p.add_argument("--depth", type=int, default=5)
    p.add_argument("--min-days", type=int, default=12)
    args = p.parse_args()
    result = run_many(args.data_dir, args.output, args.depth, args.min_days)
    print(f"Locked policy: {result['locked_selected_policy']}")
    print(f"Chronological splits: " + ", ".join(
        f"{name} {len(dates)} days" for name, dates in result["splits"].items()
    ))
    for row in result["holdout_robustness"]:
        print(
            f"latency={row['latency_ms']}ms cancel={row['cancel_ahead_fraction']} "
            f"mean_delta_USD={row['paired_mean_delta_usd']:+.4f} "
            f"CI=[{row['day_bootstrap_ci_low']:+.4f},{row['day_bootstrap_ci_high']:+.4f}]"
        )
    print(f"Summaries saved in {args.output.resolve()}")


if __name__ == "__main__":
    main()
