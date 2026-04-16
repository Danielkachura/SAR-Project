import { apiPost } from "./client";
import type { OverviewPayload } from "../types/contracts";

export async function fetchOverview(
  sessionId: string,
  selectedCsvFile: string | null,
  previewLimit = 50,
): Promise<OverviewPayload> {
  const payload = await apiPost<{ overview: OverviewPayload }>(`/sessions/${sessionId}/overview`, {
    selected_csv_file: selectedCsvFile,
    preview_limit: previewLimit,
  });
  return payload.overview;
}
