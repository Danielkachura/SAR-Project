import type { CalibrationGtMode } from "../../types/contracts";

interface Props {
  selectedCsv: string;
  onSelectedCsvChange: (value: string) => void;
  availableCsvFiles: string[];
  selectedMac: string;
  onSelectedMacChange: (value: string) => void;
  candidateMacs: Array<{ mac: string; sample_count: number }>;
  gtMode: CalibrationGtMode;
  onGtModeChange: (value: CalibrationGtMode) => void;
  gtFirstK: number;
  onGtFirstKChange: (value: number) => void;
  enableRansac: boolean;
  onEnableRansacChange: (value: boolean) => void;
  ransacThreshold: number;
  onRansacThresholdChange: (value: number) => void;
  ransacIterations: number;
  onRansacIterationsChange: (value: number) => void;
  distanceFloorM: number;
  onDistanceFloorMChange: (value: number) => void;
  manualLat: string;
  onManualLatChange: (value: string) => void;
  manualLon: string;
  onManualLonChange: (value: string) => void;
  onRun: () => void;
}

export function CalibrationControls(props: Props) {
  return (
    <section>
      <h2>Calibration Controls</h2>
      <label>
        Calibration CSV
        <select value={props.selectedCsv} onChange={(event) => props.onSelectedCsvChange(event.target.value)}>
          <option value="">Choose CSV</option>
          {props.availableCsvFiles.map((fileName) => (
            <option key={fileName} value={fileName}>
              {fileName}
            </option>
          ))}
        </select>
      </label>

      <label>
        MAC candidate
        <select value={props.selectedMac} onChange={(event) => props.onSelectedMacChange(event.target.value)}>
          <option value="">Choose MAC</option>
          {props.candidateMacs.map((candidate) => (
            <option key={candidate.mac} value={candidate.mac}>
              {candidate.mac} ({candidate.sample_count})
            </option>
          ))}
        </select>
      </label>

      <label>
        GT mode
        <select value={props.gtMode} onChange={(event) => props.onGtModeChange(event.target.value as CalibrationGtMode)}>
          <option value="mean_first_k">mean_first_k</option>
          <option value="first_sample">first_sample</option>
          <option value="manual_map_click">manual_map_click</option>
        </select>
      </label>

      {props.gtMode === "mean_first_k" && (
        <label>
          GT first K
          <input
            type="number"
            min={1}
            max={20}
            value={props.gtFirstK}
            onChange={(event) => props.onGtFirstKChange(Number(event.target.value))}
          />
        </label>
      )}

      {props.gtMode === "manual_map_click" && (
        <>
          <label>
            Manual GT latitude
            <input value={props.manualLat} onChange={(event) => props.onManualLatChange(event.target.value)} />
          </label>
          <label>
            Manual GT longitude
            <input value={props.manualLon} onChange={(event) => props.onManualLonChange(event.target.value)} />
          </label>
        </>
      )}

      <label>
        Enable RANSAC
        <input
          type="checkbox"
          checked={props.enableRansac}
          onChange={(event) => props.onEnableRansacChange(event.target.checked)}
        />
      </label>

      <label>
        RANSAC residual threshold (dB)
        <input
          type="number"
          min={1}
          max={15}
          value={props.ransacThreshold}
          onChange={(event) => props.onRansacThresholdChange(Number(event.target.value))}
        />
      </label>

      <label>
        RANSAC iterations
        <input
          type="number"
          min={10}
          max={1000}
          value={props.ransacIterations}
          onChange={(event) => props.onRansacIterationsChange(Number(event.target.value))}
        />
      </label>

      <label>
        Distance floor (m)
        <input
          type="number"
          min={0.5}
          max={5}
          step={0.1}
          value={props.distanceFloorM}
          onChange={(event) => props.onDistanceFloorMChange(Number(event.target.value))}
        />
      </label>

      <button onClick={props.onRun} disabled={!props.selectedCsv || !props.selectedMac}>
        Run calibration
      </button>
    </section>
  );
}
