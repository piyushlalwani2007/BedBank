from typing import Dict, List, Optional, Any

COMPATIBILITY = {
    1: ["general", "monitored", "critical"],
    2: ["monitored", "critical"],
    3: ["critical"],
}

WAIT_WEIGHT = {1: 1, 2: 3, 3: 8}

def _try_assign_baseline(patient: Any, bed_state: Dict[str, Dict[str, int]]) -> Optional[str]:
    """Rule A: assign the lowest-tier compatible bed with free capacity right now."""
    for bed_type in COMPATIBILITY[patient.acuity]:
        if bed_state[bed_type]["free"] > 0:
            return bed_type
    return None

def _try_assign_critical_buffer(patient: Any, bed_state: Dict[str, Dict[str, int]]) -> Optional[str]:
    """
    Policy: Prioritize critical patients by reserving one critical bed if only one is available
    and the current patient is not acuity 3.
    """
    # First, try to assign a non-critical compatible bed
    for bed_type in COMPATIBILITY[patient.acuity]:
        if bed_type != "critical" and bed_state[bed_type]["free"] > 0:
            return bed_type

    # If no non-critical compatible bed is available, consider critical beds
    if "critical" in COMPATIBILITY[patient.acuity]:
        if patient.acuity == 3: # Acuity 3 patients always get a critical bed if available
            if bed_state["critical"]["free"] > 0:
                return "critical"
        else: # For non-acuity 3 patients
            # If there's more than one critical bed free, they can take one
            if bed_state["critical"]["free"] > 1:
                return "critical"
    return None # No suitable bed found

def try_assign_policy(patient: Any, bed_state: Dict[str, Dict[str, int]], policy_name: str) -> Optional[str]:
    if policy_name == "baseline":
        return _try_assign_baseline(patient, bed_state)
    elif policy_name == "critical-bed-buffer":
        return _try_assign_critical_buffer(patient, bed_state)
    else:
        # Default or raise error for unknown policy
        return _try_assign_baseline(patient, bed_state) # Fallback to baseline

def pick_from_queue(bed_type: str, waiting_queue: List[Any], current_time: float) -> Optional[Any]:
    """Rule B: among waiters compatible with bed_type, pick highest acuity weight, then longest wait."""
    eligible = [p for p in waiting_queue if bed_type in COMPATIBILITY[p.acuity]]
    if not eligible:
        return None
    eligible.sort(key=lambda p: (WAIT_WEIGHT[p.acuity], current_time - p.arrival_time), reverse=True)
    return eligible[0]
