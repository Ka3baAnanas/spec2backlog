import { motion, useReducedMotion } from "framer-motion";
import type { Node } from "../../api/client";
import {
  selectGenerationStats,
  type LeafRunState,
  type RunState,
} from "../../lib/runState";

const STATE_LABEL: Record<LeafRunState, string> = {
  waiting: "Waiting",
  embedding: "Embedded",
  generating: "Generating",
  done: "Done",
  failed: "Failed",
  retried: "Retried",
};

function formatDuration(ms: number | null): string {
  if (ms === null) return "—";
  if (ms < 1000) return `${Math.max(1, Math.round(ms))} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
}

export function LeafGrid({
  leaves,
  state,
  selectedId,
  onSelect,
}: {
  leaves: Node[];
  state: RunState;
  selectedId: string | null;
  onSelect: (node: Node) => void;
}) {
  const reduced = useReducedMotion();
  const stats = selectGenerationStats(state, leaves.length);
  const remaining = Math.max(0, stats.total - stats.completed);
  const etaMs = stats.averageDurationMs === null ? null : stats.averageDurationMs * remaining;
  const percent = stats.total ? Math.round((stats.completed / stats.total) * 100) : 0;

  if (!leaves.length) {
    return (
      <div className="live-empty">
        <strong>No leaf sections detected</strong>
        The document has no text-bearing leaves to embed or generate.
      </div>
    );
  }

  return (
    <div className="live-leaf-grid">
      <div className="live-run-progress">
        <div className="live-run-progress__row">
          <span>
            <strong>{stats.completed}</strong> / {stats.total} leaves
          </span>
          <span>
            ETA {remaining === 0 ? "complete" : etaMs === null ? "waiting for durations" : formatDuration(etaMs)}
          </span>
        </div>
        <div
          className="live-progress"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          aria-label="Generation progress"
        >
          <motion.span
            className="live-progress__fill"
            initial={false}
            animate={{ width: `${percent}%` }}
            transition={{ duration: reduced ? 0 : 0.45, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>
        <div className="live-run-progress__meta">
          <span>{stats.ok} ok</span>
          <span>{stats.retried} retried</span>
          <span>{stats.failed} failed</span>
          <span>avg {formatDuration(stats.averageDurationMs)}</span>
        </div>
      </div>

      <div className="live-leaf-grid__tiles" role="list" aria-label="Leaf sections">
        {leaves.map((node) => {
          const runtime = state.leaves[node.id];
          const leafState = runtime?.state ?? "waiting";
          const selected = selectedId === node.id;
          return (
            <motion.button
              key={node.id}
              type="button"
              role="listitem"
              className={`live-leaf is-${leafState} ${selected ? "is-selected" : ""}`.trim()}
              title={`${node.number || "Section"} ${node.title || "Untitled"} — ${STATE_LABEL[leafState]}`}
              aria-pressed={selected}
              aria-label={`${node.number || "Section"} ${node.title}: ${STATE_LABEL[leafState]}`}
              onClick={() => onSelect(node)}
              initial={false}
              whileHover={reduced ? undefined : { y: -2 }}
              whileTap={reduced ? undefined : { scale: 0.96 }}
              transition={{ duration: 0.16 }}
            >
              <span className="live-leaf__number">{node.number || "§"}</span>
              <span className="live-leaf__dot" aria-hidden="true" />
              <span className="live-leaf__title">{node.title || "Untitled"}</span>
            </motion.button>
          );
        })}
      </div>
    </div>
  );
}
