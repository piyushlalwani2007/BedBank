import numpy as np
import pandas as pd
from typing import List, Dict, Any, Tuple

WAIT_WEIGHT = {1: 1, 2: 3, 3: 8}

def compute_metrics(patients: List[Any], max_wait: float) -> Tuple[Dict[str, Any], pd.DataFrame]:
    df = pd.DataFrame([{
        "id": p.id, "acuity": p.acuity, "status": p.status, "bed_type": p.bed_type,
        "wait_time": p.wait_time,
        "free_general_at_assign": p.free_general_at_assign,
        "free_monitored_at_assign": p.free_monitored_at_assign,
    } for p in patients])

    df["wait_capped"] = df["wait_time"].clip(upper=max_wait).fillna(max_wait)
    df["weight"] = df["acuity"].map(WAIT_WEIGHT)

    U_wait = 1 - (df["weight"] * df["wait_capped"]).sum() / (max_wait * df["weight"].sum())

    crit = df[df["acuity"] == 3]
    U_critical = 1.0 if len(crit) == 0 else 1 - crit["wait_capped"].sum() / (max_wait * len(crit))

    n_rejected = (df["status"] == "rejected").sum()
    U_reject = 1 - n_rejected / len(df)

    admitted = df[df["status"] == "admitted"]
    avoidable = 0
    for _, row in admitted.iterrows():
        if row["acuity"] == 1 and row["bed_type"] != "general" and row["free_general_at_assign"] > 0:
            avoidable += 1
        elif row["acuity"] == 2 and row["bed_type"] == "critical" and row["free_monitored_at_assign"] > 0:
            avoidable += 1
    U_specialized = 1.0 if len(admitted) == 0 else 1 - avoidable / len(admitted)

    metrics = {
        "U_wait": float(np.clip(U_wait, 0, 1)),
        "U_critical": float(np.clip(U_critical, 0, 1)),
        "U_reject": float(np.clip(U_reject, 0, 1)),
        "U_specialized": float(np.clip(U_specialized, 0, 1)),
        "n_admitted": len(admitted),
        "n_rejected": int(n_rejected),
        "n_avoidable_specialized": avoidable,
    }
    return metrics, df
