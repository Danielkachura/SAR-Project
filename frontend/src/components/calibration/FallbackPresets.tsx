import type { CalibrationFallbackPreset } from "../../types/contracts";

interface Props {
  presets: CalibrationFallbackPreset[];
  onSelectPreset: (presetName: string) => void;
  disabled: boolean;
}

export function FallbackPresets({ presets, onSelectPreset, disabled }: Props) {
  return (
    <section>
      <h2>Fallback presets</h2>
      <ul>
        {presets.map((preset) => (
          <li key={preset.name}>
            <button onClick={() => onSelectPreset(preset.name)} disabled={disabled}>
              Use {preset.label}
            </button>
            <span>
              {" "}({preset.parameters.rssi_at_1m}, {preset.parameters.path_loss_n}, {preset.parameters.sigma})
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
