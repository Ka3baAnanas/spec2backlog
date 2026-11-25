import { motion, useReducedMotion } from "framer-motion";
import type { Section } from "../../api/client";
import { selectGenerationStats, type LeafRunState, type RunState } from "../../lib/runState";
import { Button } from "../Button";
import { AlertTriangle, CheckCircle, Refresh, Sparkles } from "../Icons";

function formatDuration(ms: number | null): string {
  if (ms === null) return "n/a";
  if (ms < 1000) return `${Math.max(1, Math.round(ms))} ms`;
  return `${(ms / 1000).toFixed(ms < 10_000 ? 1 : 0)} s`;
}

const STATE_LABEL: Record<LeafRunState, string> = {
  waiting: "Waiting",
  embedded: "Linked",
  generating: "Generating",
  done: "Done",
  retried: "Retried",
  failed: "Failed",
};

export function GenerationView({
  sections,
  state,
  retrying,
  onRetry,
}: {
  sections: Section[];
  state: RunState;
  retrying: boolean;
  onRetry: () => void;
}) {
  const reduced = useReducedMotion();
  const leaves = sections.filter((section) => section.role === "requirement" && section.is_leaf);
  const stats = selectGenerationStats(state, leaves.length);
  const remaining = Math.max(0, stats.total - stats.completed);
  const etaMs = stats.averageDurationMs === null ? null : stats.averageDurationMs * remaining;
  const percent = stats.total ? Math.round((stats.completed / stats.total) * 100) : 0;
  const current = state.currentSectionId
    ? sections.find((section) => section.id === state.currentSectionId)
    : undefined;
  const generationDone = state.stages.generation.status === "done";

  return (
    <div className="generation">
      <div className="generation__progress card card--pad">
        <div className="generation__progress-top">
          <div>
            <div className="eyebrow">
              <span className="eyebrow__dot" aria-hidden="true" />
              {generationDone
                ? stats.failed > 0
                  ? "Generation needs attention"
                  : "Generation complete"
                : "Generating backlog"}
            </div>
            <div className="generation__percent">{percent}%</div>
          </div>
          <div className="generation__eta">
            <span>ETA</span>
            <strong>{remaining === 0 ? "Done" : etaMs === null ? "Estimating…" : formatDuration(etaMs)}</strong>
          </div>
        </div>

        <div
          className="generation__bar"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
          aria-label="Generation progress"
        >
          <motion.span
            className="generation__bar-fill"
            initial={false}
            animate={{ width: `${percent}%` }}
            transition={{ duration: reduced ? 0 : 0.5, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>

        <div className="generation__current">
          <Sparkles size={15} />
          <span>
            {current
              ? `${current.number || "Section"} ${current.title}`
              : generationDone
                ? "All requirement sections processed."
                : "Waiting for the next section…"}
          </span>
        </div>
      </div>

      <div className="generation__counters">
        <div className="generation__counter card">
          <span>Stories</span>
          <strong>{stats.stories}</strong>
        </div>
        <div className="generation__counter card">
          <span>Tests</span>
          <strong>{stats.tests}</strong>
        </div>
        <div className="generation__counter card">
          <span>Questions</span>
          <strong>{stats.questions}</strong>
        </div>
        <div className="generation__counter card">
          <span>Sections</span>
          <strong>
            {stats.completed}/{stats.total}
          </strong>
        </div>
      </div>

      <div className="generation__tiles" role="list" aria-label="Requirement sections">
        {leaves.map((section) => {
          const runtime = state.leaves[section.id];
          const leafState = runtime?.state ?? "waiting";
          return (
            <motion.div
              key={section.id}
              role="listitem"
              className={`generation__tile is-${leafState}`}
              initial={false}
              animate={{ opacity: 1 }}
              title={`${section.number || "Section"} ${section.title}: ${STATE_LABEL[leafState]}`}
            >
              <span className="generation__tile-number">{section.number || "§"}</span>
              <span className="generation__tile-dot" aria-hidden="true" />
              <span className="generation__tile-title">{section.title || "Untitled"}</span>
            </motion.div>
          );
        })}
      </div>

      {generationDone && stats.failed > 0 && (
        <div className="generation__failed card card--pad">
          <span className="generation__failed-icon" aria-hidden="true">
            <AlertTriangle size={18} />
          </span>
          <div>
            <strong>{stats.failed} section(s) failed</strong>
            <p>Completed sections are saved. Retry resumes only the failed ones.</p>
          </div>
          <Button size="sm" variant="secondary" icon={<Refresh size={14} />} loading={retrying} onClick={onRetry}>
            Retry failed
          </Button>
        </div>
      )}

      {generationDone && stats.failed === 0 && (
        <div className="generation__failed is-success card card--pad">
          <span className="generation__failed-icon" aria-hidden="true">
            <CheckCircle size={18} />
          </span>
          <div>
            <strong>Backlog ready</strong>
            <p>Opening the Backlog tab…</p>
          </div>
        </div>
      )}
    </div>
  );
}
