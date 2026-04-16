"""Entry point for the modular Streamlit app."""

from __future__ import annotations

from pathlib import Path
import os
import streamlit as st
import pandas as pd

from core.data_manager import DATA_DIR, Dataset, list_scan_folders, list_csv_files, load_dataset
from modules import filters as filter_module
from modules import map_viewer, localization_view, reid_interface, ble_analysis

st.set_page_config(layout="wide", page_title="Wireless Signal Analysis")


def _select_data() -> Dataset:
    st.sidebar.header("📂 Data Source")

    folders = list_scan_folders()
    if not folders:
        st.error(f"No data folders found under {DATA_DIR}")
        st.stop()

    # Initial Folder Logic
    query_folder = st.query_params.get("folder")
    f_idx = 0
    if query_folder:
        for i, f in enumerate(folders):
            if f.name == query_folder:
                f_idx = i
                break

    folder = st.sidebar.selectbox("Select Folder", folders, format_func=lambda p: p.name, key="folder_select_box", index=f_idx)
    st.query_params["folder"] = folder.name

    files_map = list_csv_files(folder)
    if not files_map:
        st.error("No CSV files in the selected folder.")
        st.stop()

    file_labels = list(files_map.keys())
    
    # Initial File Logic
    query_file = st.query_params.get("file")
    file_idx = 0
    if query_file and query_file in file_labels:
        file_idx = file_labels.index(query_file)

    file_label = st.sidebar.selectbox("Select File", file_labels, index=file_idx, key="file_select_box")
    st.query_params["file"] = file_label
    file_path = files_map[file_label]

    # Auto-prefer enriched if available
    target_path = file_path.with_name(file_path.stem + "_enriched.csv")
    prefer_enriched = target_path.exists()

    if prefer_enriched:
        stat = target_path.stat()
        file_sig = (stat.st_mtime, stat.st_size)
    else:
        file_sig = None

    dataset = load_dataset(str(file_path), prefer_enriched=prefer_enriched, file_sig=file_sig)
    return dataset


def _overview(df: pd.DataFrame, protocol: str):
    if protocol == "ble":
        ble_analysis.render_ble_overview(df)
        _render_file_preview(df)
        st.markdown("---")
        summary = ble_analysis.create_device_summary(df)
        if not summary.empty:
            ble_analysis.render_ble_device_analysis(df, summary, [])
        return

    st.subheader("📊 Overview")
    if df.empty:
        st.info("No data after filtering")
        return
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Packets", len(df))
    mac_col = "src_mac" if protocol == "wifi" else "address"
    col2.metric("Unique Devices", df[mac_col].nunique() if mac_col in df.columns else 0)
    col3.metric("Avg RSSI", f"{df['rssi_dbm'].mean():.1f} dBm")
    if "channel" in df.columns:
        col4.metric("Channels", df["channel"].nunique())
    elif "company_name" in df.columns:
        col4.metric("Companies", df["company_name"].nunique())

    _render_file_preview(df)


def _render_file_preview(df: pd.DataFrame):
    st.subheader("📂 File Preview")
    if df.empty:
        st.warning("No data available to preview.")
        return
    
    st.dataframe(df, use_container_width=True, height=300)


def main():
    st.title("📡 Wireless Signal Analysis (Modular)")

    dataset = _select_data()
    st.sidebar.info(f"Protocol: {dataset.protocol.upper() if dataset.protocol else 'UNKNOWN'}")

    if dataset.error:
        st.error(dataset.error)
        st.stop()

    # Navigation
    sections = ["Overview", "Map", "Localization", "Calibration", "Ground Truth", "Re-ID"]
    
    # Initial Section Logic
    query_section = st.query_params.get("section")
    s_idx = 0
    if query_section in sections:
        s_idx = sections.index(query_section)

    section = st.sidebar.radio("Navigate", sections, index=s_idx, key="nav_section_radio", help="Navigate between different analysis modules.")
    st.query_params["section"] = section

    # Filters
    filters = filter_module.render(dataset.data, dataset.protocol)
    filtered = filter_module.apply_filters(dataset.data, dataset.protocol, filters) if filters else dataset.data

    # Main body by section
    if section == "Overview":
        _overview(filtered, dataset.protocol)
    elif section == "Map":
        mac_col = "src_mac" if dataset.protocol == "wifi" else "address"
        selected_macs = []
        if mac_col in filtered.columns:
            st.markdown("**Focus devices (optional):**")
            selected_macs = st.multiselect("Devices", filtered[mac_col].unique().tolist())
        map_viewer.render(filtered, dataset.protocol, selected_macs=selected_macs, show_packets=True)
    elif section == "Localization":
        localization_view.render(filtered, dataset.protocol)
    elif section == "Calibration":
        from modules import calibration
        calibration.render(filtered, dataset.protocol)
    elif section == "Ground Truth":
        from modules import ground_truth
        ground_truth.render()
    elif section == "Re-ID":
        reid_interface.render(dataset, filtered)


if __name__ == "__main__":
    main()
