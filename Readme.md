# Hospital Bed Allocation — HC-03 Submission

## What this is
An online, discrete-event simulator and allocation policy for HC-03. Patients arrive one
at a time (exponential inter-arrival, mean 2.5 min), each needs a bed type determined by
acuity (1=general, 2=monitored, 3=critical, with fallback compatibility as specified),
and the policy must decide, at the moment of arrival, which bed (if any) to assign —
using only information available up to that instant.

## Policies implemented
- **`baseline`** — greedy, lowest-tier-first: assign the cheapest compatible bed with
  free capacity right now; if none is free, the patient waits (and is rejected if still
  waiting after 240 minutes).
- **`critical-bed-buffer`** — same as baseline, except it keeps at least 1 critical bed
  reserved from patients for whom critical is *not* their natural tier (acuity 1 and 2),
  so an incoming acuity-3 patient is less likely to find critical fully occupied by
  lower-acuity spillover. The reservation is enforced **both** when a new patient arrives
  **and** when a critical bed is discharged and the waiting queue is re-checked — the
  first version of this policy only enforced it on arrival, which silently let the
  reservation get undone the moment a bed turned over.
- **`tiered-buffer`** — extends the same reservation logic to monitored beds (reserving
  2) to protect against acuity-1 spillover into monitored capacity. Critically, the
  reservation only ever blocks a patient from a bed type that is *not* their own natural
  tier — an acuity-2 patient is never denied a monitored bed, and an acuity-3 patient is
  never denied a critical bed, regardless of reservation thresholds. This avoids
  triggering "avoidable specialized-bed placement" penalties, which an earlier draft of
  this policy did (`U_specialized` dropped to 0.993) before the tier check was added.

All decisions use only: patients already revealed, current bed occupancy, elapsed
waiting times, previously completed stays, and the published arrival/LOS distributions —
never future arrivals, future realized lengths of stay, or future RNG state.

## Files
- `simulator.py` — `Patient` dataclass, arrival generator, event-driven simulation loop.
- `policies.py` — the three policies above, plus the shared reservation gate used by
  both the arrival path and the discharge/re-queue path.
- `metrics.py` — `U_wait`, `U_critical`, `U_reject`, `U_specialized`, exactly as defined
  in the HC-03 judging criteria.
- `eval.py` — multi-seed batch evaluation helper.
- `run_dev_evaluation.py` — produces `dev_metrics.csv` and the per-patient decision logs
  in `logs/`.
- `app.py` — Streamlit UI for interactive exploration.

## Development results (seeds 20260911, 1, 2 — see `dev_metrics.csv`)
Averaged over a wider 30-seed sweep for a more stable read:

| Policy | U_wait | U_critical | U_reject | U_specialized |
|---|---|---|---|---|
| baseline | 0.3474 | 0.1862 | 0.8132 | 1.0000 |
| critical-bed-buffer | 0.3511 | 0.2031 | 0.8127 | 1.0000 |
| tiered-buffer | 0.3511 | 0.2031 | 0.8127 | 1.0000 |

`critical-bed-buffer` improves `U_critical` by ~9% relative to baseline with no measurable
cost to `U_specialized`, `U_reject`, or `U_wait`. `tiered-buffer` does not add further
improvement under these specific development parameters — level-1 spillover into
monitored beds essentially never occurs at this traffic intensity — but it is kept as a
zero-cost hedge in case unseen evaluation seeds have a different traffic mix.

## Known limitation
The discharge-side re-queue check (`pick_admissible_from_queue`) only re-evaluates the
waiting queue for the specific bed type that was just discharged. If a higher-priority
alternative bed type becomes free at a different moment, an already-waiting patient is
only picked up when *their own* compatible bed type's discharge event fires. This is a
minor inefficiency, not a constraint violation (no future information is used either
way), and did not show measurable impact in development testing.
