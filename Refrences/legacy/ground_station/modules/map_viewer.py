"""Spatial map viewer for WiFi and BLE datasets."""

from __future__ import annotations

import math
from typing import Iterable, List, Optional
import base64
from io import BytesIO

import folium
from folium.plugins import FastMarkerCluster
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import streamlit as st
from streamlit_folium import st_folium

from core.shared_utils import get_mac_column, get_frame_type_column, haversine_distance


def _build_popup(row: pd.Series, mac_col: str, is_heartbeat: bool) -> str:
    parts = [f"Time: {row.get('t_bin', '')}"]
    if is_heartbeat:
        parts.append("Heartbeat (No devices)")
    else:
        mac_list: List[str] = row.get(mac_col, []) if isinstance(row.get(mac_col, []), list) else [row.get(mac_col)]
        mac_list = [m for m in mac_list if pd.notna(m) and m]
        if mac_list:
            parts.append(f"Devices: {len(mac_list)}")
            parts.append(f"MACs: {', '.join(mac_list[:5])}{'…' if len(mac_list) > 5 else ''}")
        rssi = row.get("rssi_dbm")
        if pd.notna(rssi):
            parts.append(f"Avg RSSI: {rssi:.1f} dBm")
    lat = row.get("lat_r")
    lon = row.get("lon_r")
    if pd.notna(lat) and pd.notna(lon):
        parts.append(f"Lat: {lat:.6f}, Lon: {lon:.6f}")
    return "<br>".join(parts)


def _prepare_map_groups(df: pd.DataFrame, protocol: str) -> pd.DataFrame:
    mac_col = get_mac_column(protocol)
    if df.empty:
        return df
    map_df = df.dropna(subset=["gps_lat", "gps_lon"]).copy()
    if map_df.empty:
        return map_df

    # Rounded coords and time bins for grouping
    map_df["lat_r"] = map_df["gps_lat"].round(5)
    map_df["lon_r"] = map_df["gps_lon"].round(5)
    if "timestamp_utc" in map_df.columns:
        map_df["t_bin"] = map_df["timestamp_utc"].dt.round("1s")
    else:
        map_df["t_bin"] = ""

    frame_col = get_frame_type_column(protocol)
    map_df["is_heartbeat"] = map_df.get(frame_col, "") == "heartbeat"

    grouped = map_df.groupby(["t_bin", "lat_r", "lon_r"]).agg({
        mac_col: lambda x: [m for m in x if pd.notna(m) and m],
        "rssi_dbm": "mean",
        "is_heartbeat": lambda x: all(x),
    }).reset_index().sort_values("t_bin")
    return grouped


def render(
    df: pd.DataFrame,
    protocol: str,
    selected_macs: Optional[Iterable[str]] = None,
    show_packets: bool = True,
):
    st.subheader("🗺️ Spatial Analysis")

    if df.empty:
        st.info("No data available to render the map.")
        return

    mac_col = get_mac_column(protocol)
    grouped = _prepare_map_groups(df, protocol)
    if grouped.empty:
        st.warning("No GPS data found in the current selection.")
        return

    avg_lat, avg_lon = grouped["lat_r"].mean(), grouped["lon_r"].mean()
    m = folium.Map([avg_lat, avg_lon], zoom_start=19, control_scale=True, max_zoom=24, tiles=None)
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri Satellite",
        overlay=False,
        show=True,
        max_zoom=24,
        max_native_zoom=18
    ).add_to(m)
    folium.TileLayer("openstreetmap", name="OpenStreetMap", overlay=False, show=False, max_zoom=24, max_native_zoom=18).add_to(m)

    # Route polyline (downsample if huge)
    route_points = grouped[["lat_r", "lon_r"]].values.tolist()
    if len(route_points) > 5000:
        step = math.ceil(len(route_points) / 5000)
        route_points = route_points[::step]
    folium.PolyLine(route_points, color="cyan", weight=3, opacity=0.6).add_to(m)

    selected = set(selected_macs or [])
    heartbeats = []
    others = []
    targets = []
    for _, row in grouped.iterrows():
        is_heartbeat = bool(row.get("is_heartbeat", False))
        macs: List[str] = row.get(mac_col, []) if isinstance(row.get(mac_col, []), list) else []
        is_target = selected and any(m in selected for m in macs)
        entry = (row["lat_r"], row["lon_r"], _build_popup(row, mac_col, is_heartbeat))
        if is_heartbeat:
            heartbeats.append(entry)
        elif is_target:
            targets.append(entry)
        else:
            others.append(entry)

    for lat, lon, popup in targets:
        folium.CircleMarker(
            [lat, lon], radius=7, color="white", weight=2, fill=True, fill_color="#f4b000", fill_opacity=0.9, popup=popup
        ).add_to(m)

    MAX_SIMPLE = 1000
    if len(others) <= MAX_SIMPLE:
        for lat, lon, popup in others:
            folium.CircleMarker(
                [lat, lon], radius=4, color="#1f77b4", weight=1, fill=True, fill_color="#1f77b4", fill_opacity=0.8, popup=popup
            ).add_to(m)
    else:
        cluster_data = [[lat, lon, popup] for lat, lon, popup in others]
        FastMarkerCluster(data=cluster_data, name="Detections").add_to(m)
        st.caption(f"Clustered {len(others):,} detections for responsiveness.")

    show_hb = st.checkbox("Show Heartbeats", value=False, help="Toggle display of heartbeats.")
    if show_hb:
        for lat, lon, popup in heartbeats:
            folium.CircleMarker(
                [lat, lon], radius=3, color="#ff0000", weight=1, fill=True, fill_color="#ff0000", fill_opacity=0.6, popup=popup
            ).add_to(m)

    # --- Overlays ---
    st.markdown("---")
    st.markdown("**Layer Overlays**")
    
    # 1. Ground Truth Overlay
    if st.checkbox("Show Ground Truths", value=True, help="Overlay defined ground truth locations."):
        gt_list = st.session_state.get("ground_truth_list", [])
        for gt in gt_list:
            folium.Marker(
                [gt['lat'], gt['lon']],
                tooltip=f"Ground Truth ({gt['mac']})",
                icon=folium.Icon(color=gt.get('color', 'green'), icon="bullseye", prefix="fa"),
                zIndexOffset=2000
            ).add_to(m)

    # 2. Localization Heatmap Overlay
    if "multi_target_results" in st.session_state and st.session_state["multi_target_results"]:
        if st.checkbox("Show Localization Heatmaps", value=True, help="Overlay calculated localization heatmaps."):
            results = st.session_state["multi_target_results"]
            
            for i, (cid, res) in enumerate(results.items()):
                prob_map = res['prob_map']
                bounds = res['bounds']
                label = res['label']
                
                # Normalize & Colorize (replicated from localization_view)
                s_min, s_max = np.min(prob_map), np.max(prob_map)
                if s_max > s_min:
                    pm_norm = (prob_map - s_min) / (s_max - s_min)
                else:
                    pm_norm = prob_map - s_min
                
                # Use jet colormap
                cmap = cm.jet
                img = cmap(pm_norm)
                
                # Alpha channel
                img[:, :, 3] = np.clip(pm_norm * 0.8, 0.0, 0.8)
                img[pm_norm < 0.1, 3] = 0.0
                img = np.flipud(img)

                buf = BytesIO()
                plt.imsave(buf, img, format="png")
                buf.seek(0)
                data_url = f"data:image/png;base64,{base64.b64encode(buf.read()).decode()}"
                
                folium.raster_layers.ImageOverlay(
                    image=data_url,
                    bounds=bounds,
                    opacity=0.6,
                    interactive=False,
                    name=f"Heatmap: {label}",
                    zindex=10 + i,
                    show=False,
                ).add_to(m)
                
                # Peak Marker
                peak = res.get('peak')
                if peak:
                    folium.Marker(
                        [peak['lat'], peak['lon']],
                        tooltip=f"{label} (Conf: {peak['confidence']:.2f})",
                        icon=folium.Icon(color="red", icon="crosshairs", prefix="fa"),
                        zIndexOffset=1000
                    ).add_to(m)

    # --- Distance Measurement Markers ---
    if "map_measure_points" not in st.session_state:
        st.session_state["map_measure_points"] = []
    
    measure_points = st.session_state["map_measure_points"]
    for i, (plat, plon) in enumerate(measure_points):
        folium.Marker(
            [plat, plon],
            tooltip=f"Measure Point {i+1}",
            icon=folium.Icon(color="blue", icon="ruler", prefix="fa")
        ).add_to(m)
        
    if len(measure_points) == 2:
        folium.PolyLine(measure_points, color="blue", weight=2, dash_array="5, 5").add_to(m)

    folium.LayerControl().add_to(m)
    out = st_folium(m, width="100%", height=600, key="map_view_folium")
    
    # --- Interaction Logic (Distance) ---
    if "prev_map_clicked" not in st.session_state:
        st.session_state["prev_map_clicked"] = None
    if "prev_map_obj_clicked" not in st.session_state:
        st.session_state["prev_map_obj_clicked"] = None
        
    if out:
        curr_clicked = out.get("last_clicked")
        curr_obj_clicked = out.get("last_object_clicked")
        
        new_point = None
        
        # Priority: Object Click (Marker) > Map Click
        # We detect CHANGE to know which one was just triggered
        
        if curr_obj_clicked != st.session_state["prev_map_obj_clicked"] and curr_obj_clicked is not None:
             st.session_state["prev_map_obj_clicked"] = curr_obj_clicked
             new_point = (curr_obj_clicked["lat"], curr_obj_clicked["lng"])
             
        elif curr_clicked != st.session_state["prev_map_clicked"] and curr_clicked is not None:
             st.session_state["prev_map_clicked"] = curr_clicked
             new_point = (curr_clicked["lat"], curr_clicked["lng"])
             
        if new_point:
            clat, clon = new_point
            
            # Check against last MEASURED point to avoid duplicates
            is_valid = True
            if measure_points:
                last_pt = measure_points[-1]
                if abs(last_pt[0] - clat) < 1e-9 and abs(last_pt[1] - clon) < 1e-9:
                    is_valid = False
            
            if is_valid:
                new_pt_list = measure_points.copy()
                if len(new_pt_list) >= 2:
                    new_pt_list = []
                
                new_pt_list.append((clat, clon))
                st.session_state["map_measure_points"] = new_pt_list
                st.rerun()

    # --- Measurement UI ---
    st.markdown("### 📏 Distance Measurement")
    m_col1, m_col2 = st.columns([3, 1])
    
    with m_col1:
        if not measure_points:
            st.info("Click 2 points on the map (or markers) to measure distance.")
        elif len(measure_points) == 1:
            p1 = measure_points[0]
            st.write(f"**Point 1:** `{p1[0]:.6f}, {p1[1]:.6f}`")
            st.info("Select a second point to measure distance.")
        elif len(measure_points) == 2:
            p1 = measure_points[0]
            p2 = measure_points[1]
            dist = haversine_distance(p1[0], p1[1], p2[0], p2[1])
            st.write(f"**Point 1:** `{p1[0]:.6f}, {p1[1]:.6f}`")
            st.write(f"**Point 2:** `{p2[0]:.6f}, {p2[1]:.6f}`")
            st.success(f"**Distance:** **{dist:.2f} m**")
    
    with m_col2:
        if st.button("Clear Points", key="clear_map_measure"):
            st.session_state["map_measure_points"] = []
            st.rerun()

    if show_packets:
        st.markdown("---")
        st.markdown("**Packet Inspector**")
        display_cols = [c for c in ["timestamp_utc", mac_col, "rssi_dbm", "channel", "frame_type", "event_type", "gps_lat", "gps_lon"] if c in df.columns]
        st.dataframe(df[display_cols].sort_values("timestamp_utc") if "timestamp_utc" in df.columns else df[display_cols], use_container_width=True)


def render_blank_placeholder():
    st.info("Map viewer is disabled for this layout.")
