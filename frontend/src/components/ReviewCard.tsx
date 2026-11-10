import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useState } from "react";
import { Link } from "react-router-dom";
import type { Item, Node } from "../api/client";
import { easePremium } from "../lib/motion";
import { itemStatusMeta, kindMeta } from "../lib/status";
import { Button } from "./Button";
import { Chip } from "./Chip";
import { CheckCircle, XCircle } from "./Icons";

type ReviewCardProps = {
  item: Item;
  projectId: string;
  lineage?: string[];
  sourceNode?: Node;
  onAction: (status: "approved" | "rejected") => Promise<void>;
};

function text(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === "string") : [];
}

function StoryBody({ body }: { body: Record<string, unknown> }) {
  const asA = text(body.as_a);
  const iWant = text(body.i_want);
  const soThat = text(body.so_that);
  const criteria = stringList(body.acceptance_criteria);
  const priority = text(body.priority);

  return (
    <>
      {(asA || iWant || soThat) && (
        <p className="review-card__as-a">
          As a <b>{asA || "user"}</b>, I want <b>{iWant || "the capability"}</b>
          {soThat ? (
            <>
              , so that <b>{soThat}</b>
            </>
          ) : null}
          .
        </p>
      )}
      {priority && (
        <Chip tone={priority === "must" ? "amber" : "outline"} className="review-card__kind">
          {priority.toUpperCase()} priority
        </Chip>
      )}
      {criteria.length > 0 && (
        <>
          <div className="review-card__subhead">Acceptance criteria</div>
          <ul className="criteria-list">
            {criteria.map((criterion, index) => (
              <li key={index}>{criterion}</li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}

function TestBody({ body }: { body: Record<string, unknown> }) {
  const steps = stringList(body.steps);
  const expected = text(body.expected);
  const storyTitle = text(body.story_title);

  return (
    <>
      {storyTitle && <div className="review-card__as-a">Covers story: <b>{storyTitle}</b></div>}
      {steps.length > 0 && (
        <>
          <div className="review-card__subhead">Test steps</div>
          <ol className="steps-list">
            {steps.map((step, index) => (
              <li key={index}>{step}</li>
            ))}
          </ol>
        </>
      )}
      {expected && <div className="expected-box">Expected: {expected}</div>}
    </>
  );
}

function GenericBody({ body }: { body: Record<string, unknown> }) {
  const ignored = new Set([
    "title",
    "as_a",
    "i_want",
    "so_that",
    "acceptance_criteria",
    "steps",
    "expected",
    "story_title",
    "priority",
  ]);
  const entries = Object.entries(body).filter(([key, value]) => {
    if (ignored.has(key)) return false;
    if (value == null || value === "") return false;
    if (Array.isArray(value) && value.length === 0) return false;
    return true;
  });

  if (!entries.length) return null;

  return (
    <>
      {entries.map(([key, value]) => (
        <div key={key}>
          <div className="review-card__subhead">{key.replace(/_/g, " ")}</div>
          {Array.isArray(value) ? (
            <ul className="criteria-list">
              {value.map((entry, index) => (
                <li key={index}>{typeof entry === "string" ? entry : JSON.stringify(entry)}</li>
              ))}
            </ul>
          ) : (
            <p>{typeof value === "string" ? value : JSON.stringify(value)}</p>
          )}
        </div>
      ))}
    </>
  );
}

export function ReviewCard({ item, projectId, lineage, sourceNode, onAction }: ReviewCardProps) {
  const reduced = useReducedMotion();
  const [flash, setFlash] = useState<"approved" | "rejected" | null>(null);
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState(false);
  const body = (item.body ?? {}) as Record<string, unknown>;
  const kind = kindMeta(item.kind);
  const status = itemStatusMeta(item.status);
  const sourceLineage = sourceNode?.lineage ?? lineage;
  const source = sourceLineage?.filter(Boolean).join(" › ") || "Source section";
  const showSourceChip = item.kind !== "epic" && Boolean(sourceNode);

  const act = async (next: "approved" | "rejected") => {
    if (busy) return;
    setBusy(true);
    setFlash(next);
    if (!reduced) await new Promise((resolve) => window.setTimeout(resolve, 260));
    try {
      await onAction(next);
      if (!reduced) await new Promise((resolve) => window.setTimeout(resolve, 180));
    } finally {
      setBusy(false);
      setFlash(null);
    }
  };

  return (
    <motion.article
      layout={!reduced}
      className="card review-card"
      initial={false}
      transition={{ duration: reduced ? 0 : 0.24, ease: easePremium }}
      aria-label={`${kind.label}: ${item.title}`}
    >
      <motion.span
        className="review-card__flash"
        aria-hidden="true"
        animate={{ opacity: flash ? 1 : 0 }}
        transition={{ duration: reduced ? 0 : 0.2, ease: "easeOut" }}
        style={{
          background:
            flash === "approved"
              ? "linear-gradient(100deg, rgba(31,138,91,0.16), rgba(31,138,91,0.02) 60%, transparent)"
              : "linear-gradient(100deg, rgba(185,37,28,0.15), rgba(185,37,28,0.02) 60%, transparent)",
        }}
      />

      <div className="review-card__head">
        <Chip tone={kind.tone} className="review-card__kind">
          {kind.label}
        </Chip>
        <h3 className="review-card__title">{item.title || "Untitled item"}</h3>
        <Chip tone={status.tone} dot>
          {status.label}
        </Chip>
      </div>

      <div className="review-card__body">
        {item.kind === "story" ? (
          <StoryBody body={body} />
        ) : item.kind === "test" ? (
          <TestBody body={body} />
        ) : (
          <GenericBody body={body} />
        )}

        {showSourceChip && sourceNode && (
          <div className="review-source-row">
            <Link
              to={`/p/${projectId}/live?node=${item.source_node_id}`}
              className="chip chip--outline review-source-chip"
              onMouseEnter={() => setPreview(true)}
              onMouseLeave={() => setPreview(false)}
              onFocus={() => setPreview(true)}
              onBlur={() => setPreview(false)}
              title={source}
            >
              Source · {sourceNode.number || "§"} {sourceNode.title || "Untitled section"}
            </Link>
            <AnimatePresence>
              {preview && (
                <motion.div
                  className="review-source-preview"
                  initial={{ opacity: 0, y: reduced ? 0 : 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: reduced ? 0 : 4 }}
                  transition={{ duration: reduced ? 0 : 0.18, ease: easePremium }}
                >
                  <div className="review-source-preview__label">Source section</div>
                  <div className="review-source-preview__path">{source}</div>
                  <p className="review-source-preview__text">
                    {sourceNode.text?.trim()
                      ? sourceNode.text.slice(0, 240)
                      : "This section has no body text."}
                  </p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {item.questions?.length > 0 && (
          <div className="questions-box">
            <strong>Questions for the client</strong>
            <ul>
              {item.questions.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="review-card__foot">
        <div className="review-card__source" title={source}>
          Traceability {" "}
          <Link to={`/p/${projectId}/live?node=${item.source_node_id}`}>{source}</Link>
        </div>
        <div className="review-card__actions">
          <Button
            size="sm"
            variant="secondary"
            icon={<XCircle size={14} />}
            loading={busy && flash === "rejected"}
            disabled={busy}
            onClick={() => void act("rejected")}
          >
            Reject
          </Button>
          <Button
            size="sm"
            variant="primary"
            icon={<CheckCircle size={14} />}
            loading={busy && flash === "approved"}
            disabled={busy}
            onClick={() => void act("approved")}
          >
            Approve
          </Button>
        </div>
      </div>
    </motion.article>
  );
}
