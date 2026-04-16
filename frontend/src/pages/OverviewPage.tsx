import type { SessionState } from "../types/contracts";

interface Props {
  session: SessionState;
}

export function OverviewPage({ session }: Props) {
  return (
    <section>
      <h1>Overview</h1>
      <p>Active folder: {session.scan_folder_name}</p>
      <p>Mode: {session.mode}</p>
      <p>
        TODO(spec): Overview statistics/charts/table/map are intentionally deferred to Phase 2.
      </p>
    </section>
  );
}
