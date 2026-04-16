import { apiGet } from "./client";

export async function getInventory(sessionId: string) {
  return apiGet(`/sessions/${sessionId}/inventory`);
}
