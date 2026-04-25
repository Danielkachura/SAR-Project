import { apiPost } from "./client";
import type { EnrichmentParameters, EnrichmentRunPayload, SessionState } from "../types/contracts";

export interface EnrichmentRunResponse {
  enrichment: EnrichmentRunPayload;
  session: SessionState;
}

export async function runEnrichment(
  sessionId: string,
  selectedCsvFile: string,
  selectedPcapFile: string,
  parameters?: EnrichmentParameters,
): Promise<EnrichmentRunResponse> {
  const payload = await apiPost<EnrichmentRunResponse>(
    `/sessions/${sessionId}/enrichment/run`,
    {
      selected_csv_file: selectedCsvFile,
      selected_pcap_file: selectedPcapFile,
      parameters: parameters ?? {},
    },
  );
  return payload;
}
