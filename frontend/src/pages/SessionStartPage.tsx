import { useEffect, useState } from "react";
import { createSession, listScanFolders, overrideMode } from "../api/sessions";
import type { ProtocolMode, ScanFolder, SessionState } from "../types/contracts";

interface Props {
  onSessionReady: (session: SessionState) => void;
}

export function SessionStartPage({ onSessionReady }: Props) {
  const [folders, setFolders] = useState<ScanFolder[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<string>("");
  const [session, setSession] = useState<SessionState | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    listScanFolders().then(setFolders).catch((err) => setError(String(err)));
  }, []);

  const handleCreateSession = async () => {
    try {
      const created = await createSession(selectedFolder);
      setSession(created);
      onSessionReady(created);
    } catch (err) {
      setError(String(err));
    }
  };

  const handleModeOverride = async (mode: ProtocolMode) => {
    if (!session) return;
    try {
      const updated = await overrideMode(session.session_id, mode);
      setSession(updated);
      onSessionReady(updated);
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <section>
      <h1>Session Start</h1>
      <label>
        Scan folder
        <select value={selectedFolder} onChange={(e) => setSelectedFolder(e.target.value)}>
          <option value="">Select folder</option>
          {folders.map((folder) => (
            <option key={folder.folder_id} value={folder.folder_id}>
              {folder.folder_name}
            </option>
          ))}
        </select>
      </label>
      <button onClick={handleCreateSession} disabled={!selectedFolder}>
        Create Session
      </button>

      {session && (
        <div>
          <p>Detected mode: {session.mode}</p>
          <button onClick={() => handleModeOverride("wifi")}>Override Wi-Fi</button>
          <button onClick={() => handleModeOverride("ble")}>Override BLE</button>
        </div>
      )}

      {error && <p role="alert">{error}</p>}
    </section>
  );
}
