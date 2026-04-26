export type MissionStatus = "idle" | "running" | "stopped";
export type PacketProtocol = "wifi" | "ble" | "unknown";

export interface LivePacketIn {
  protocol?: PacketProtocol;
  device_id?: string | null;
  rssi?: number | null;
  frame_type?: string | null;
  timestamp?: string | null;
  extra?: Record<string, unknown>;
}

export interface LivePacket extends LivePacketIn {
  protocol: PacketProtocol;
  seq: number;
  received_at: string;
}

export interface LiveMissionState {
  status: MissionStatus;
  started_at: string | null;
  stopped_at: string | null;
  received_count: number;
  dropped_count: number;
  buffer_size: number;
  buffer_capacity: number;
  last_seq: number;
}

export interface LivePacketsResponse {
  state: LiveMissionState;
  packets: LivePacket[];
}

export interface IngestResponse {
  accepted: number;
  rejected: number;
  state: LiveMissionState;
}
