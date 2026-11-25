import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import type { RunEvent, RunStage } from "../../api/run";
import { Button } from "../Button";
import {
  AlertTriangle,
  Check,
  CheckCircle,
  Clock,
  History,
  Link2,
  Pause,
  Play,
  Sparkles,
  XCircle,
} from "../Icons";

const STAGE_LABELS: Record<string, string> = {
  ingestion: "Ingestion",
  structure: "Structure",
  knowledge: "Knowledge",
  context: "Context",
  generation: "Generation",
  review: "Review",
  export: "Export",
};

function EventIcon({ type }: { type: RunEvent["type"] }) {
  if (type === "error" || type === "leaf_failed") return <XCircle size={13} />;
  if (type === "warning") return <AlertTriangle size={13} />;
  if (type === "link_found") return <Link2 size={13} />;
  if (type === "leaf_done") return <Check size={13} />;
  if (type === "leaf_start") return <Sparkles size={13} />;
  if (type === "stage_end") return <CheckCircle size={13} />;
  if (type === "stage_start") return <Clock size={13} />;
  return <Clock size={13} />;
}

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

function levelClass(type: RunEvent["type"]): string {
  if (type === "error" || type === "leaf_failed") return "is-error";
  if (type === "warning") return "is-warning";
  if (type === "leaf_done" || type === "stage_end") return "is-success";
  if (type === "link_found") return "is-link";
  if (type === "leaf_start") return "is-active";
  return "is-neutral";
}

export function ActivityLog({
  events,
  replay,
  replaying,
}: {
  events: RunEvent[];
  replay: () => void;
  replaying: boolean;
}) {
  const reduced = useReducedMotion();
  const [stage, setStage] = useState<"all" | RunStage>("all");
  const [paused, setPaused] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);

  const stages = useMemo(() => {
    const found = new Set<RunStage>();
    for (const event of events) found.add(event.stage);
    return Array.from(found);
  }, [events]);

  const filtered = useMemo(
    () => (stage === "all" ? events : events.filter((event) => event.stage === stage)),
    [events, stage],
  );

  useEffect(() => {
    if (paused) return;
    const element = listRef.current;
    if (!element) return;
    element.scrollTo({
      top: element.scrollHeight,
      behavior: reduced ? "auto" : "smooth",
    });
  }, [filtered.length, paused, reduced]);

  return (
    <div className="live-log">
      <div className="live-panel__head">
        <div>
          <h2>Activity log</h2>
          <p>{events.length} events · timestamped from the backend journal</p>
        </div>
        <div className="live-log__actions">
          <button
            type="button"
            className={`live-icon-button ${paused ? "is-on" : ""}`.trim()}
            onClick={() => setPaused((value) => !value)}
            aria-label={paused ? "Resume activity auto-scroll" : "Pause activity auto-scroll"}
            title={paused ? "Resume auto-scroll" : "Pause auto-scroll"}
          >
            {paused ? <Play size={13} /> : <Pause size={13} />}
          </button>
          <Button
            size="sm"
            variant="secondary"
            icon={<History size={14} />}
            loading={replaying}
            onClick={replay}
          >
            Replay run
          </Button>
        </div>
      </div>

      <div className="live-log__filters" role="group" aria-label="Filter events by stage">
        <button
          type="button"
          className={`live-filter ${stage === "all" ? "is-active" : ""}`.trim()}
          onClick={() => setStage("all")}
        >
          All <span>{events.length}</span>
        </button>
        {stages.map((entry) => (
          <button
            key={entry}
            type="button"
            className={`live-filter ${stage === entry ? "is-active" : ""}`.trim()}
            onClick={() => setStage(entry)}
          >
            {STAGE_LABELS[entry] ?? entry}
            <span>{events.filter((event) => event.stage === entry).length}</span>
          </button>
        ))}
      </div>

      <div className="live-log__list" ref={listRef} aria-live="polite">
        {filtered.length === 0 ? (
          <div className="live-log__empty">
            No events yet. Start a run to watch the backend work.
          </div>
        ) : (
          filtered.map((event) => (
            <motion.div
              key={event.id}
              className={`live-log__row ${levelClass(event.type)}`}
              initial={false}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: reduced ? 0 : 0.18 }}
            >
              <time dateTime={event.ts}>{timeLabel(event.ts)}</time>
              <span className="live-log__icon" aria-hidden="true">
                <EventIcon type={event.type} />
              </span>
              <div className="live-log__content">
                <span className="live-log__stage">{STAGE_LABELS[event.stage] ?? event.stage}</span>
                <span className="live-log__message">{event.message}</span>
              </div>
            </motion.div>
          ))
        )}
      </div>
    </div>
  );
}
