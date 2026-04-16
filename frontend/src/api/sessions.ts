import { apiGet, apiPatch, apiPost } from "./client";
import type { ProtocolMode, ScanFolder, SessionState } from "../types/contracts";

export async function listScanFolders(): Promise<ScanFolder[]> {
  const payload = await apiGet<{ folders: ScanFolder[] }>("/scan-folders");
  return payload.folders;
}

export async function createSession(folderId: string): Promise<SessionState> {
  const payload = await apiPost<{ session: SessionState }>("/sessions", { folder_id: folderId });
  return payload.session;
}

export async function overrideMode(sessionId: string, mode: ProtocolMode): Promise<SessionState> {
  const payload = await apiPatch<{ session: SessionState }>(`/sessions/${sessionId}/mode`, { mode });
  return payload.session;
}
