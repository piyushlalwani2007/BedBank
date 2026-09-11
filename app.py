import streamlit as st
import pandas as pd
import numpy as np
from bedbank.simulator import generate_arrivals, run_simulation
from bedbank.metrics import compute_metrics

# Standard Constants
N_PATIENTS = 500
INTERARRIVAL_MEAN = 2.5
ACUITY_LEVELS = [1, 2, 3]
ACUITY_PROBS = [0.60, 0.30, 0.10]
BED_CAPACITY = {"general": 30, "monitored": 10, "critical": 5}
LOS_MEDIAN = {"general": 120, "monitored": 180, "critical": 240}
LOS_SIGMA = 0.35
MAX_WAIT = 240

@st.cache_data
def cached_simulation_run(seed_val, policy_name):
    # Re-seed correctly
    rng = np.random.default_rng(seed_val)
    patients = generate_arrivals(rng, N_PATIENTS, INTERARRIVAL_MEAN, ACUITY_LEVELS, ACUITY_PROBS)

    # Run simulation
    results = run_simulation(patients, rng, BED_CAPACITY, LOS_MEDIAN, LOS_SIGMA, MAX_WAIT)
    metrics, _ = compute_metrics(results, MAX_WAIT)
    return metrics

st.title("🏥 Hospital Bed Allocation Simulator")
st.write("Assess room assignment rules, waiting metrics, and critical patient rejection rates.")

# Sidebar Controls
st.sidebar.header("Simulation Settings")
seed_input = st.sidebar.text_input("Enter Seeds (comma separated)", "20260911, 1, 2")
selected_policies = st.sidebar.multiselect(
    "Select Policies to Compare",
    options=["baseline", "Rule B", "critical-bed-buffer"],
    default=["baseline"]
)

run_button = st.sidebar.button("Run Simulation")

if run_button:
    try:
        seeds = [int(s.strip()) for s in seed_input.split(",") if s.strip().isdigit()]
    except ValueError:
        st.error("Please enter valid integer seeds.")
        seeds = []

    if not seeds:
        st.warning("Please enter at least one valid seed.")
    elif not selected_policies:
        st.warning("Please select at least one policy.")
    else:
        all_results = []

        for policy in selected_policies:
            for s in seeds:
                metrics = cached_simulation_run(s, policy)
                row = {
                    "Policy": policy,
                    "Seed": s,
                    "U_wait": metrics["U_wait"],
                    "U_critical": metrics["U_critical"],
                    "U_reject": metrics["U_reject"],
                    "U_specialized": metrics["U_specialized"],
                    "Admitted": metrics["n_admitted"],
                    "Rejected": metrics["n_rejected"]
                }
                all_results.append(row)

        df_results = pd.DataFrame(all_results)

        st.subheader("Simulation Performance Metrics")
        st.dataframe(df_results.style.format({
            "U_wait": "{:.4f}",
            "U_critical": "{:.4f}",
            "U_reject": "{:.4f}",
            "U_specialized": "{:.4f}"
        }))

        # Comparison Bar Chart if multiple policies are selected
        if len(selected_policies) > 1:
            st.subheader("Policy Comparison (Averages across Seeds)")
            avg_df = df_results.groupby("Policy")[["U_wait", "U_critical", "U_reject", "U_specialized"]].mean()
            st.bar_chart(avg_df)
