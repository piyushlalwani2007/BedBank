"""
grid_search.py

Tunes the reserve thresholds for the 'tiered-buffer' policy against the OFFICIAL
HC-03 rubric weights (45/20/15/15/5), averaged over many seeds - not just the
three dev seeds used for eyeballing.

Why this exists:
The RESERVE_RULES thresholds in policies.py ({"critical": 1, "monitored": 2}) were
hand-picked, not optimized. This script sweeps candidate values, scores each
combination with the real rubric formula, and reports the best-performing one so
the choice is backed by data instead of a guess.

Usage:
    python grid_search.py

This only touches local development data (published seeds/distributions), never
evaluator-only state, consistent with the HC-03 online-information rule.
"""

import numpy as np
import pandas as pd
import itertools

import policies
from simulator import generate_arrivals, run_simulation
from metrics import compute_metrics

# ---- Standard HC-03 development constants (from the problem statement) ----
N_PATIENTS = 500
INTERARRIVAL_MEAN = 2.5
ACUITY_LEVELS = [1, 2, 3]
ACUITY_PROBS = [0.60, 0.30, 0.10]
BED_CAPACITY = {"general": 30, "monitored": 10, "critical": 5}
LOS_MEDIAN = {"general": 120, "monitored": 180, "critical": 240}
LOS_SIGMA = 0.35
MAX_WAIT = 240

# ---- Official rubric weights (out of 100), normalized to sum to 1 for scoring ----
RUBRIC_WEIGHTS = {
    "U_wait": 45,
    "U_critical": 20,
    "U_reject": 15,
    "U_specialized": 15,
    # 5 points are runtime/reproducibility - not something a policy choice affects,
    # so they're left out of the tuning objective.
}

# ---- Seeds used for tuning ----
# The published dev seed, plus a spread of additional seeds so the choice isn't
# overfit to one particular random arrival stream. These are all still local
# development seeds (not evaluator-only), consistent with the HC-03 rules.
DEV_SEED = 20260911
TUNING_SEEDS = [DEV_SEED] + list(range(1, 30))  # 30 seeds total

# ---- Candidate reserve thresholds to sweep ----
CRITICAL_RESERVE_CANDIDATES = [0, 1, 2, 3, 4]  # capacity is 5, so 4 is the practical ceiling
MONITORED_RESERVE_CANDIDATES = [0]  # confirmed to have no effect in this scenario - see notes below

POLICY_UNDER_TEST = "tiered-buffer"


def rubric_score(metrics: dict) -> float:
    """Weighted score (0-100 scale) matching the official HC-03 judging criteria."""
    return sum(RUBRIC_WEIGHTS[k] * metrics[k] for k in RUBRIC_WEIGHTS)


def run_one(seed: int, critical_reserve: int, monitored_reserve: int) -> dict:
    # Monkey-patch this policy's reserve rule for the duration of this run.
    policies.RESERVE_RULES[POLICY_UNDER_TEST] = {
        "critical": critical_reserve,
        "monitored": monitored_reserve,
    }
    rng = np.random.default_rng(seed)
    patients = generate_arrivals(rng, N_PATIENTS, INTERARRIVAL_MEAN, ACUITY_LEVELS, ACUITY_PROBS)
    results = run_simulation(patients, rng, BED_CAPACITY, LOS_MEDIAN, LOS_SIGMA, MAX_WAIT, POLICY_UNDER_TEST)
    metrics, _ = compute_metrics(results, MAX_WAIT)
    return metrics


def main():
    rows = []
    combos = list(itertools.product(CRITICAL_RESERVE_CANDIDATES, MONITORED_RESERVE_CANDIDATES))
    print(f"Sweeping {len(combos)} reserve combinations across {len(TUNING_SEEDS)} seeds "
          f"({len(combos) * len(TUNING_SEEDS)} simulation runs)...\n")

    for critical_reserve, monitored_reserve in combos:
        seed_scores = []
        seed_metrics = []
        for seed in TUNING_SEEDS:
            m = run_one(seed, critical_reserve, monitored_reserve)
            seed_metrics.append(m)
            seed_scores.append(rubric_score(m))

        avg_row = {
            "critical_reserve": critical_reserve,
            "monitored_reserve": monitored_reserve,
            "mean_rubric_score": float(np.mean(seed_scores)),
            "std_rubric_score": float(np.std(seed_scores)),
            "mean_U_wait": float(np.mean([m["U_wait"] for m in seed_metrics])),
            "mean_U_critical": float(np.mean([m["U_critical"] for m in seed_metrics])),
            "mean_U_reject": float(np.mean([m["U_reject"] for m in seed_metrics])),
            "mean_U_specialized": float(np.mean([m["U_specialized"] for m in seed_metrics])),
        }
        rows.append(avg_row)

    df = pd.DataFrame(rows).sort_values("mean_rubric_score", ascending=False).reset_index(drop=True)

    pd.set_option("display.width", 140)
    pd.set_option("display.max_columns", None)
    print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    best = df.iloc[0]
    print("\nBest reserve combination found:")
    print(f"  critical_reserve  = {int(best['critical_reserve'])}")
    print(f"  monitored_reserve = {int(best['monitored_reserve'])}")
    print(f"  mean rubric score = {best['mean_rubric_score']:.2f} / 95 "
          f"(excludes the 5-point runtime/reproducibility criterion)")

    df.to_csv("reserve_grid_search_results.csv", index=False)
    print("\nFull results written to reserve_grid_search_results.csv")


if __name__ == "__main__":
    main()
