"""Module for managing Ground Truth (Real) emitter locations."""

from __future__ import annotations
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from pathlib import Path
import numpy as np

from core.shared_utils import get_mac_column, haversine_distance

from core.data_manager import list_scan_folders, list_csv_files

GT_COLORS = ['green', 'red', 'blue', 'orange', 'purple', 'darkred', 'cadetblue', 'darkgreen', 'darkblue', 'black']

def render():
    st.subheader("📍 Ground Truth Management")
    
    # Initialize list if not present
    if "ground_truth_list" not in st.session_state:
        st.session_state["ground_truth_list"] = []
        
        # Migration from old single-item state if exists
        if "ground_truth_location" in st.session_state:
            old_gt = st.session_state["ground_truth_location"]
            # Add color field
            old_gt["color"] = GT_COLORS[0]
            st.session_state["ground_truth_list"].append(old_gt)
            del st.session_state["ground_truth_location"]
            
        # Check URL params (legacy single item support -> add to list)
        qs = st.query_params
        if "gt_lat" in qs and "gt_lon" in qs and "gt_mac" in qs:
            try:
                lat = float(qs["gt_lat"])
                lon = float(qs["gt_lon"])
                mac = qs["gt_mac"]
                # Check if already in list to avoid duplicates on reload
                exists = any(gt['mac'] == mac and gt['lat'] == lat for gt in st.session_state["ground_truth_list"])
                if not exists:
                    st.session_state["ground_truth_list"].append({
                        "lat": lat,
                        "lon": lon,
                        "mac": mac,
                        "label": "Real Location",
                        "color": GT_COLORS[len(st.session_state["ground_truth_list"]) % len(GT_COLORS)]
                    })
            except ValueError:
                pass

    st.markdown("""
    Define **Real Locations** of emitters to verify accuracy. 
    You can add multiple ground truth points.
    """)

    # Mode Selection
    gt_mode = st.radio("Selection Mode", ["From File", "Manual Selection"], horizontal=True, help="Choose how to define the ground truth location.")

    if gt_mode == "From File":
        # File Selector Logic (Replacing Uploader)
        current_folder_name = st.query_params.get("folder")
        folders = list_scan_folders()
        current_folder = next((f for f in folders if f.name == current_folder_name), None)
        
        # Fallback to first folder if current not found
        if not current_folder and folders:
            current_folder = folders[0]
            
        uploaded_file = None
        if current_folder:
            st.write(f"**Source Folder:** `{current_folder.name}`")
            files_map = list_csv_files(current_folder)
            file_options = list(files_map.keys())
            
            selected_label = st.selectbox("Select File", ["(None)"] + file_options, key="gt_file_selector")
            if selected_label != "(None)":
                uploaded_file = files_map[selected_label]
        else:
            st.error("No data folders available.")
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                df.columns = df.columns.str.strip().str.lower()
                
                # Detect MAC column
                mac_col = None
                if 'address' in df.columns: mac_col = 'address'
                elif 'src_mac' in df.columns: mac_col = 'src_mac'
                elif 'mac' in df.columns: mac_col = 'mac'
                
                if not mac_col:
                    st.error("Could not find a MAC address column (address, src_mac, or mac).")
                    return

                if 'gps_lat' not in df.columns or 'gps_lon' not in df.columns:
                    st.error("CSV must contain 'gps_lat' and 'gps_lon' columns.")
                    return

                # Clean data
                df = df.dropna(subset=['gps_lat', 'gps_lon'])
                df = df[(df['gps_lat'] != 0) & (df['gps_lon'] != 0)]
                
                if df.empty:
                    st.warning("No valid GPS data found in the uploaded file.")
                    return

                # Device selection
                mac_counts = df[mac_col].value_counts()
                
                col1, col2 = st.columns([2, 1])
                sort_by = col2.radio("Sort by", ["Packets", "Address"], index=0, horizontal=True)
                
                mac_list = list(mac_counts.items())
                if sort_by == "Packets":
                    mac_list.sort(key=lambda x: x[1], reverse=True)
                else:
                    mac_list.sort(key=lambda x: x[0])
                    
                options = [f"{m} ({c} pkts)" for m, c in mac_list]
                selected_opt = col1.selectbox("Select Target Device (Real Emitter)", options)
                target_mac = selected_opt.split(" (")[0]
                
                # Calculate average location
                subset = df[df[mac_col] == target_mac]
                avg_lat = subset['gps_lat'].mean()
                avg_lon = subset['gps_lon'].mean()
                std_lat = subset['gps_lat'].std() * 111320 # approx meters
                std_lon = subset['gps_lon'].std() * 111320 * np.cos(np.radians(avg_lat))
                
                st.info(f"**Averaged Location for {target_mac}:**  \n`{avg_lat:.7f}, {avg_lon:.7f}` (Spread: ~{max(std_lat, std_lon):.1f}m)")
                
                def_idx = len(st.session_state["ground_truth_list"]) % len(GT_COLORS)
                selected_color = st.selectbox("Marker Color", GT_COLORS, index=def_idx, key="gt_color_file")
                
                if st.button("Add as Ground Truth", type="primary"):
                    st.session_state["ground_truth_list"].append({
                        "lat": avg_lat,
                        "lon": avg_lon,
                        "mac": target_mac,
                        "label": "Real Location",
                        "color": selected_color
                    })
                    st.success(f"Added Ground Truth ({selected_color})!")
                    st.rerun()

            except Exception as e:
                st.error(f"Error processing CSV: {e}")

    else: # Manual Selection
        st.info("Click on map + 'Add Selected Point' to add a ground truth.")
        
        # Default start center (Use last added GT or some default)
        start_loc = [32.0, 34.8] # Default
        if st.session_state["ground_truth_list"]:
            last = st.session_state["ground_truth_list"][-1]
            start_loc = [last["lat"], last["lon"]]
            
        m = folium.Map(location=start_loc, zoom_start=18, max_zoom=24)
        folium.TileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri", 
            name="Esri Satellite",
            max_zoom=24,
            max_native_zoom=18
        ).add_to(m)
        
        # Draw EXISTING ground truths
        for gt in st.session_state["ground_truth_list"]:
            folium.Marker(
                [gt['lat'], gt['lon']], 
                tooltip=f"GT: {gt['mac']}",
                icon=folium.Icon(color=gt.get('color', 'green'), icon="crosshairs", prefix="fa")
            ).add_to(m)

        # Check for persisted temporary point
        if "gt_manual_temp" not in st.session_state:
            st.session_state["gt_manual_temp"] = None

        # Display marker if a point is selected
        if st.session_state["gt_manual_temp"]:
            temp_pt = st.session_state["gt_manual_temp"]
            folium.Marker(
                [temp_pt["lat"], temp_pt["lon"]],
                tooltip="New Selection",
                icon=folium.Icon(color="gray", icon="question", prefix="fa")
            ).add_to(m)
        
        output = st_folium(m, width="100%", height=500, key="manual_gt_map")
        
        # Capture click and update temp state
        if output and output.get("last_clicked"):
            lat = output["last_clicked"]["lat"]
            lon = output["last_clicked"]["lng"]
            
            # Update only if changed to avoid unnecessary reruns
            st.session_state["gt_manual_temp"] = {"lat": lat, "lon": lon}
            st.rerun()

        # Render Button based on PERSISTED state
        if st.session_state["gt_manual_temp"]:
            temp_pt = st.session_state["gt_manual_temp"]
            st.write(f"**Selected Point:** `{temp_pt['lat']:.7f}, {temp_pt['lon']:.7f}`")
            
            def_idx = len(st.session_state["ground_truth_list"]) % len(GT_COLORS)
            selected_color = st.selectbox("Marker Color", GT_COLORS, index=def_idx, key="gt_color_manual")
            
            if st.button("Add Selected Point", type="primary"):
                st.session_state["ground_truth_list"].append({
                    "lat": temp_pt['lat'],
                    "lon": temp_pt['lon'],
                    "mac": "Manual Selection",
                    "label": "Manual GT",
                    "color": selected_color
                })
                
                # Clear temp point after setting
                del st.session_state["gt_manual_temp"]
                
                st.success(f"Added Manual Ground Truth ({selected_color})!")
                st.rerun()

    # Display Active Ground Truths Table
    st.markdown("---")
    st.markdown("### ✅ Active Ground Truths")
    
    if st.session_state["ground_truth_list"]:
        # Create a df for nicer display
        gt_display = []
        for i, gt in enumerate(st.session_state["ground_truth_list"]):
            gt_display.append({
                "Index": i,
                "MAC / Label": gt['mac'],
                "Lat": f"{gt['lat']:.6f}",
                "Lon": f"{gt['lon']:.6f}",
                "Color": gt.get('color', 'green')
            })
        
        st.dataframe(pd.DataFrame(gt_display).set_index("Index"), use_container_width=True)

        col_c1, col_c2 = st.columns([1, 1])
        with col_c1:
            if st.button("Clear All Ground Truths"):
                st.session_state["ground_truth_list"] = []
                # Clear URL params
                if "gt_lat" in st.query_params: del st.query_params["gt_lat"]
                if "gt_lon" in st.query_params: del st.query_params["gt_lon"]
                if "gt_mac" in st.query_params: del st.query_params["gt_mac"]
                st.rerun()
        with col_c2:
            to_remove = st.selectbox("Remove specific GT", options=range(len(gt_display)), format_func=lambda i: f"{gt_display[i]['MAC / Label']} ({gt_display[i]['Color']})")
            if st.button("Remove Selected"):
                st.session_state["ground_truth_list"].pop(to_remove)
                st.rerun()
    else:
        st.info("No ground truths defined.")
