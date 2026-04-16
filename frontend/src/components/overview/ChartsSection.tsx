import type { ChartDatum, OverviewCharts } from "../../types/contracts";

interface Props {
  charts: OverviewCharts;
}

function DatumList({ title, data }: { title: string; data: ChartDatum[] }) {
  return (
    <div>
      <h3>{title}</h3>
      {data.length === 0 ? (
        <p>No data</p>
      ) : (
        <ul>
          {data.map((item) => (
            <li key={`${title}-${item.key}`}>
              {item.key}: {item.count}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function ChartsSection({ charts }: Props) {
  return (
    <section>
      <h2>Charts</h2>
      <DatumList title="Frame/Event Types" data={charts.frame_or_event_type_distribution} />
      <DatumList title="Top Vendors" data={charts.top_vendors} />
      <DatumList title="RSSI Distribution" data={charts.rssi_histogram} />
    </section>
  );
}
