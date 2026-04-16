"""Module for RF Path Loss Estimation (Hotspot Method)."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

from core.shared_utils import calculate_3d_distance, get_mac_column


def _linear_regression(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float]:
    """
    Perform linear regression: y = slope * x + intercept
    Returns (slope, intercept, r_squared)
    """
    if len(x) < 2:
        return 0.0, 0.0, 0.0
    
    A = np.vstack([x, np.ones(len(x))]).T
    slope, intercept = np.linalg.lstsq(A, y, rcond=None)[0]
    
    # Calculate R-squared
    y_pred = slope * x + intercept
    residuals = y - y_pred
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y - np.mean(y))**2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
    
    sigma = np.std(residuals)
    return slope, intercept, r_squared, sigma


def render(df: pd.DataFrame, protocol: str):
    st.subheader("📡 Path Loss Calibration (Golden Device)")

    if df.empty:
        st.info("Load a dataset with GPS and RSSI data to begin calibration.")
        return

    mac_col = get_mac_column(protocol)
    if mac_col not in df.columns:
        st.warning(f"Column {mac_col} not found in dataset.")
        return

    # Phase 1: Target Selection
    st.markdown("### Phase 1: Initialization & Targeting")
    
    # Get unique MACs sorted by strongest RSSI
    device_summary = df.groupby(mac_col).agg({
        "rssi_dbm": ["max", "count"],
        "gps_lat": "first",
        "gps_lon": "first",
        "gps_alt_m": "first"
    })
    device_summary.columns = ["max_rssi", "pkt_count", "lat", "lon", "alt"]
    sort_cal = st.radio("Sort Targets by", ["RSSI", "Packets", "MAC Address", "Name"], index=0, horizontal=True, key="cal_target_sort")
    
    # Prepare list for sorting
    target_data = []
    for mac, row in device_summary.iterrows():
        name = "Unknown"
        if protocol == "wifi" and "vendor" in df.columns:
            v_series = df[df[mac_col] == mac]["vendor"].dropna()
            if not v_series.empty: name = v_series.iloc[0]
        elif protocol == "ble" and "company_name" in df.columns:
            c_series = df[df[mac_col] == mac]["company_name"].dropna()
            if not c_series.empty: name = c_series.iloc[0]
        
        target_data.append({
            "mac": mac,
            "max_rssi": row.max_rssi,
            "pkt_count": row.pkt_count,
            "name": name,
            "lat": row.lat,
            "lon": row.lon,
            "alt": row.alt
        })

    if sort_cal == "RSSI":
        target_data.sort(key=lambda x: x["max_rssi"], reverse=True)
    elif sort_cal == "Packets":
        target_data.sort(key=lambda x: x["pkt_count"], reverse=True)
    elif sort_cal == "MAC Address":
        target_data.sort(key=lambda x: x["mac"])
    elif sort_cal == "Name":
        target_data.sort(key=lambda x: (x["name"].lower(), x["mac"]))

    if not target_data:
        st.warning("No targets found with valid data for calibration.")
        return

    options = [f"{d['mac']} (max: {d['max_rssi']}dBm, {d['pkt_count']} pkts, {d['name']})" for d in target_data]
    selected_option = st.selectbox("Select Target Device (Calibration Hotspot)", options)
    
    if not selected_option:
        return
        
    target_mac = selected_option.split(" (")[0]
    
    # Find matching data in our temp list
    target_info_dict = next(d for d in target_data if d["mac"] == target_mac)

    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Target MAC:** `{target_mac}`")
        if st.button("Lock Target Position (Origin)", type="primary"):
            st.session_state["cal_origin"] = {
                "mac": target_mac,
                "lat": target_info_dict["lat"],
                "lon": target_info_dict["lon"],
                "alt": target_info_dict["alt"]
            }
            st.session_state["cal_buffer"] = [] # Clear previous run
            st.success(f"Locked origin at {target_info_dict['lat']:.6f}, {target_info_dict['lon']:.6f}")

    if "cal_origin" not in st.session_state:
        st.info("Select a device and click 'Lock Target Position' when the drone/unit is directly over the hotspot.")
        return

    origin = st.session_state["cal_origin"]
    st.write(f"📍 **Active Origin:** `{origin['mac']}` at {origin['lat']:.6f}, {origin['lon']:.6f} (Alt: {origin['alt']}m)")

    # Phase 2: Data Acquisition
    st.markdown("---")
    st.markdown("### Phase 2: Data Acquisition")
    
    # Filter data for current MAC
    run_df = df[df[mac_col] == origin["mac"]].copy()
    run_df = run_df.dropna(subset=["gps_lat", "gps_lon", "rssi_dbm"])
    
    if run_df.empty:
        st.warning("No GPS-tagged packets seen for this MAC after locking origin.")
        return

    # Calculate 3D distances
    run_df["dist_3d"] = run_df.apply(
        lambda row: calculate_3d_distance(
            row["gps_lat"], row["gps_lon"], row.get("gps_alt_m", 0),
            origin["lat"], origin["lon"], origin["alt"]
        ), axis=1
    )
    
    # Avoid near-field and logs of small numbers
    valid_cal = run_df[run_df["dist_3d"] >= 1.0].copy()
    valid_cal["log10_dist"] = np.log10(valid_cal["dist_3d"])
    
    st.metric("Samples Collected", len(valid_cal))
    
    if len(valid_cal) < 10:
        st.info("Continue acquisition. Need at least 10 valid samples across different distances.")
        # Even with few samples, we can show what we have
    
    # Phase 3: Visualization & Regression
    st.markdown("---")
    st.markdown("### Phase 3: Visualization & Regression")
    
    if not valid_cal.empty:
        # Scatter Plot
        chart = alt.Chart(valid_cal).mark_circle(size=60).encode(
            x=alt.X("log10_dist", title="log10(Distance [m])"),
            y=alt.Y("rssi_dbm", title="RSSI (dBm)", scale=alt.Scale(zero=False)),
            tooltip=["dist_3d", "rssi_dbm"]
        ).properties(height=400)
        
        # Regression
        slope, intercept, r2, sigma = _linear_regression(
            valid_cal["log10_dist"].values,
            valid_cal["rssi_dbm"].values
        )
        
        # n = -slope / 10
        n_est = -slope / 10.0
        p0_est = intercept
        
        # Add regression line to chart
        x_rng = np.array([valid_cal["log10_dist"].min(), valid_cal["log10_dist"].max()])
        y_rng = slope * x_rng + intercept
        line_df = pd.DataFrame({"x": x_rng, "y": y_rng})
        line = alt.Chart(line_df).mark_line(color="red").encode(x="x", y="y")
        
        st.altair_chart(chart + line, use_container_width=True)
        
        # Results
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric("Path Loss (n)", f"{n_est:.2f}")
        res_col2.metric("RSSI @ 1m (P0)", f"{p0_est:.1f} dBm")
        res_col3.metric("Confidence (R²)", f"{r2:.3f}")
        
        st.write(f"**Std Dev of Residuals (σ):** {sigma:.2f} dB")
        
        # Warnings
        dist_range = valid_cal["dist_3d"].max() - valid_cal["dist_3d"].min()
        if dist_range < 10:
            st.warning("⚠️ Low Diversity: Acquisition covers less than 10m of range. Walk further away for better estimation.")
        if sigma > 10:
            st.warning("⚠️ High Variance: Signal is very noisy (σ > 10dB). Parameters may be unreliable.")

        # Commit
        if st.button("Commit Parameters to Localization Engine", type="primary"):
            st.session_state["loc_params"] = {
                "n": n_est,
                "A": p0_est,
                "sigma": sigma,
                "res_m": 2.0, # Default resolutions
                "vis_thresh": 0.5
            }
            st.success("Parameters updated! Go to 'Localization' view to see the effects.")

    else:
        st.info("Move away from target to begin generating signal profile.")


def render_blank_placeholder():
    st.info("Calibration is disabled for this view.")
