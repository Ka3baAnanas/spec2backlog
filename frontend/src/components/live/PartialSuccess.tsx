import type { Node } from "../../api/client";
import { selectGenerationStats, type RunState } from "../../lib/runState";
import { Button } from "../Button";
import { AlertTriangle, CheckCircle, Refresh } from "../Icons";

export function PartialSuccess({
  leaves,
  state,
  retrying,
  onRetry,
}: {
  leaves: Node[];
  state: RunState;
  retrying: boolean;
  onRetry: () => void;
}) {
  const stats = selectGenerationStats(state, leaves.length);
  const generationDone = state.stages.generation.status === "done";
  if (!generationDone || stats.completed === 0) return null;

  return (
    <div className={`live-summary ${stats.failed ? "has-failure" : "is-success"}`}>
      <span className="live-summary__icon" aria-hidden="true">
        {stats.failed ? <AlertTriangle size={18} /> : <CheckCircle size={18} />}
      </span>
      <div className="live-summary__main">
        <strong>
          {stats.ok} ok, {stats.retried} retried, {stats.failed} failed
        </strong>
        <p>
          {stats.failed
            ? "The run completed with partial success. Failed leaves did not stop the rest of the backlog."
            : "Every leaf completed successfully. Failed leaves can be retried without re-running the whole project."}
        </p>
      </div>
      {stats.failed > 0 && (
        <Button
          size="sm"
          variant="secondary"
          icon={<Refresh size={14} />}
          loading={retrying}
          onClick={onRetry}
        >
          Retry failed
        </Button>
      )}
    </div>
  );
}
