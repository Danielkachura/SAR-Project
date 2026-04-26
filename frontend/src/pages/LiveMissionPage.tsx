import { useEffect, useRef, useState } from "react";

import { clearBuffer, getPackets, getState, startMission, stopMission } from "../api/liveMission";
import type { LiveMissionState, LivePacket } from "../types/liveMission";

interface Props {
  onBack: () => void;
}

export function LiveMissionPage({ onBack }: Props) {
  const [state, setState] = useState<LiveMissionState | null>(null);
  const [packets, setPackets] = useState<LivePacket[]>([]);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastSeqRef = useRef(0);

  useEffect(() => {
    let mounted = true;

    async function poll() {
      try {
        const response = await getPackets(lastSeqRef.current, 200);
        if (!mounted) {
          return;
        }
        setState(response.state);
        lastSeqRef.current = response.state.last_seq;
        if (response.packets.length > 0) {
          setPackets((prev) => {
            const merged = [...prev, ...response.packets];
            return merged.length > 500 ? merged.slice(merged.length - 500) : merged;
          });
        }
        setPolling(true);
      } catch (err) {
        if (mounted) {
          setError(String(err));
          setPolling(false);
        }
      }
    }

    async function boot() {
      try {
        const initial = await getState();
        if (!mounted) {
          return;
        }
        setState(initial);
        lastSeqRef.current = initial.last_seq;
      } catch (err) {
        if (mounted) {
          setError(String(err));
        }
      }
      await poll();
    }

    void boot();
    const intervalId = setInterval(() => {
      void poll();
    }, 1000);

    return () => {
      mounted = false;
      clearInterval(intervalId);
      setPolling(false);
    };
  }, []);

  async function onStart() {
    setError(null);
    try {
      const next = await startMission();
      setState(next);
      setPackets([]);
      lastSeqRef.current = next.last_seq;
    } catch (err) {
      setError(String(err));
    }
  }

  async function onStop() {
    setError(null);
    try {
      const next = await stopMission();
      setState(next);
      lastSeqRef.current = next.last_seq;
    } catch (err) {
      setError(String(err));
    }
  }

  async function onClear() {
    setError(null);
    try {
      const next = await clearBuffer();
      setState(next);
      setPackets([]);
      lastSeqRef.current = next.last_seq;
    } catch (err) {
      setError(String(err));
    }
  }

  const status = state?.status ?? "idle";

  return (
    <div style={{ padding: "1rem", fontFamily: "monospace" }}>
      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.5rem" }}>
        <button onClick={onBack}>← Back to Overview</button>
        <button onClick={onStart} disabled={status === "running"}>Start</button>
        <button onClick={onStop} disabled={status !== "running"}>Stop</button>
        <button onClick={onClear}>Clear</button>
      </div>

      <h2>Live Mission</h2>
      <p>
        Status: <strong>{status}</strong> | Polling: <strong>{polling ? "on" : "off"}</strong>
      </p>

      <div style={{ border: "1px solid #ccc", padding: "0.75rem", marginBottom: "1rem" }}>
        <div>received_count: {state?.received_count ?? 0}</div>
        <div>dropped_count: {state?.dropped_count ?? 0}</div>
        <div>buffer: {state?.buffer_size ?? 0} / {state?.buffer_capacity ?? 0}</div>
        <div>started_at: {state?.started_at ?? "-"}</div>
      </div>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th align="left">seq</th>
            <th align="left">received_at</th>
            <th align="left">protocol</th>
            <th align="left">device_id</th>
            <th align="left">rssi</th>
            <th align="left">frame_type</th>
          </tr>
        </thead>
        <tbody>
          {[...packets].reverse().map((packet) => (
            <tr key={packet.seq}>
              <td>{packet.seq}</td>
              <td>{packet.received_at}</td>
              <td>{packet.protocol}</td>
              <td>{packet.device_id ?? ""}</td>
              <td>{packet.rssi ?? ""}</td>
              <td>{packet.frame_type ?? ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
