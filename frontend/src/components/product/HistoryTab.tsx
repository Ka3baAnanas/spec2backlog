import type { RunEvent } from "../../api/run";
import { ActivityLog } from "../live/ActivityLog";

export function HistoryTab({
  events,
  replay,
  replaying,
}: {
  events: RunEvent[];
  replay: () => void;
  replaying: boolean;
}) {
  return (
    <div className="history-tab">
      <div className="tab-head">
        <div>
          <div className="eyebrow">
            <span className="eyebrow__dot" aria-hidden="true" />
            Run journal
          </div>
          <h2>History</h2>
          <p>Every backend event, timestamped and replayable.</p>
        </div>
      </div>
      <div className="card history-card">
        <ActivityLog events={events} replay={replay} replaying={replaying} />
      </div>
    </div>
  );
}
