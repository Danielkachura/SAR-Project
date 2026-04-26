import { apiGet } from "./client";
import type { ExecutionRecord, LocalizationRunPayload } from "../types/contracts";

export interface ExecutionStatusResponse {
  execution: ExecutionRecord;
  localization: LocalizationRunPayload | null;
}

export async function getExecutionStatus(executionId: string): Promise<ExecutionStatusResponse> {
  return apiGet<ExecutionStatusResponse>(`/executions/${executionId}`);
}
