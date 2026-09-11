import numpy as np
import pandas as pd
from typing import List
from simulator import generate_arrivals, run_simulation
from metrics import compute_metrics

def multi_seed_eval(seeds: List[int], n_patients, interarrival_mean, acuity_levels, acuity_probs, bed_capacity, los_median, los_sigma, max_wait):
    results = []
    for s in seeds:
        r = np.random.default_rng(s)
        pts = generate_arrivals(r, n_patients, interarrival_mean, acuity_levels, acuity_probs)
        pts_result = run_simulation(pts, r, bed_capacity, los_median, los_sigma, max_wait)
        m, _ = compute_metrics(pts_result, max_wait)
        m["seed"] = s
        results.append(m)
    return pd.DataFrame(results)
