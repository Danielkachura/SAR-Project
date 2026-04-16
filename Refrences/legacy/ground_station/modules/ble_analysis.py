"""
BLE-specific analysis and visualization for vis_app.
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from typing import List, Optional, Tuple
from core.shared_utils import get_mac_column, is_randomized_mac, resolve_vendor


def apply_ble_filters(
    df: pd.DataFrame,
    rssi_range: Tuple[int, int],
    selected_event_types: List[str],
    selected_companies: List[str],
    tx_power_range: Optional[Tuple[int, int]],
    address_type_filter: Optional[List[str]],
    min_packets: int,
    selected_macs: List[str],
    mac_filter_mode: str = "Exclude"
) -> pd.DataFrame:
    """
    Apply BLE-specific filters to DataFrame.
    """
    if df.empty:
        return df
    
    # Separate Heartbeats
    is_heartbeat = df["event_type"] == "heartbeat" if "event_type" in df.columns else pd.Series(False, index=df.index)
    heartbeats = df[is_heartbeat].copy()
    others = df[~is_heartbeat].copy()
    
    selected_macs = selected_macs or []
    
    # Base mask: RSSI range for Others
    mask = (
        (others['rssi_dbm'] >= rssi_range[0]) &
        (others['rssi_dbm'] <= rssi_range[1])
    )

    # MAC filtering
    if selected_macs:
        if mac_filter_mode == "Include":
            mask = mask & others['address'].isin(selected_macs)
        else: # Exclude
            mask = mask & (~others['address'].isin(selected_macs))
    
    # Event type filter
    if selected_event_types:
        mask = mask & others['event_type'].isin(selected_event_types)
    
    # Company filter
    if selected_companies:
        mask = mask & others['company_name'].isin(selected_companies)
    
    # TX power filter
    if tx_power_range and 'tx_power' in others.columns:
        tx_mask = others['tx_power'].notna()
        tx_mask = tx_mask & (others['tx_power'] >= tx_power_range[0]) & (others['tx_power'] <= tx_power_range[1])
        mask = mask & (tx_mask | others['tx_power'].isna())  # Allow missing TX power
    
    # Address type filter
    if address_type_filter and 'address_type' in others.columns:
        mask = mask & others['address_type'].isin(address_type_filter)
    
    filtered_others = others[mask].copy()
    
    # Min packets filter (per MAC) for others
    if min_packets > 1:
        counts = filtered_others['address'].value_counts()
        valid_macs = counts[counts >= min_packets].index
        filtered_others = filtered_others[filtered_others['address'].isin(valid_macs)]
    
    return pd.concat([filtered_others, heartbeats])


def create_device_summary(df: pd.DataFrame) -> pd.DataFrame:
    """
    Create per-device summary statistics for BLE.
    """
    if df.empty:
        return pd.DataFrame()
    
    # Group by MAC address
    grouped = df.groupby('address')
    
    summary = pd.DataFrame({
        'address': grouped.size().index,
        'packets': grouped.size().values,
        'rssi_mean': grouped['rssi_dbm'].mean().round(1).values,
        'rssi_std': grouped['rssi_dbm'].std().round(1).fillna(0).values,
        'rssi_min': grouped['rssi_dbm'].min().values,
        'rssi_max': grouped['rssi_dbm'].max().values,
    })
    
    # Duration
    if 'timestamp_utc' in df.columns:
        duration = grouped['timestamp_utc'].agg(lambda x: (x.max() - x.min()).total_seconds())
        summary['duration_sec'] = duration.round(1).values
    else:
        summary['duration_sec'] = 0
    
    # Event types
    event_types = grouped['event_type'].apply(lambda x: ', '.join(x.value_counts().index[:3]))
    summary['event_types'] = event_types.values
    
    # Company
    if 'company_name' in df.columns:
        companies = grouped['company_name'].apply(lambda x: x.mode()[0] if not x.mode().empty else '')
        summary['company'] = companies.values
    else:
        summary['company'] = ''
    
    # Address type
    if 'address_type' in df.columns:
        addr_types = grouped['address_type'].apply(lambda x: x.mode()[0] if not x.mode().empty else '')
        summary['address_type'] = addr_types.values
    else:
        summary['address_type'] = ''
    
    # TX power stats
    if 'tx_power' in df.columns:
        tx_counts = grouped['tx_power'].apply(lambda x: x.notna().sum())
        tx_mean = grouped['tx_power'].mean().round(1)
        summary['tx_power_mean'] = tx_mean.values
        summary['tx_power_count'] = tx_counts.values
    
    # Flags
    if 'flags' in df.columns:
        flags = grouped['flags'].apply(lambda x: x.mode()[0] if not x.mode().empty and x.notna().any() else '')
        summary['flags'] = flags.values
    
    # Randomization detection
    summary['is_randomized'] = summary['address'].apply(is_randomized_mac)
    summary['mac_type'] = summary['is_randomized'].map({True: '🎲 Random', False: '🔒 Fixed'})
    
    # Sort by packet count
    summary = summary.sort_values('packets', ascending=False).reset_index(drop=True)
    
    return summary


def render_ble_overview(df: pd.DataFrame):
    """
    Render overview metrics and charts for BLE data.
    """
    st.subheader("📊 Overview")
    
    if df.empty:
        st.info("No data to display after filtering")
        return
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Packets", len(df))
    
    with col2:
        unique_devices = df['address'].nunique()
        st.metric("Unique Devices", unique_devices)
    
    with col3:
        avg_rssi = df['rssi_dbm'].mean()
        st.metric("Avg RSSI", f"{avg_rssi:.1f} dBm")
    
    with col4:
        if 'company_name' in df.columns:
            unique_companies = df['company_name'].nunique()
            st.metric("Companies", unique_companies)
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        # Event type distribution
        if 'event_type' in df.columns:
            st.markdown("##### Event Type Distribution")
            event_counts = df['event_type'].value_counts().reset_index()
            event_counts.columns = ['Event Type', 'Count']
            
            chart = alt.Chart(event_counts).mark_bar().encode(
                x=alt.X('Event Type:N', title='Event Type'),
                y=alt.Y('Count:Q', title='Packet Count'),
                color=alt.Color('Event Type:N', legend=None)
            ).properties(
                height=250
            )
            st.altair_chart(chart, use_container_width=True)
    
    with col2:
        # Company distribution (top 10)
        if 'company_name' in df.columns:
            st.markdown("##### Top 10 Companies")
            company_counts = df['company_name'].value_counts().head(10).reset_index()
            company_counts.columns = ['Company', 'Count']
            
            chart = alt.Chart(company_counts).mark_bar().encode(
                x=alt.X('Count:Q', title='Packet Count'),
                y=alt.Y('Company:N', sort='-x', title='Company'),
                color=alt.Color('Company:N', legend=None)
            ).properties(
                height=250
            )
            st.altair_chart(chart, use_container_width=True)


def render_ble_device_analysis(df: pd.DataFrame, summary: pd.DataFrame, selected_macs: List[str]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Render device analysis section with summary table and detail view.
    
    Returns:
        (filtered_summary, selected_macs)
    """
    st.subheader("📱 Device Analysis")
    
    if summary.empty:
        st.info("No devices to display")
        return summary, selected_macs
    
    # Display columns selector
    display_cols = ['address', 'packets', 'rssi_mean', 'rssi_std', 'duration_sec', 
                    'event_types', 'company', 'address_type', 'mac_type']
    
    if 'tx_power_mean' in summary.columns:
        display_cols.append('tx_power_mean')
    
    if 'flags' in summary.columns:
        display_cols.append('flags')
    
    # Filter to available columns
    display_cols = [c for c in display_cols if c in summary.columns]
    
    # Device selector for filtering
    st.markdown("**Select devices to view details:**")
    all_macs = summary['address'].tolist()
    
    selected_macs = st.multiselect(
        "Devices",
        options=all_macs,
        default=selected_macs if selected_macs else [],
        format_func=lambda mac: f"{mac} ({summary[summary['address']==mac]['packets'].iloc[0]} pkts)",
        key="ble_device_selector"
    )
    
    # Display summary table
    st.dataframe(
        summary[display_cols],
        use_container_width=True,
        height=400
    )
    
    # Download button
    csv = summary.to_csv(index=False)
    st.download_button(
        label="📥 Download Device Summary",
        data=csv,
        file_name="ble_device_summary.csv",
        mime="text/csv"
    )
    
    # Detailed packet view for selected devices
    if selected_macs:
        st.markdown("---")
        st.markdown(f"**Packet Details for {len(selected_macs)} Selected Device(s):**")
        
        detail_df = df[df['address'].isin(selected_macs)].copy()
        
        if not detail_df.empty:
            # Select relevant columns for display
            detail_cols = ['timestamp_utc', 'address', 'rssi_dbm', 'event_type', 
                          'company_name', 'address_type']
            
            if 'tx_power' in detail_df.columns:
                detail_cols.append('tx_power')
            if 'flags' in detail_df.columns:
                detail_cols.append('flags')
            if 'adv_data_hex' in detail_df.columns:
                detail_cols.append('adv_data_hex')
            
            # Filter to available columns
            detail_cols = [c for c in detail_cols if c in detail_df.columns]
            
            st.dataframe(
                detail_df[detail_cols].sort_values('timestamp_utc', ascending=False),
                use_container_width=True,
                height=400
            )
            
            # Download detailed data
            detail_csv = detail_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Packet Details",
                data=detail_csv,
                file_name="ble_packet_details.csv",
                mime="text/csv",
                key="download_ble_details"
            )
    
    return summary, selected_macs


def render_ble_filters(df: pd.DataFrame) -> dict:
    """
    Render BLE-specific filter controls in sidebar.
    
    Returns:
        dict with filter values
    """
    st.sidebar.markdown("### 🔍 BLE Filters")
    
    filters = {}
    
    # RSSI range
    if not df.empty and 'rssi_dbm' in df.columns and df['rssi_dbm'].notna().any():
        rssi_min = int(df['rssi_dbm'].min())
        rssi_max = int(df['rssi_dbm'].max())
        
        # Handle case where min == max (slider needs difference)
        if rssi_min == rssi_max:
             rssi_min -= 10
             rssi_max += 10
             
        filters['rssi_range'] = st.sidebar.slider(
            "RSSI Range (dBm)",
            rssi_min, rssi_max,
            (rssi_min, rssi_max),
            key="ble_rssi_range",
            help="Filter packets by signal strength. Lower is weaker."
        )
    else:
        filters['rssi_range'] = (-100, 0)
    
    # Event type filter
    if 'event_type' in df.columns:
        event_types = sorted(df['event_type'].dropna().unique())
        filters['event_types'] = st.sidebar.multiselect(
            "Event Types",
            options=event_types,
            default=[],
            key="ble_event_types",
            help="Filter by BLE advertisement type (e.g. ADV_IND)."
        )
    else:
        filters['event_types'] = []
    
    # Company filter
    if 'company_name' in df.columns:
        companies = sorted(df['company_name'].dropna().unique())
        filters['companies'] = st.sidebar.multiselect(
            "Companies",
            options=companies,
            default=[],
            key="ble_companies",
            help="Filter by company ID/Name in advertisement data."
        )
    else:
        filters['companies'] = []
    
    # TX power filter
    if 'tx_power' in df.columns and df['tx_power'].notna().any():
        tx_min = int(df['tx_power'].min())
        tx_max = int(df['tx_power'].max())
        use_tx_filter = st.sidebar.checkbox("Filter by TX Power", key="ble_use_tx", help="Enable filtering by Transmission Power Level.")
        if use_tx_filter:
            filters['tx_power_range'] = st.sidebar.slider(
                "TX Power Range (dBm)",
                tx_min, tx_max,
                (tx_min, tx_max),
                key="ble_tx_range",
                help="Filter devices by their broadcasted TX Power."
            )
        else:
            filters['tx_power_range'] = None
    else:
        filters['tx_power_range'] = None
    
    # Address type filter
    if 'address_type' in df.columns:
        addr_types = sorted(df['address_type'].dropna().unique())
        filters['address_types'] = st.sidebar.multiselect(
            "Address Types",
            options=addr_types,
            default=[],
            key="ble_addr_types",
            help="Filter by address type (Public, Random, etc)."
        )
    else:
        filters['address_types'] = []
    
    # Min packets threshold
    filters['min_packets'] = st.sidebar.slider(
        "Min Packets per Device",
        1, 50, 1,
        key="ble_min_packets",
        help="Exclude devices with fewer than N packets."
    )
    
    # MAC filtering
    if not df.empty:
        all_macs = df['address'].value_counts()
        
        sort_by = st.sidebar.radio("Sort Devices by", ["Packets", "MAC Address", "Name"], index=0, horizontal=True, key="ble_device_sort", help="Sort order for the device list below.")
        
        # Prepare list for sorting
        mac_data = []
        for mac, count in all_macs.items():
            company = "Unknown"
            if 'company_name' in df.columns:
                c_series = df[df['address'] == mac]['company_name'].dropna()
                if not c_series.empty:
                    company = c_series.iloc[0]
            mac_data.append({"mac": mac, "count": count, "company": company})

        if sort_by == "Packets":
            mac_data.sort(key=lambda x: x["count"], reverse=True)
        elif sort_by == "MAC Address":
            mac_data.sort(key=lambda x: x["mac"])
        elif sort_by == "Name":
            mac_data.sort(key=lambda x: (x["company"].lower(), x["mac"]))

        mac_options = [f"{d['mac']} ({d['count']} pkts, {d['company']})" for d in mac_data]
        
        mode = st.sidebar.radio("MAC Filter Mode", ["Include", "Exclude"], index=1, key="ble_mac_mode", help="Include or Exclude the selected devices.")
        filters['mac_filter_mode'] = mode

        selected = st.sidebar.multiselect(
            f"{mode} Devices",
            options=mac_options,
            default=[],
            key="ble_selected_macs",
            help="Select specific devices to filter."
        )
        
        filters['selected_macs'] = [opt.split(' (')[0] for opt in selected]
    else:
        filters['mac_filter_mode'] = "Exclude"
        filters['selected_macs'] = []
    
    return filters
