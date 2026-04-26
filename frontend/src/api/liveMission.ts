import { apiGet, apiPost } from "./client";
import type { IngestResponse, LiveMissionState, LivePacketIn, LivePacketsResponse } from "../types/liveMission";

export async function getState(): Promise<LiveMissionState> {
  return apiGet<LiveMissionState>("/live-mission/state");
}

export async function getPackets(sinceSeq: number, limit = 200): Promise<LivePacketsResponse> {
  return apiGet<LivePacketsResponse>(`/live-mission/packets?since_seq=${sinceSeq}&limit=${limit}`);
}

export async function startMission(): Promise<LiveMissionState> {
  return apiPost<LiveMissionState>("/live-mission/start", {});
}

export async function stopMission(): Promise<LiveMissionState> {
  return apiPost<LiveMissionState>("/live-mission/stop", {});
}

export async function clearBuffer(): Promise<LiveMissionState> {
  return apiPost<LiveMissionState>("/live-mission/clear", {});
}

export async function pushPacket(packet: LivePacketIn | LivePacketIn[]): Promise<IngestResponse> {
  return apiPost<IngestResponse>("/live-mission/packets", packet);
}
