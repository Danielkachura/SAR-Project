import { apiPost } from "./client";
import type { ExecutionRecord, LocalizationParameters, LocalizationPreFilters } from "../types/contracts";

export interface LocalizationRunResponse {
  execution: ExecutionRecord;
}

export async function runLocalization(
  sessionId: string,
  selectedReidArtifactId: string | null,
  parameters: LocalizationParameters,
  preFilters: LocalizationPreFilters,
): Promise<LocalizationRunResponse> {
  return apiPost<LocalizationRunResponse>(`/sessions/${sessionId}/localization/run`, {
    selected_reid_artifact_id: selectedReidArtifactId,
    parameters,
    pre_filters: preFilters,
  });
}
