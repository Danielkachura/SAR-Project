import type { OverviewDeviceAnalysis } from "../../types/contracts";

interface Props {
  analysis: OverviewDeviceAnalysis;
}

export function DeviceInspection({ analysis }: Props) {
  return (
    <section>
      <h2>Device Inspection</h2>
      <table>
        <thead>
          <tr>
            <th>Device</th>
            <th>Packets</th>
            <th>Avg RSSI</th>
            <th>Vendor/Company</th>
          </tr>
        </thead>
        <tbody>
          {analysis.devices.map((item) => (
            <tr key={item.device_id}>
              <td>{item.device_id}</td>
              <td>{item.packet_count}</td>
              <td>{item.average_rssi ?? "N/A"}</td>
              <td>{item.vendor_or_company ?? "N/A"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
