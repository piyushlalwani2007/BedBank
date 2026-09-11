from typing import Dict, List, Optional, Any

COMPATIBILITY = {
    1: ["general", "monitored", "critical"],
    2: ["monitored", "critical"],
    3: ["critical"],
}

WAIT_WEIGHT = {1: 1, 2: 3, 3: 8}

def try_assign(patient: Any, bed_state: Dict[str, Dict[str, int]]) -> Optional[str]:
    """Rule A: assign the lowest-tier compatible bed with free capacity right now."""
    for bed_type in COMPATIBILITY[patient.acuity]:
        if bed_state[bed_type]["free"] > 0:
            return bed_type
    return None

def pick_from_queue(bed_type: str, waiting_queue: List[Any], current_time: float) -> Optional[Any]:
    """Rule B: among waiters compatible with bed_type, pick highest acuity weight, then longest wait."""
    eligible = [p for p in waiting_queue if bed_type in COMPATIBILITY[p.acuity]]
    if not eligible:
        return None
    eligible.sort(key=lambda p: (WAIT_WEIGHT[p.acuity], current_time - p.arrival_time), reverse=True)
    return eligible[0]
