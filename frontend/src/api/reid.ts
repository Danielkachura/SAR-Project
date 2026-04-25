import { apiPost } from "./client";
import type { ReIdParameters, ReIdRunPayload } from "../types/contracts";

export async function runReId(
  sessionId: string,
  parameters?: ReIdParameters,
): Promise<ReIdRunPayload> {
  const payload = await apiPost<{ reid: ReIdRunPayload }>(
    `/sessions/${sessionId}/reid/run`,
    {
      parameters: parameters ?? {},
    },
  );
  return payload.reid;
}
