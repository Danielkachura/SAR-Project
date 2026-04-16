import type { CalibrationRunPayload } from "../../types/contracts";

interface Props {
  result: CalibrationRunPayload;
}

export function CalibrationDiagnostics({ result }: Props) {
  return (
    <section>
      <h2>Fit diagnostics</h2>
      <ul>
        <li>sample_count: {result.diagnostics.sample_count}</li>
        <li>inlier_count: {result.diagnostics.inlier_count}</li>
        <li>inlier_ratio: {result.diagnostics.inlier_ratio}</li>
        <li>distance_min_m: {result.diagnostics.distance_min_m}</li>
        <li>distance_max_m: {result.diagnostics.distance_max_m}</li>
        <li>distance_span_m: {result.diagnostics.distance_span_m}</li>
        <li>r2: {result.diagnostics.r2}</li>
      </ul>

      <h3>Derived parameters</h3>
      <ul>
        <li>rssi_at_1m: {result.parameters.rssi_at_1m}</li>
        <li>path_loss_n: {result.parameters.path_loss_n}</li>
        <li>sigma: {result.parameters.sigma}</li>
      </ul>

      {result.warnings.length > 0 && (
        <>
          <h3>Warnings (approval still allowed)</h3>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning.code}>{warning.message}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
