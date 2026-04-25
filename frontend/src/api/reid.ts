import { apiPost } from "./client";
import type { ReIdParameters, ReIdRunPayload, SessionState } from "../types/contracts";

export interface ReIdRunResponse {
  reid: ReIdRunPayload;
  session: SessionState;
}

export async function runReId(
  sessionId: string,
  selectedEnrichedArtifactId: string | null,
  parameters?: ReIdParameters,
): Promise<ReIdRunResponse> {
  const payload = await apiPost<ReIdRunResponse>(
    `/sessions/${sessionId}/reid/run`,
    {
      selected_enriched_artifact_id: selectedEnrichedArtifactId,
      parameters: parameters ?? {},
    },
  );
  return payload;
}
