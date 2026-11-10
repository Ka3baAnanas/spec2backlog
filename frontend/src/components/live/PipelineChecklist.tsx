import { motion, useReducedMotion } from "framer-motion";
import { CHECKLIST_STAGES, type RunState, type StageState } from "../../lib/runState";
import { Check } from "../Icons";

function withValidation(stage: StageState, projectStatus?: string): StageState {
  if (stage.key !== "validation") return stage;
  if (projectStatus === "validated" || projectStatus === "exported") {
    return { ...stage, status: "done", counter: "Backlog validated and ready to export" };
  }
  if (projectStatus === "generated") {
    return { ...stage, status: "active", counter: "Review queue ready for a business analyst" };
  }
  return stage;
}

export function PipelineChecklist({
  state,
  projectStatus,
}: {
  state: RunState;
  projectStatus?: string;
}) {
  const reduced = useReducedMotion();

  return (
    <div className="live-checklist" aria-live="polite" aria-label="Pipeline checklist">
      {CHECKLIST_STAGES.map((meta, index) => {
        const stage = withValidation(state.stages[meta.key], projectStatus);
        const statusLabel =
          stage.status === "done" ? "Done" : stage.status === "active" ? "In progress" : "Pending";
        return (
          <motion.div
            key={meta.key}
            className={`live-stage is-${stage.status}`}
            initial={false}
            animate={{
              borderColor:
                stage.status === "active"
                  ? "color-mix(in srgb, var(--ey-yellow) 60%, var(--border))"
                  : "var(--border)",
            }}
            transition={{ duration: reduced ? 0 : 0.3 }}
          >
            <span className="live-stage__marker" aria-hidden="true">
              {stage.status === "done" ? (
                <Check size={13} />
              ) : stage.status === "active" ? (
                <span className="live-stage__pulse" />
              ) : (
                <span className="live-stage__index">{index + 1}</span>
              )}
            </span>
            <div className="live-stage__main">
              <div className="live-stage__top">
                <strong>{meta.label}</strong>
                <span className="live-stage__status">{statusLabel}</span>
              </div>
              <span className="live-stage__counter">{stage.counter}</span>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
