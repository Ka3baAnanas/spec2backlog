import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect } from "react";
import type { RunEvent } from "../../api/run";
import { X } from "../Icons";

const STAGE_LABELS: Record<string, string> = {
  ingestion: "Ingestion",
  structure: "Structure",
  knowledge: "Knowledge",
  context: "Context",
  generation: "Generation",
  review: "Review",
  export: "Export",
};

function timeLabel(ts: string): string {
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) return "n/a";
  return date.toLocaleTimeString("en-GB", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function actorFor(event: RunEvent): string {
  const explicit = event.data?.actor;
  if (typeof explicit === "string" && explicit.trim()) return explicit;
  if (event.data?.checkpoint || event.stage === "review" || event.stage === "export") return "You";
  return "System";
}

export function ActivityDrawer({
  open,
  events,
  onClose,
}: {
  open: boolean;
  events: RunEvent[];
  onClose: () => void;
}) {
  const reduced = useReducedMotion();

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="drawer-backdrop activity-drawer__backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduced ? 0 : 0.16 }}
          onClick={onClose}
        >
          <motion.aside
            className="drawer activity-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Activity"
            initial={{ x: reduced ? 0 : 48 }}
            animate={{ x: 0 }}
            exit={{ x: reduced ? 0 : 48 }}
            transition={{ duration: reduced ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="drawer__head">
              <div>
                <div className="drawer__eyebrow">Run journal</div>
                <h2>Activity</h2>
              </div>
              <button type="button" className="drawer__close" onClick={onClose} aria-label="Close activity">
                <X size={15} />
              </button>
            </div>
            <div className="drawer__body">
              {!events.length ? (
                <p className="muted-small">No activity yet. Events appear here as the pipeline runs.</p>
              ) : (
                <div className="activity-list">
                  {[...events].reverse().map((event) => (
                    <div key={event.id} className="activity-item">
                      <p className="activity-item__message">
                        {event.message || `${STAGE_LABELS[event.stage] ?? event.stage} ${event.type}`}
                      </p>
                      <div className="activity-item__meta">
                        <time dateTime={event.ts}>{timeLabel(event.ts)}</time>
                        <span>{STAGE_LABELS[event.stage] ?? event.stage}</span>
                        <span>{actorFor(event)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
