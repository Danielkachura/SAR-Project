import type { OverviewSpatialPayload } from "../../types/contracts";

interface Props {
  spatial: OverviewSpatialPayload;
}

export function SpatialInspection({ spatial }: Props) {
  return (
    <section>
      <h2>Spatial Inspection</h2>
      <p>GPS points: {spatial.points.length}</p>
      <ul>
        {spatial.points.map((point, index) => (
          <li
            key={`point-${index}`}
            title={JSON.stringify(point.hover_metadata)}
          >
            ({point.latitude.toFixed(6)}, {point.longitude.toFixed(6)})
          </li>
        ))}
      </ul>
      <p>TODO(spec): replace basic list with shared Spatial Presentation renderer in next UI slice.</p>
    </section>
  );
}
