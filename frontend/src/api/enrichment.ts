import { apiPost } from "./client";
import type { EnrichmentRunPayload } from "../types/contracts";

export interface RunEnrichmentParams {
  selected_csv_file: string;
}

export async function runEnrichment(
  sessionId: string,
  params: RunEnrichmentParams,
): Promise<EnrichmentRunPayload> {
  const payload = await apiPost<{ enrichment: EnrichmentRunPayload }>(
    `/sessions/${sessionId}/enrichment/run`,
    params,
  );
  return payload.enrichment;
}
