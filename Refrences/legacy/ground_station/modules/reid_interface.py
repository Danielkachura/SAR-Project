"""Wrapper UI for Re-ID and enrichment actions."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from core.data_manager import Dataset, enrich_csv

try:
    from reid.pipeline import cluster_scan_df, apply_clusters_to_df, generate_localization_export, resolve_mac_conflicts  # type: ignore
except Exception:  # pragma: no cover
    cluster_scan_df = None
    apply_clusters_to_df = None
    generate_localization_export = None
    resolve_mac_conflicts = None


def render(dataset: Dataset, filtered_df: Optional[pd.DataFrame] = None):
    st.subheader("🧩 Re-ID & Enrichment")

    if dataset.error:
        st.warning(dataset.error)
        return

    col1, col2 = st.columns(2)

    with col1:
        if st.button("Enrich CSV with PCAP", type="primary"):
            out_path, log_text = enrich_csv(dataset.source_path)
            if out_path:
                st.success(f"Enriched file written to {out_path.name}")
                if log_text:
                    st.text_area("Enrichment log", log_text, height=200)
            else:
                st.error(log_text or "Enrichment failed")

    with col2:
        if cluster_scan_df is None or apply_clusters_to_df is None:
            st.info("Re-ID clustering not available in this environment.")
        else:
            st.caption("Cluster MACs using Bleach-style pairing.")
            if st.button("Run Re-ID", key="reid_run_btn"):
                if filtered_df is None or filtered_df.empty:
                    st.warning("No data available to cluster.")
                else:
                    with st.spinner("Running Re-ID Clustering..."):
                        # Use confidence=True to enable Hardware Signature logic
                        cluster_result, summary = cluster_scan_df(filtered_df, use_confidence=True)
                        df_with_clusters = apply_clusters_to_df(filtered_df, cluster_result)
                        
                        # Apply Conflict Resolution
                        if resolve_mac_conflicts:
                            df_with_clusters = resolve_mac_conflicts(df_with_clusters)
                        
                        # Determine output path based on original filename if possible
                        # The dataset object has 'source_path'
                        try:
                            source_path = dataset.source_path
                            stem = source_path.stem.replace("_enriched", "")
                            output_filename = f"{stem}_reid.csv"
                            output_path = source_path.parent / output_filename
                            
                            # Save Re-ID output
                            df_with_clusters.to_csv(output_path, index=False)
                            
                            # Generate Localization Export
                            if generate_localization_export:
                                generate_localization_export(df_with_clusters, str(output_path))
                            
                            # Calculate Stats
                            num_unique_macs = df_with_clusters['src_mac'].nunique()
                            valid_clusters = df_with_clusters[df_with_clusters['cluster_id'] != -1]
                            num_clusters = valid_clusters['cluster_id'].nunique()
                            
                            st.success(f"Clustered {num_unique_macs} unique MACs to {num_clusters} clusters.")
                            st.info(f"Saved Re-ID output to: `{output_filename}`")
                            st.info(f"Saved Localization input to: `localization_input.csv`")
                            
                        except Exception as e:
                            st.error(f"Analysis complete but failed to save files: {e}")

                    st.dataframe(df_with_clusters[[c for c in df_with_clusters.columns if c in ['src_mac', 'cluster_id', 'rssi_dbm', 'timestamp_utc']]].head(200), use_container_width=True)


def render_blank_placeholder():
    st.info("Re-ID module is disabled for this view.")
