"""
Produces the two submission artifacts HC-03 asks for that a live Streamlit session
doesn't persist to disk:
  - logs/decisions_<policy>_<seed>.csv   (per-patient decision & occupancy-at-assignment log)
  - logs/occupancy_summary.csv           (bed-type utilization summary per run)
  - dev_metrics.csv                      (U_wait / U_critical / U_reject / U_specialized per run)

Uses only the published development parameters and the required seed (20260911),
plus two extra seeds for a slightly more robust read - exactly the same generator
already used by app.py / eval.py.
"""
import os
import numpy as np
import pandas as pd

from simulator import generate_arrivals, run_simulation
from metrics import compute_metrics

N_PATIENTS = 500
INTERARRIVAL_MEAN = 2.5
ACUITY_LEVELS = [1, 2, 3]
ACUITY_PROBS = [0.60, 0.30, 0.10]
BED_CAPACITY = {"general": 30, "monitored": 10, "critical": 5}
LOS_MEDIAN = {"general": 120, "monitored": 180, "critical": 240}
LOS_SIGMA = 0.35
MAX_WAIT = 240

SEEDS = [20260911, 1, 2]  # 20260911 is the required development seed
POLICIES = ["baseline", "critical-bed-buffer", "tiered-buffer"]

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

dev_metrics_rows = []
occupancy_rows = []

for policy in POLICIES:
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        patients = generate_arrivals(rng, N_PATIENTS, INTERARRIVAL_MEAN, ACUITY_LEVELS, ACUITY_PROBS)
        results = run_simulation(patients, rng, BED_CAPACITY, LOS_MEDIAN, LOS_SIGMA, MAX_WAIT, policy)
        metrics, df = compute_metrics(results, MAX_WAIT)

        # --- decision & occupancy-at-assignment log (per patient) ---
        log_df = pd.DataFrame([{
            "patient_id": p.id,
            "arrival_time": round(p.arrival_time, 2),
            "acuity": p.acuity,
            "status": p.status,
            "bed_type_assigned": p.bed_type,
            "admit_time": round(p.admit_time, 2) if p.admit_time is not None else None,
            "discharge_time": round(p.discharge_time, 2) if p.discharge_time is not None else None,
            "wait_time": round(p.wait_time, 2) if p.wait_time is not None else None,
            "free_general_at_assign": p.free_general_at_assign,
            "free_monitored_at_assign": p.free_monitored_at_assign,
        } for p in results])
        log_path = os.path.join(LOG_DIR, f"decisions_{policy}_{seed}.csv")
        log_df.to_csv(log_path, index=False)

        # --- occupancy / bed-use summary for this run ---
        admitted = df[df["status"] == "admitted"]
        for bed_type, cap in BED_CAPACITY.items():
            n_served = (admitted["bed_type"] == bed_type).sum()
            occupancy_rows.append({
                "policy": policy, "seed": seed, "bed_type": bed_type,
                "capacity": cap, "n_patients_served": int(n_served),
            })

        # --- development metrics row ---
        dev_metrics_rows.append({
            "policy": policy, "seed": seed,
            "U_wait": round(metrics["U_wait"], 4),
            "U_critical": round(metrics["U_critical"], 4),
            "U_reject": round(metrics["U_reject"], 4),
            "U_specialized": round(metrics["U_specialized"], 4),
            "n_admitted": metrics["n_admitted"],
            "n_rejected": metrics["n_rejected"],
            "n_avoidable_specialized": metrics["n_avoidable_specialized"],
        })

pd.DataFrame(occupancy_rows).to_csv(os.path.join(LOG_DIR, "occupancy_summary.csv"), index=False)
dev_metrics_df = pd.DataFrame(dev_metrics_rows)
dev_metrics_df.to_csv("dev_metrics.csv", index=False)

print(dev_metrics_df.to_string(index=False))
print(f"\nWrote {len(SEEDS) * len(POLICIES)} decision logs to {LOG_DIR}/, "
      f"occupancy_summary.csv, and dev_metrics.csv")
