"""Probabilistic localization view using LikelihoodGrid."""

from __future__ import annotations

import base64
import math
from io import BytesIO
from typing import Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

from core.likelihood_grid.grid import LikelihoodGrid
from core.likelihood_grid.model import calibrate
from core.likelihood_grid.ransac import RANSACLocalization
from core.shared_utils import haversine_distance


def _compute_distances(df, lat0, lon0):
    R = 6371000.0
    dlat = np.radians(df["gps_lat"].values - lat0)
    dlon = np.radians(df["gps_lon"].values - lon0)
    lat0_rad = np.radians(lat0)
    x = dlon * R * np.cos(lat0_rad)
    y = dlat * R
    return np.sqrt(x ** 2 + y ** 2)


def _render_heatmap(grid_layers: list, origin_lat, origin_lon, show_grid: bool = False, resolution_m: float = 1.0, ground_truth: dict = None):
    """
    Render multiple heatmaps layers.
    grid_layers: List of dicts with keys:
        - 'data': prob_map (np.ndarray)
        - 'bounds': [[lat1, lon1], [lat2, lon2]]
        - 'label': str (Cluster Name)
        - 'peak': dict (Lat/Lon/Conf) or None
        - 'color_map': str (matplotlib colormap name, e.g., 'jet', 'viridis', 'plasma')
    """
    # Render Heatmaps
    from matplotlib import cm
    
    # Determine global bounds for grid if multiple layers
    global_bounds = None
    
    # Pre-process layers to find bounds
    for layer in grid_layers:
        bounds = layer['bounds']
        if global_bounds is None:
            # Need deep copy or fresh list to avoid mutating original ref if logic changes
            global_bounds = [list(bounds[0]), list(bounds[1])]
        else:
            # Expand to include this layer
            global_bounds[0][0] = min(global_bounds[0][0], bounds[0][0])
            global_bounds[0][1] = min(global_bounds[0][1], bounds[0][1])
            global_bounds[1][0] = max(global_bounds[1][0], bounds[1][0])
            global_bounds[1][1] = max(global_bounds[1][1], bounds[1][1])

    # Determine Map Center
    if global_bounds:
        center_lat = (global_bounds[0][0] + global_bounds[1][0]) / 2.0
        center_lon = (global_bounds[0][1] + global_bounds[1][1]) / 2.0
    else:
        center_lat, center_lon = origin_lat, origin_lon

    m = folium.Map(location=[center_lat, center_lon], zoom_start=19, max_zoom=24, control_scale=True, tiles=None)
    
    folium.TileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri", 
        name="Esri Satellite", 
        overlay=False, 
        show=True,
        max_zoom=24,
        max_native_zoom=18
    ).add_to(m)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", overlay=False, show=False, max_zoom=24, max_native_zoom=18).add_to(m)
    
    for i, layer in enumerate(grid_layers):
        prob_map = layer['data']
        bounds = layer['bounds']
        label = layer['label']
        
        # Normalize
        s_min, s_max = np.min(prob_map), np.max(prob_map)
        if s_max > s_min:
            pm_norm = (prob_map - s_min) / (s_max - s_min)
        else:
            pm_norm = prob_map - s_min
            
        # Get Colormap
        cmap_name = layer.get('color_map', 'jet')
        try:
            cmap = cm.get_cmap(cmap_name)
        except:
            cmap = cm.jet
            
        img = cmap(pm_norm)
        
        # Alpha channel: clear for low probability, opaque for high
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
            show=False,  # <--- Deselected by default
            name=f"Heatmap: {label}",
            zindex=10 + i,
        ).add_to(m)
        
        # Peak Marker
        peak = layer.get('peak')
        if peak:
            folium.Marker(
                [peak['lat'], peak['lon']],
                tooltip=f"{label} (Conf: {peak['confidence']:.2f})",
                icon=folium.Icon(color="red", icon="crosshairs", prefix="fa"),
                zIndexOffset=1000
            ).add_to(m)

    if show_grid and global_bounds:
        lat_min, lon_min = global_bounds[0]
        lat_max, lon_max = global_bounds[1]
        
        # Approx meters to deg
        R = 6371000.0
        lat_step = (resolution_m / R) * (180 / math.pi)
        lon_step = (resolution_m / (R * math.cos(math.radians(lat_min)))) * (180 / math.pi)
        
        # Vertical lines
        curr_lon = lon_min
        while curr_lon <= lon_max:
            folium.PolyLine([(lat_min, curr_lon), (lat_max, curr_lon)], 
                            color="white", weight=0.5, opacity=0.2).add_to(m)
            curr_lon += lon_step
            
        # Horizontal lines
        curr_lat = lat_min
        while curr_lat <= lat_max:
            folium.PolyLine([(curr_lat, lon_min), (curr_lat, lon_max)], 
                            color="white", weight=0.5, opacity=0.2).add_to(m)
            curr_lat += lat_step

    # Render Ground Truths (List)
    gt_list = st.session_state.get("ground_truth_list", [])
    if gt_list:
        for gt in gt_list:
            folium.Marker(
                [gt['lat'], gt['lon']],
                tooltip=f"Ground Truth ({gt['mac']})",
                icon=folium.Icon(color=gt.get('color', 'green'), icon="bullseye", prefix="fa"),
                zIndexOffset=2000
            ).add_to(m)
    elif ground_truth: # Fallback for legacy single arg
         folium.Marker(
            [ground_truth['lat'], ground_truth['lon']],
            tooltip=f"Ground Truth ({ground_truth['mac']})",
            icon=folium.Icon(color="green", icon="bullseye", prefix="fa"),
            zIndexOffset=2000
        ).add_to(m)

    # --- Distance Measurement Markers ---
    if "loc_measure_points" not in st.session_state:
        st.session_state["loc_measure_points"] = []
    
    measure_points = st.session_state["loc_measure_points"]
    for i, (plat, plon) in enumerate(measure_points):
        folium.Marker(
            [plat, plon],
            tooltip=f"Measure Point {i+1}",
            icon=folium.Icon(color="blue", icon="ruler", prefix="fa")
        ).add_to(m)
        
    if len(measure_points) == 2:
        folium.PolyLine(measure_points, color="blue", weight=2, dash_array="5, 5").add_to(m)

    folium.LayerControl().add_to(m)
    out = st_folium(m, width="100%", height=600, key="heatmap_folium_multi")
    
    # --- Interaction Logic ---
    if "prev_loc_clicked" not in st.session_state:
        st.session_state["prev_loc_clicked"] = None
    if "prev_loc_obj_clicked" not in st.session_state:
        st.session_state["prev_loc_obj_clicked"] = None
        
    if out:
        curr_clicked = out.get("last_clicked")
        curr_obj_clicked = out.get("last_object_clicked")
        
        new_point = None
        
        # Priority: Object Click (Marker) > Map Click
        # We detect CHANGE to know which one was just triggered
        
        # Check object click change
        if curr_obj_clicked != st.session_state["prev_loc_obj_clicked"] and curr_obj_clicked is not None:
             st.session_state["prev_loc_obj_clicked"] = curr_obj_clicked
             new_point = (curr_obj_clicked["lat"], curr_obj_clicked["lng"])
             
        # Check map click change (only if obj didn't trigger, or logic could be sequential)
        elif curr_clicked != st.session_state["prev_loc_clicked"] and curr_clicked is not None:
             st.session_state["prev_loc_clicked"] = curr_clicked
             new_point = (curr_clicked["lat"], curr_clicked["lng"])
             
        if new_point:
            clat, clon = new_point
            
            # Check against last MEASURED point to avoid duplicates if somehow triggered
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
                st.session_state["loc_measure_points"] = new_pt_list
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
        if st.button("Clear Points", key="loc_clear_measure"):
            st.session_state["loc_measure_points"] = []
            st.rerun()


def render(df, protocol: str, default_params: Optional[Dict[str, float]] = None):
    st.subheader("📍 Emitter Localization")

    required = {"gps_lat", "gps_lon", "rssi_dbm"}
    if df.empty or not required.issubset(df.columns):
        st.info("Localization requires GPS and RSSI data.")
        return

    valid_df = df.dropna(subset=["gps_lat", "gps_lon", "rssi_dbm"])
    if valid_df.empty:
        st.warning("No rows with valid GPS and RSSI found.")
        return

    params = default_params or st.session_state.get(
        "loc_params",
        {"n": 2.5, "A": -40.0, "sigma": 6.0, "res_m": 2.0, "vis_thresh": 0.5},
    )

    st.markdown("**Heatmap Settings**")
    col1, col2, col3 = st.columns(3)
    p_n = col1.number_input("Path Loss n", value=float(params["n"]), step=0.1, format="%.1f", key="loc_p_n", help="Path loss exponent. Typically 2.0 (free space) to 4.0 (indoors/dense).")
    p_A = col2.number_input("RSSI @ 1m", value=float(params["A"]), step=0.1, format="%.1f", key="loc_p_A", help="Reference RSSI at 1 meter. Typical values: -30 to -50 dBm.")
    p_s = col3.number_input("Sigma", value=float(params["sigma"]), step=0.1, format="%.1f", key="loc_p_s", help="Standard deviation of shadow fading (uncertainty in RSSI model).")

    col4, col5, col6 = st.columns(3)
    res_m = col4.number_input("Grid Resolution (m)", value=float(params.get("res_m", 1.0)), min_value=0.5, max_value=20.0, step=0.5, format="%.1f", key="loc_res_m", help="Size of each grid cell in meters. Smaller = higher resolution but slower.")
    vis_thresh = col5.slider("Sensitivity Cutoff", 0.0, 0.95, float(params.get("vis_thresh", 0.1)), key="loc_vis_thresh", help="Minimum probability threshold for visualization. Hides low-confidence noise.")
    show_grid = col6.checkbox("Show Grid Lines", value=st.session_state.get("show_grid", False), help="Overlay a reference grid on the map.")
    st.session_state["show_grid"] = show_grid

    st.markdown("**Multi-Target Configuration**")
    mt_col1, mt_col2 = st.columns(2)
    alpha_val = mt_col1.number_input("Dynamic Sigma (Alpha)", value=0.05, min_value=0.0, max_value=0.2, step=0.01, format="%.2f", help="Uncertainty scaling with distance.")
    conf_thresh = mt_col2.slider("Confidence Cutoff", 0.0, 1.0, 0.4, step=0.05, key="loc_conf_thresh", help="Confidence threshold for identifying primary targets.")

    st.markdown("**Outlier Rejection (RANSAC)**")
    ran_col1, ran_col2, ran_col3 = st.columns(3)
    use_ransac = ran_col1.toggle("Enable RANSAC", value=True, key="loc_use_ransac", help="Filter outliers per cluster.")
    ran_thresh = ran_col2.number_input("RANSAC Thresh (dB)", value=10.0, min_value=1.0, max_value=30.0, step=1.0, format="%.0f", key="loc_ran_thresh", help="RSSI threshold for RANSAC. Points deviating more are ignored.")
    ran_iters = ran_col3.number_input("RANSAC Iters", value=100, min_value=10, max_value=1000, step=100, key="loc_ran_iters", help="Number of RANSAC iterations. Higher = more robust but slower.")

    if "cluster_id" not in valid_df.columns:
        valid_df["cluster_id"] = 0
        
    # Cluster Selection UI (Pre-Computation)
    unique_clusters = sorted([c for c in valid_df["cluster_id"].unique() if c != -1])
    st.markdown("---")
    
    # Load previous results if available
    if "multi_target_results" not in st.session_state:
        st.session_state["multi_target_results"] = {}
        
    if st.button("Compute Multi-Target Localization", type="primary", key="loc_heatmap_btn"):
        with st.spinner("Processing Clusters..."):
            # Global origin computation
            lat_min, lat_max = valid_df["gps_lat"].min(), valid_df["gps_lat"].max()
            lon_min, lon_max = valid_df["gps_lon"].min(), valid_df["gps_lon"].max()
            margin_m = 50.0
            R = 6371000.0
            margin_deg = math.degrees(margin_m / R)

            origin_lat = lat_min - margin_deg
            origin_lon = lon_min - margin_deg
            h_deg = (lat_max + margin_deg) - origin_lat
            w_deg = (lon_max + margin_deg) - origin_lon
            h_m = math.radians(h_deg) * R
            w_m = math.radians(w_deg) * R * math.cos(math.radians(origin_lat))
            
            # Shared Grid Geometry
            grid_geom = {
                'origin_lat': origin_lat, 
                'origin_lon': origin_lon, 
                'width_m': w_m, 
                'height_m': h_m, 
                'resolution_m': res_m
            }
            
            tr_lat = origin_lat + math.degrees(h_m / R)
            tr_lon = origin_lon + math.degrees(w_m / (R * math.cos(math.radians(origin_lat))))
            bounds = [[origin_lat, origin_lon], [tr_lat, tr_lon]]

            model_params = {"n": p_n, "A": p_A, "sigma": p_s, "alpha": alpha_val}
            
            results = {}
                
            progress_bar = st.progress(0)
            for i, cid in enumerate(unique_clusters):
                cluster_df = valid_df[valid_df["cluster_id"] == cid].copy()
                
                # Optional: Downsample large clusters
                if len(cluster_df) > 1000:
                    cluster_df = cluster_df.sample(1000)
                    
                # Initialize Grid
                grid = LikelihoodGrid(**grid_geom)
                
                # RANSAC
                subset = cluster_df
                if use_ransac and len(cluster_df) > 5:
                    coords = []
                    for _, row in cluster_df.iterrows():
                        mx, my = grid.latlon_to_xy(row["gps_lat"], row["gps_lon"])
                        coords.append([mx, my])
                    coords = np.array(coords)
                    rssis = cluster_df["rssi_dbm"].values
                    
                    ransac = RANSACLocalization(iterations=int(ran_iters), inlier_thresh_dbm=ran_thresh)
                    best_xy, inliers_indices = ransac.fit(coords, rssis, model_params)
                    
                    if inliers_indices is not None and len(inliers_indices) > 0:
                        subset = cluster_df.iloc[inliers_indices]
                
                # Update Grid
                for _, row in subset.iterrows():
                    mx, my = grid.latlon_to_xy(row["gps_lat"], row["gps_lon"])
                    # Simple weighted update (1.0 for now)
                    grid.update(mx, my, row["rssi_dbm"], model_params, weight=1.0)
                    
                # Detect single best peak
                peaks = grid.detect_peaks(max_peaks=1)
                best_peak = peaks[0] if peaks else None
                
                # Store Result
                # Try to get SSID or MAC description
                mac_col = "src_mac" if protocol == "wifi" else "address"
                if mac_col in cluster_df.columns:
                    mac_counts = cluster_df[mac_col].value_counts()
                    primary_mac = mac_counts.index[0] if not mac_counts.empty else "Unknown"
                else:
                    primary_mac = "Unknown"
                ssid = cluster_df['ssid'].mode()[0] if 'ssid' in cluster_df and not cluster_df['ssid'].mode().empty else ""
                label = f"Cluster {cid} ({ssid or primary_mac})"
                
                results[cid] = {
                    "prob_map": grid.get_probability_map(),
                    "peak": best_peak,
                    "label": label,
                    "bounds": bounds,
                    "params": model_params
                }
                progress_bar.progress((i + 1) / len(unique_clusters))
            
            st.session_state["multi_target_results"] = results
            st.session_state["grid_origin"] = (origin_lat, origin_lon)
            
    # Visualization Controls
    if st.session_state["multi_target_results"]:
        results = st.session_state["multi_target_results"]
        origin = st.session_state.get("grid_origin", (valid_df["gps_lat"].mean(), valid_df["gps_lon"].mean()))
        
        # Selector
        all_cids = list(results.keys())
        st.sidebar.markdown("### 🎯 Active Targets")

        if "loc_cluster_selector" not in st.session_state:
            st.session_state["loc_cluster_selector"] = all_cids
        
        c_s1, c_s2 = st.sidebar.columns(2)
        if c_s1.button("Select All", key="loc_sel_all"):
            st.session_state["loc_cluster_selector"] = all_cids
            st.rerun()
        if c_s2.button("Deselect All", key="loc_desel_all"):
            st.session_state["loc_cluster_selector"] = []
            st.rerun()
        
        # Format labels for selector
        format_func = lambda x: results[x]['label']
        selected_cids = st.sidebar.multiselect("Select Clusters", all_cids, format_func=format_func, key="loc_cluster_selector")
            
        # Legend / Info Table
        if selected_cids:
            table_data = []
            for cid in selected_cids:
                res = results[cid]
                peak = res['peak']
                lat = f"{peak['lat']:.5f}" if peak else "N/A"
                lon = f"{peak['lon']:.5f}" if peak else "N/A"
                conf = f"{peak['confidence']:.2f}" if peak else "0.0"
                table_data.append({
                    "Cluster": res['label'],
                    "Lat": lat,
                    "Lon": lon,
                    "Conf": conf
                })
            st.table(pd.DataFrame(table_data))
            
            # Prepare Layers for Renderer
            layers = []
            color_cycle = ['jet', 'viridis', 'plasma', 'inferno', 'magma']
            for i, cid in enumerate(selected_cids):
                res = results[cid]
                layers.append({
                    'data': res['prob_map'],
                    'bounds': res['bounds'],
                    'label': res['label'],
                    'peak': res['peak'],
                    'color_map': color_cycle[i % len(color_cycle)]
                })
                
            gt = st.session_state.get("ground_truth_location")
            _render_heatmap(layers, origin[0], origin[1], show_grid=show_grid, resolution_m=res_m, ground_truth=gt)
            
        else:
            st.info("Select clusters from the sidebar to visualize.")
    else:
        st.info("Click 'Compute Multi-Target Localization' to start.")




def render_blank_placeholder():
    st.info("Localization view is disabled for this layout.")
