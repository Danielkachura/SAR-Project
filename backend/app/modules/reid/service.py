from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median

import pandas as pd

from app.core.errors import ValidationError
from app.models.canonical_models import (
    ProtocolMode,
    ReIdConfidenceBand,
    ReIdConfidenceDistributionItem,
    ReIdMethod,
    ReIdMethodDistributionItem,
    ReIdParameters,
    ReIdQualityStats,
    ReIdRunPayload,
)
from app.modules.dataset_discovery.service import DatasetDiscoveryService
from app.modules.session_navigation.service import SessionNavigationService

_REQUIRED_REID_COLUMNS = [
    "cluster_id",
    "cluster_type",
]


@dataclass
class _Assignment:
    cluster_id: str
    cluster_type: str
    confidence_score: float
    confidence_band: ReIdConfidenceBand
    method: ReIdMethod
    evidence: str
    warning: str


def _norm_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "" if text in {"", "nan", "none"} else text


def _parse_ts_ms(value: object) -> float | None:
    if value is None:
        return None
    ts = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(ts):
        return None
    return float(ts.value / 1_000_000)


def _confidence_band(score: float) -> ReIdConfidenceBand:
    if score >= 0.85:
        return ReIdConfidenceBand.HIGH
    if score >= 0.7:
        return ReIdConfidenceBand.MEDIUM
    return ReIdConfidenceBand.LOW


class ReIdService:
    def __init__(
        self,
        session_service: SessionNavigationService,
        dataset_service: DatasetDiscoveryService,
    ) -> None:
        self._session_service = session_service
        self._dataset_service = dataset_service

    def run_reid(
        self,
        session_id: str,
        parameters: ReIdParameters,
        selected_enriched_artifact_id: str | None = None,
    ) -> ReIdRunPayload:
        session = self._session_service.require_session(session_id)
        artifact_id = selected_enriched_artifact_id or session.active_enriched_artifact_id
        if artifact_id is None:
            raise ValidationError("Re-ID requires an active ENRICHED artifact.")

        inventory = self._dataset_service.resolve_inventory(session.scan_folder_id)
        artifact = next((a for a in inventory.enriched_artifacts if a.artifact_id == artifact_id), None)
        if artifact is None:
            raise ValidationError("Selected artifact is not a compatible ENRICHED artifact.")

        input_path = Path(artifact.path)
        if not input_path.exists():
            raise ValidationError(f"Active ENRICHED artifact not found on disk: {artifact.file_name}")

        df = pd.read_csv(input_path)
        if df.empty:
            raise ValidationError("ENRICHED artifact is empty; cannot run Re-ID.")
        original_columns = list(df.columns)

        # OPTIMIZATION: Convert to dict records once and process
        assignments = self._assign_clusters(df, protocol=session.mode, params=parameters)
        
        # Batch update the dataframe
        cluster_ids = [assignments[i].cluster_id for i in df.index]
        cluster_types = [assignments[i].cluster_type for i in df.index]
        df["cluster_id"] = cluster_ids
        df["cluster_type"] = cluster_types

        for col in _REQUIRED_REID_COLUMNS:
            if col not in df.columns:
                df[col] = pd.NA

        stem = artifact.file_name
        if stem.lower().endswith("_enriched.csv"):
            stem = stem[:-13]
        else:
            stem = Path(stem).stem
        output_name = f"{stem}_REID.csv"
        output_path = self._dataset_service.resolve_csv_path(session.scan_folder_id, output_name)
        tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
        df.to_csv(tmp_path, index=False)
        tmp_path.replace(output_path)

        output_artifact_id = f"{session.scan_folder_id}:{output_name}"
        self._session_service.activate_artifact(session_id=session_id, artifact_id=output_artifact_id)

        stats = self._compute_quality_stats(
            df,
            assignments,
        )

        warnings: list[str] = []
        if len(original_columns) + 2 != len(df.columns):
            warnings.append("Output schema contains unexpected additional columns.")

        return ReIdRunPayload(
            input_enriched_file=artifact.file_name,
            output_reid_file=output_name,
            protocol=session.mode,
            parameters=parameters,
            row_count=len(df),
            cluster_count=stats.cluster_count,
            quality_stats=stats,
            warnings=warnings,
        )

    def _assign_clusters(
        self,
        df: pd.DataFrame,
        protocol: ProtocolMode,
        params: ReIdParameters,
    ) -> dict[int, _Assignment]:
        assignments: dict[int, _Assignment] = {}
        # active_clusters: deque of (cluster_id, last_ts, last_representative_data)
        # We use a deque and ensure it stays sorted by timestamp so we can prune in O(1)
        from collections import deque
        active_clusters: deque[tuple[str, float, dict]] = deque()
        next_cluster_num = 1

        # Pre-convert to records and pre-calculate timestamps/types to avoid overhead in loop
        records = df.to_dict('records')
        indices = list(df.index)
        
        rows = []
        for i, idx in enumerate(indices):
            rec = records[i]
            ts = _parse_ts_ms(rec.get("timestamp_utc")) or 0.0
            ctype = self._cluster_type_for_row(rec)
            rows.append({
                "idx": idx,
                "ts": ts,
                "record": rec,
                "type": ctype
            })
        
        # Ensure chronological order
        rows.sort(key=lambda x: (x["ts"], x["idx"]))

        max_gap = params.max_time_gap_candidate_ms

        for i, row in enumerate(rows):
            idx = row["idx"]
            ts = row["ts"]
            rec = row["record"]
            row_type = row["type"]

            if i > 0 and i % 10000 == 0:
                print(f"[RE-ID] Processed {i}/{len(rows)} rows... (Active clusters: {len(active_clusters)})")

            # 1. Prune expired clusters (O(1) average)
            # Since we ensure active_clusters is sorted by last_ts, we only peek the front.
            while active_clusters and (ts - active_clusters[0][1]) > max_gap:
                active_clusters.popleft()

            best_cluster_id: str | None = None
            best_score = -1.0
            best_method = ReIdMethod.SINGLETON_INSUFFICIENT_EVIDENCE
            best_type = "dynamic"
            best_evidence = "insufficient"

            # 2. Compare against active candidates (O(active_C))
            for cluster_id, last_ts, last_rec in active_clusters:
                score, method, ctype, evidence_text = self._pair_score(
                    rec,
                    last_rec,
                    ts,
                    last_ts,
                    protocol=protocol,
                    params=params,
                )
                if score > best_score:
                    best_score = score
                    best_cluster_id = cluster_id
                    best_method = method
                    best_type = ctype
                    best_evidence = evidence_text

            # 3. Decision logic
            if (
                best_cluster_id
                and best_score >= params.protocol_global_min_merge_threshold
                and len(best_evidence.split("|")) >= params.minimum_evidence_for_non_singleton
            ):
                cluster_id = best_cluster_id
                # UPDATE AND RE-ORDER: to keep deque sorted by ts, we remove and re-add at the end
                # (Removing from middle of deque is O(C), but C is small here)
                for j in range(len(active_clusters)):
                    if active_clusters[j][0] == cluster_id:
                        del active_clusters[j]
                        break
                active_clusters.append((cluster_id, ts, rec))
                
                score = best_score
                method = best_method
                cluster_type = best_type
                evidence = best_evidence
                warning = ""
            else:
                cluster_id = f"c{next_cluster_num:05d}"
                next_cluster_num += 1
                active_clusters.append((cluster_id, ts, rec))
                score = 0.0 if best_score < 0 else min(best_score, 0.69)
                method = ReIdMethod.SINGLETON_INSUFFICIENT_EVIDENCE
                cluster_type = row_type
                evidence = "insufficient"
                warning = "singleton_due_to_low_evidence"

            assignments[idx] = _Assignment(
                cluster_id=cluster_id,
                cluster_type=cluster_type,
                confidence_score=score,
                confidence_band=_confidence_band(score),
                method=method,
                evidence=evidence,
                warning=warning,
            )

        return assignments

    def _cluster_type_for_row(self, row: dict | pd.Series) -> str:
        mac = _norm_text(row.get("src_mac"))
        if not mac or ":" not in mac:
            return "dynamic"
        try:
            if int(mac.split(":")[0], 16) & 0x02:
                return "dynamic"
            return "static"
        except (ValueError, IndexError):
            return "dynamic"

    def _pair_score(
        self,
        row: dict,
        representative: dict,
        row_ts: float,
        rep_ts: float,
        protocol: ProtocolMode,
        params: ReIdParameters,
    ) -> tuple[float, ReIdMethod, str, str]:
        delta_ms = abs(row_ts - rep_ts)
        if delta_ms > params.max_time_gap_candidate_ms:
            return 0.0, ReIdMethod.SINGLETON_INSUFFICIENT_EVIDENCE, "dynamic", "time_gap"

        # 1. Identity Check (MAC Bypass)
        mac_a = _norm_text(row.get("src_mac"))
        mac_b = _norm_text(representative.get("src_mac"))
        
        is_static_a = self._cluster_type_for_row(row) == "static"
        is_static_b = self._cluster_type_for_row(representative) == "static"
        
        # Static MAC Bypass: if it's the same static MAC, it's the same device.
        if mac_a and mac_b and mac_a == mac_b and is_static_a and is_static_b:
            return 1.0, ReIdMethod.WIFI_SEQUENCE_FINGERPRINT_MATCH if protocol == ProtocolMode.WIFI else ReIdMethod.BLE_ADVERTISING_SIGNATURE_MATCH, "static", "time|mac_static"

        time_score = max(0.0, 1.0 - delta_ms / params.max_time_gap_candidate_ms)
        evidence_bits = ["time"]
        
        # MAC match for dynamic/mixed provides strong but not absolute evidence in Forensic mode
        mac_match = 1.0 if (mac_a and mac_b and mac_a == mac_b) else 0.0
        if mac_match:
            evidence_bits.append("mac")

        if protocol == ProtocolMode.BLE:
            sig_keys = [
                "enr_ble_manufacturer_data",
                "enr_ble_service_uuids",
                "enr_ble_local_name",
                "enr_ble_vendor_company_id",
            ]
            signature_matches = 0
            for key in sig_keys:
                a = _norm_text(row.get(key))
                b = _norm_text(representative.get(key))
                if a and b and a == b:
                    signature_matches += 1
                    evidence_bits.append(key)

            context_matches = 0
            for key in ("enr_ble_event_type", "enr_ble_addr_type"):
                a = _norm_text(row.get(key))
                b = _norm_text(representative.get(key))
                if a and b and a == b:
                    context_matches += 1
                    evidence_bits.append(key)

            # Weighting: MAC (0.3), Time (0.2), Sig (0.3), Context (0.2)
            score = 0.30 * mac_match + 0.20 * time_score + 0.30 * (signature_matches / len(sig_keys)) + 0.20 * (context_matches / 2)
            method = (
                ReIdMethod.BLE_ADVERTISING_SIGNATURE_MATCH
                if signature_matches > 0 or mac_match > 0
                else ReIdMethod.BLE_CONTEXT_ONLY_MATCH
            )
            threshold = (
                params.ble_strong_merge_threshold
                if signature_matches >= 2 or mac_match > 0
                else params.ble_weak_context_merge_threshold
            )
        else:
            seq_a = row.get("enr_seq_num")
            seq_b = representative.get("enr_seq_num")
            sequence_score = 0.0
            if pd.notna(seq_a) and pd.notna(seq_b):
                try:
                    gap = abs(float(seq_a) - float(seq_b))
                    if gap <= params.wifi_sequence_gap_threshold:
                        sequence_score = max(0.0, 1.0 - gap / params.wifi_sequence_gap_threshold)
                        evidence_bits.append("seq")
                except Exception:
                    sequence_score = 0.0

            fp_match = 1.0 if _norm_text(row.get("enr_ie_fingerprint")) and _norm_text(row.get("enr_ie_fingerprint")) == _norm_text(representative.get("enr_ie_fingerprint")) else 0.0
            if fp_match:
                evidence_bits.append("fingerprint")
            vendor_match = 1.0 if _norm_text(row.get("enr_ie_vendor_ouis")) and _norm_text(row.get("enr_ie_vendor_ouis")) == _norm_text(representative.get("enr_ie_vendor_ouis")) else 0.0
            if vendor_match:
                evidence_bits.append("vendor")
            bssid_match = 1.0 if _norm_text(row.get("enr_bssid")) and _norm_text(row.get("enr_bssid")) == _norm_text(representative.get("enr_bssid")) else 0.0
            if bssid_match:
                evidence_bits.append("bssid")

            # Weighting: MAC (0.5), Time (0.3), Seq (0.1), FP (0.05), Vendor (0.02), BSSID (0.03)
            # This ensures a Time + MAC match yields 0.8, which crosses most thresholds.
            score = 0.50 * mac_match + 0.30 * time_score + 0.10 * sequence_score + 0.05 * fp_match + 0.02 * vendor_match + 0.03 * bssid_match
            
            if (sequence_score > 0 and fp_match > 0) or mac_match > 0:
                method = ReIdMethod.WIFI_SEQUENCE_FINGERPRINT_MATCH
            elif fp_match > 0:
                method = ReIdMethod.WIFI_FINGERPRINT_CONTEXT_MATCH
            else:
                method = ReIdMethod.WIFI_CONTEXT_ONLY_MATCH
                
            threshold = (
                params.wifi_strong_merge_threshold
                if (sequence_score > 0 and fp_match > 0) or mac_match > 0
                else params.wifi_weak_context_merge_threshold
            )

        if score < threshold:
            return score, ReIdMethod.SINGLETON_INSUFFICIENT_EVIDENCE, self._cluster_type_for_row(row), "|".join(evidence_bits)

        return score, method, self._cluster_type_for_row(row), "|".join(evidence_bits)

    def _compute_quality_stats(
        self,
        df: pd.DataFrame,
        assignments: dict[int, _Assignment],
    ) -> ReIdQualityStats:
        cluster_to_rows: dict[str, list[int]] = defaultdict(list)
        method_counter: Counter[ReIdMethod] = Counter()
        conf_counter: Counter[ReIdConfidenceBand] = Counter()

        for idx, assignment in assignments.items():
            cluster_to_rows[assignment.cluster_id].append(idx)
            method_counter[assignment.method] += 1
            conf_counter[assignment.confidence_band] += 1

        cluster_sizes = sorted(len(rows) for rows in cluster_to_rows.values())
        total_rows = len(df)
        cluster_count = len(cluster_sizes)
        singleton_count = sum(1 for size in cluster_sizes if size == 1)

        def _coverage(col: str) -> float:
            if col not in df.columns or total_rows == 0:
                return 0.0
            present = int(df[col].fillna("").astype(str).str.strip().ne("").sum())
            return round(present / total_rows, 4)

        confidence_distribution = [
            ReIdConfidenceDistributionItem(
                band=band,
                ratio=round(conf_counter[band] / total_rows, 4) if total_rows else 0.0,
            )
            for band in (ReIdConfidenceBand.HIGH, ReIdConfidenceBand.MEDIUM, ReIdConfidenceBand.LOW)
        ]
        method_distribution = [
            ReIdMethodDistributionItem(
                method=method,
                ratio=round(count / total_rows, 4) if total_rows else 0.0,
            )
            for method, count in sorted(method_counter.items(), key=lambda item: item[0].value)
        ]

        return ReIdQualityStats(
            total_rows=total_rows,
            cluster_count=cluster_count,
            singleton_cluster_count=singleton_count,
            singleton_ratio=round(singleton_count / cluster_count, 4) if cluster_count else 0.0,
            average_cluster_size=round((sum(cluster_sizes) / cluster_count), 4) if cluster_count else 0.0,
            median_cluster_size=float(median(cluster_sizes)) if cluster_sizes else 0.0,
            max_cluster_size=max(cluster_sizes) if cluster_sizes else 0,
            high_confidence_ratio=round(conf_counter[ReIdConfidenceBand.HIGH] / total_rows, 4) if total_rows else 0.0,
            medium_confidence_ratio=round(conf_counter[ReIdConfidenceBand.MEDIUM] / total_rows, 4) if total_rows else 0.0,
            low_confidence_ratio=round(conf_counter[ReIdConfidenceBand.LOW] / total_rows, 4) if total_rows else 0.0,
            sequence_data_coverage_ratio=_coverage("enr_seq_num"),
            fingerprint_data_coverage_ratio=_coverage("enr_ie_fingerprint"),
            vendor_data_coverage_ratio=max(_coverage("enr_ie_vendor_ouis"), _coverage("enr_ble_vendor_company_id")),
            ble_signature_coverage_ratio=max(
                _coverage("enr_ble_manufacturer_data"),
                _coverage("enr_ble_service_uuids"),
                _coverage("enr_ble_local_name"),
            ),
            confidence_distribution=confidence_distribution,
            method_distribution=method_distribution,
        )
