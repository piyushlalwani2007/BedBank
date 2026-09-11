import numpy as np
import pandas as pd
from typing import List, Dict
from .simulator import generate_arrivals, run_simulation # Changed to relative import
from .metrics import compute_metrics # Changed to relative import

def multi_seed_eval(seeds: List[int], n_patients: int, interarrival_mean: float, acuity_levels: List[int], acuity_probs: List[float], bed_capacity: Dict[str, int], los_median: Dict[str, float], los_sigma: float, max_wait: float, policy_name: str = "baseline"):
    results = []
    for s in seeds:
        r = np.random.default_rng(s)
        pts = generate_arrivals(r, n_patients, interarrival_mean, acuity_levels, acuity_probs)
        pts_result = run_simulation(pts, r, bed_capacity, los_median, los_sigma, max_wait, policy_name)
        m, _ = compute_metrics(pts_result, max_wait)
        m["seed"] = s
        results.append(m)
    return pd.DataFrame(results)
