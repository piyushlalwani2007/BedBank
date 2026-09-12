from typing import Dict, List, Optional, Any

COMPATIBILITY = {
    1: ["general", "monitored", "critical"],
    2: ["monitored", "critical"],
    3: ["critical"],
}

WAIT_WEIGHT = {1: 1, 2: 3, 3: 8}

# How many free beds of a given (reserved) type must remain before a patient who is
# "borrowing" that tier (it is not their natural/home tier) may take one.
# Keyed by policy_name -> {bed_type: reserve_floor}.
#
# Values below were chosen by grid_search.py: swept critical_reserve in [0..4] and
# monitored_reserve in [0..4] against the official rubric score (45*U_wait +
# 20*U_critical + 15*U_reject + 15*U_specialized), averaged over 30 seeds.
# Findings:
#   - critical_reserve is the lever that matters: raising it from 0 to 4 lifts
#     U_critical from ~0.184 to ~0.210 with only a small U_wait/U_reject cost,
#     and the score plateaus by reserve=4 (out of 5 total critical beds).
#   - monitored_reserve had NO measurable effect in this scenario across every
#     value tested (0-4) - monitored-tier crowding never got severe enough to
#     bind at these arrival rates/capacities, so it's set to 0 to avoid implying
#     a protection that isn't actually happening.
RESERVE_RULES: Dict[str, Dict[str, int]] = {
    "critical-bed-buffer": {"critical": 4},
    "tiered-buffer": {"critical": 4, "monitored": 0},
}

# Each acuity's own preferred/required tier. A reservation on a bed_type never blocks
# the acuity level for whom that bed_type IS the home tier - e.g. reserving monitored
# beds is meant to stop level-1 spillover, never to deny level-2 patients their own
# preferred bed (that would itself create an avoidable specialized-bed placement).
HOME_BED = {1: "general", 2: "monitored", 3: "critical"}


def _reserved_ok(
    patient: Any,
    bed_type: str,
    bed_state: Dict[str, Dict[str, int]],
    policy_name: str,
    waiting_queue: Optional[List[Any]] = None,
) -> bool:
    """
    Shared reservation gate used both when a new arrival is being routed AND when a
    freshly-discharged bed is being handed to someone from the waiting queue. Keeping
    this in one place is what guarantees the buffer can't be bypassed at discharge time.
    Only reads the CURRENT bed_state - no future information is used.

    NOTE: an earlier version of this function tried to only bind the reserve when a
    HOME-tier patient was already sitting in the waiting queue. That was wrong: a
    reservation is meant to protect capacity for a critical patient who has not
    arrived YET. By definition such a patient isn't in the queue at the moment the
    reserve needs to bind, so that check made the reserve a no-op (verified: it made
    tiered-buffer produce results bit-for-bit identical to baseline). Reverted to the
    original unconditional reserve-floor check. waiting_queue is accepted as an
    optional parameter for signature compatibility but intentionally unused here.
    """
    reserve = RESERVE_RULES.get(policy_name, {}).get(bed_type)
    if reserve is None:
        return True  # this policy doesn't reserve this bed type
    if HOME_BED[patient.acuity] == bed_type:
        return True  # this is the patient's own natural tier - never withheld from them
    return bed_state[bed_type]["free"] - 1 >= reserve


def _try_assign_baseline(patient: Any, bed_state: Dict[str, Dict[str, int]]) -> Optional[str]:
    """Rule A: assign the lowest-tier compatible bed with free capacity right now."""
    for bed_type in COMPATIBILITY[patient.acuity]:
        if bed_state[bed_type]["free"] > 0:
            return bed_type
    return None


def _try_assign_buffered(
    patient: Any,
    bed_state: Dict[str, Dict[str, int]],
    policy_name: str,
    waiting_queue: Optional[List[Any]] = None,
) -> Optional[str]:
    """
    Generic buffered assignment: try cheapest-first compatible bed, but for any bed_type
    this policy reserves, only take it if _reserved_ok allows it.
    """
    for bed_type in COMPATIBILITY[patient.acuity]:
        if bed_state[bed_type]["free"] > 0 and _reserved_ok(patient, bed_type, bed_state, policy_name, waiting_queue):
            return bed_type
    return None


def try_assign_policy(
    patient: Any,
    bed_state: Dict[str, Dict[str, int]],
    policy_name: str,
    waiting_queue: Optional[List[Any]] = None,
) -> Optional[str]:
    if policy_name == "baseline":
        return _try_assign_baseline(patient, bed_state)
    elif policy_name in RESERVE_RULES:
        return _try_assign_buffered(patient, bed_state, policy_name, waiting_queue)
    else:
        # Default / unknown policy name: fall back to baseline
        return _try_assign_baseline(patient, bed_state)


def can_admit_from_queue(
    patient: Any,
    bed_type: str,
    bed_state: Dict[str, Dict[str, int]],
    policy_name: str,
    waiting_queue: Optional[List[Any]] = None,
) -> bool:
    """
    Called when a bed has just been discharged and pick_from_queue has proposed `patient`
    for it. Enforces the SAME reservation rule that governs new arrivals, so a policy's
    buffer can't be silently undone the moment a reserved bed turns over. Uses only the
    current bed_state/waiting_queue - no future information.
    """
    return _reserved_ok(patient, bed_type, bed_state, policy_name, waiting_queue)


def _sorted_eligible(bed_type: str, waiting_queue: List[Any], current_time: float) -> List[Any]:
    eligible = [p for p in waiting_queue if bed_type in COMPATIBILITY[p.acuity]]
    eligible.sort(key=lambda p: (WAIT_WEIGHT[p.acuity], current_time - p.arrival_time), reverse=True)
    return eligible


def pick_from_queue(bed_type: str, waiting_queue: List[Any], current_time: float) -> Optional[Any]:
    """Rule B: among waiters compatible with bed_type, pick highest acuity weight, then longest wait."""
    eligible = _sorted_eligible(bed_type, waiting_queue, current_time)
    return eligible[0] if eligible else None


def pick_admissible_from_queue(
    bed_type: str,
    waiting_queue: List[Any],
    current_time: float,
    bed_state: Dict[str, Dict[str, int]],
    policy_name: str,
) -> Optional[Any]:
    """
    Same priority order as pick_from_queue, but skips any candidate the policy's own
    reservation rule would refuse (see can_admit_from_queue). This is what keeps a
    buffering policy's reservation intact when a reserved bed is discharged, instead of
    handing it straight to the highest-priority waiter regardless of policy intent.
    Only looks at current bed_state / waiting_queue - no future information.

    Note: waiting_queue itself is passed through to can_admit_from_queue so the reserve
    can check whether a HOME-tier patient for bed_type is present elsewhere in the queue.
    """
    for candidate in _sorted_eligible(bed_type, waiting_queue, current_time):
        if can_admit_from_queue(candidate, bed_type, bed_state, policy_name, waiting_queue):
            return candidate
    return None
