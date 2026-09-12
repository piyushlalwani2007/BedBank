import numpy as np
import heapq
import pandas as pd
from dataclasses import dataclass
from typing import Optional, List, Dict
from policies import try_assign_policy, pick_admissible_from_queue

@dataclass
class Patient:
    id: int
    arrival_time: float
    acuity: int
    status: str = "waiting"
    bed_type: Optional[str] = None
    admit_time: Optional[float] = None
    discharge_time: Optional[float] = None
    wait_time: Optional[float] = None
    free_general_at_assign: Optional[int] = None
    free_monitored_at_assign: Optional[int] = None

def generate_arrivals(rng: np.random.Generator, n_patients: int, interarrival_mean: float, acuity_levels: List[int], acuity_probs: List[float]):
    """Generate n_patients arrivals: exponential interarrival times, categorical acuity."""
    patients = []
    t = 0.0
    for i in range(n_patients):
        t += rng.exponential(interarrival_mean)
        acuity = rng.choice(acuity_levels, p=acuity_probs)
        patients.append(Patient(id=i, arrival_time=t, acuity=int(acuity)))
    return patients

def run_simulation(patients: List[Patient], rng: np.random.Generator, bed_capacity: Dict[str, int], los_median: Dict[str, float], los_sigma: float, max_wait: float, policy_name: str = "baseline"):
    """Online, event-driven simulation. Policy only ever sees current/past state."""
    bed_state = {bt: {"free": cap} for bt, cap in bed_capacity.items()}
    waiting_queue = []
    patient_by_id = {p.id: p for p in patients}

    event_queue = []
    seq = 0
    def schedule(time, event_type, pid):
        nonlocal seq
        heapq.heappush(event_queue, (time, seq, event_type, pid))
        seq += 1

    for p in patients:
        schedule(p.arrival_time, "ARRIVAL", p.id)

    def admit(patient, bed_type, current_time):
        patient.free_general_at_assign = bed_state["general"]["free"]
        patient.free_monitored_at_assign = bed_state["monitored"]["free"]
        bed_state[bed_type]["free"] -= 1
        patient.status = "admitted"
        patient.bed_type = bed_type
        patient.admit_time = current_time
        patient.wait_time = current_time - patient.arrival_time
        los = rng.lognormal(mean=np.log(los_median[bed_type]), sigma=los_sigma)
        patient.discharge_time = current_time + los
        schedule(patient.discharge_time, "DISCHARGE", patient.id)

    while event_queue:
        current_time, _, event_type, pid = heapq.heappop(event_queue)
        patient = patient_by_id[pid]

        if event_type == "ARRIVAL":
            bed_type = try_assign_policy(patient, bed_state, policy_name)
            if bed_type:
                admit(patient, bed_type, current_time)
            else:
                waiting_queue.append(patient)
                schedule(current_time + max_wait, "REJECT_CHECK", pid)

        elif event_type == "REJECT_CHECK":
            if patient.status == "waiting":
                patient.status = "rejected"
                patient.wait_time = max_wait
                if patient in waiting_queue:
                    waiting_queue.remove(patient)

        elif event_type == "DISCHARGE":
            bed_state[patient.bed_type]["free"] += 1
            # Respects the same reservation rule used at ARRIVAL time, so a buffering
            # policy's reserved capacity can't be handed away the instant it turns over.
            chosen = pick_admissible_from_queue(patient.bed_type, waiting_queue, current_time, bed_state, policy_name)
            if chosen:
                waiting_queue.remove(chosen)
                admit(chosen, patient.bed_type, current_time)
            # else: no eligible waiter passes the reservation gate right now - the bed
            # stays free, preserved for a higher-priority arrival, consistent with the
            # chosen policy's intent.

    return patients
