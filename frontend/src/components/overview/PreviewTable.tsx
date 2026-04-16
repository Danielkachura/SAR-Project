import type { OverviewPreview } from "../../types/contracts";

interface Props {
  preview: OverviewPreview;
}

export function PreviewTable({ preview }: Props) {
  return (
    <section>
      <h2>File Preview</h2>
      <p>
        Showing {preview.rows.length} of {preview.total_rows} rows
        {preview.truncated ? " (preview capped)" : ""}
      </p>
      <table>
        <thead>
          <tr>
            {preview.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {preview.rows.map((row, index) => (
            <tr key={`preview-row-${index}`}>
              {preview.columns.map((column) => (
                <td key={`${index}-${column}`}>{row[column] ?? ""}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
