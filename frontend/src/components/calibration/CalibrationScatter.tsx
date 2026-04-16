import type { CalibrationRunPayload } from "../../types/contracts";

interface Props {
  result: CalibrationRunPayload;
}

export function CalibrationScatter({ result }: Props) {
  return (
    <section>
      <h2>Scatter payload (x=log10(distance), y=RSSI)</h2>
      <p>GT point: ({result.gt_point_latitude}, {result.gt_point_longitude})</p>
      <p>Scatter points: {result.scatter_points.length}</p>
      <p>Fit line points: {result.fit_line.length}</p>
      <pre>{JSON.stringify({ scatter_points: result.scatter_points.slice(0, 10), fit_line: result.fit_line }, null, 2)}</pre>
    </section>
  );
}
