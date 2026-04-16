import type { OverviewSummaryStats } from "../../types/contracts";

interface Props {
  stats: OverviewSummaryStats;
}

export function SummaryStats({ stats }: Props) {
  return (
    <section>
      <h2>Summary Statistics</h2>
      <ul>
        <li>Total rows: {stats.total_rows}</li>
        <li>Unique devices: {stats.unique_devices}</li>
        <li>Average RSSI: {stats.average_rssi ?? "N/A"}</li>
        <li>Vendors/Companies detected: {Object.keys(stats.vendor_company_counts).length}</li>
      </ul>
    </section>
  );
}
