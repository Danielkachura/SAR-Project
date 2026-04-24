import { apiPost } from "./client";
import type { EnrichmentParameters, EnrichmentRunPayload } from "../types/contracts";

export async function runEnrichment(
  sessionId: string,
  selectedCsvFile: string,
  selectedPcapFile: string,
  parameters?: EnrichmentParameters,
): Promise<EnrichmentRunPayload> {
  const payload = await apiPost<{ enrichment: EnrichmentRunPayload }>(
    `/sessions/${sessionId}/enrichment/run`,
    {
      selected_csv_file: selectedCsvFile,
      selected_pcap_file: selectedPcapFile,
      parameters: parameters ?? {},
    },
  );
  return payload.enrichment;
}
