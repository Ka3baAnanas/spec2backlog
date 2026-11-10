import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type {
  ContextPack,
  ItemStatus,
  ItemTrace,
  Section,
  StoryNode,
} from "../../api/client";
import { itemStatusMeta, roleMeta } from "../../lib/status";
import { Button } from "../Button";
import { Chip } from "../Chip";
import { Copy, Link2, Refresh, X, XCircle, CheckCircle } from "../Icons";

const PRIORITIES = ["must", "should", "could"];

export function StoryDrawer({
  story,
  sourceSection,
  context,
  trace,
  loadingContext,
  loadingTrace,
  busy,
  onClose,
  onSave,
  onDecide,
  onRegenerate,
}: {
  story: StoryNode | null;
  sourceSection?: Section;
  context?: ContextPack;
  trace?: ItemTrace;
  loadingContext: boolean;
  loadingTrace: boolean;
  busy: boolean;
  onClose: () => void;
  onSave: (title: string, body: Record<string, unknown>) => void;
  onDecide: (status: ItemStatus, title: string, body: Record<string, unknown>) => void;
  onRegenerate: (instruction: string) => void;
}) {
  const reduced = useReducedMotion();
  const [title, setTitle] = useState("");
  const [asA, setAsA] = useState("");
  const [iWant, setIWant] = useState("");
  const [soThat, setSoThat] = useState("");
  const [priority, setPriority] = useState("should");
  const [criteria, setCriteria] = useState("");
  const [instruction, setInstruction] = useState("");
  const [traceTab, setTraceTab] = useState<"prompt" | "json">("prompt");

  useEffect(() => {
    if (!story) return;
    const body = story.body;
    setTitle(story.title);
    setAsA(String(body.as_a ?? ""));
    setIWant(String(body.i_want ?? ""));
    setSoThat(String(body.so_that ?? ""));
    setPriority(String(body.priority ?? "should"));
    setCriteria((body.acceptance_criteria ?? []).join("\n"));
    setInstruction("");
    setTraceTab("prompt");
  }, [story]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const body = useMemo<Record<string, unknown>>(() => {
    if (!story) return {};
    return {
      ...story.body,
      as_a: asA,
      i_want: iWant,
      so_that: soThat,
      priority,
      acceptance_criteria: criteria
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
    };
  }, [story, asA, iWant, soThat, priority, criteria]);

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard may be unavailable; the content stays visible.
    }
  };

  return (
    <AnimatePresence>
      {story && (
        <motion.div
          className="drawer-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reduced ? 0 : 0.2 }}
          onClick={onClose}
        >
          <motion.aside
            className="drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`Story ${story.key}`}
            initial={{ x: reduced ? 0 : "100%" }}
            animate={{ x: 0 }}
            exit={{ x: reduced ? 0 : "100%" }}
            transition={{ duration: reduced ? 0 : 0.28, ease: [0.22, 1, 0.36, 1] }}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="drawer__head">
              <div>
                <div className="drawer__eyebrow">
                  <span>{story.key}</span>
                  <Chip tone={itemStatusMeta(story.status).tone}>{itemStatusMeta(story.status).label}</Chip>
                </div>
                <h2>{story.title}</h2>
              </div>
              <button type="button" className="drawer__close" onClick={onClose} aria-label="Close story drawer">
                <X size={18} />
              </button>
            </div>

            <div className="drawer__body">
              <section className="drawer-section">
                <h3>Source section</h3>
                {sourceSection ? (
                  <div className="source-block">
                    <div className="source-block__head">
                      <span>{sourceSection.number || "Section"}</span>
                      <Chip tone={roleMeta(sourceSection.role).tone}>{roleMeta(sourceSection.role).label}</Chip>
                    </div>
                    <div className="source-block__path">{sourceSection.lineage.join(" › ")}</div>
                    <p>{sourceSection.text || "No body text in this section."}</p>
                  </div>
                ) : (
                  <p className="muted-small">Source section not found.</p>
                )}
              </section>

              <section className="drawer-section">
                <h3>Linked sections</h3>
                {loadingContext ? (
                  <p className="muted-small">Loading linked sections…</p>
                ) : context?.links?.length ? (
                  <ul className="drawer-links">
                    {context.links.map((link) => (
                      <li key={link.section_id}>
                        <Link2 size={13} />
                        <span>
                          <b>{link.number || "§"}</b> {link.title}
                        </span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted-small">No linked sections in this context.</p>
                )}
              </section>

              <section className="drawer-section">
                <div className="drawer-section__head">
                  <h3>What the AI saw</h3>
                  <div className="context-panel__tabs drawer-tabs">
                    <button
                      type="button"
                      className={`context-tab ${traceTab === "prompt" ? "is-active" : ""}`.trim()}
                      onClick={() => setTraceTab("prompt")}
                    >
                      Prompt
                    </button>
                    <button
                      type="button"
                      className={`context-tab ${traceTab === "json" ? "is-active" : ""}`.trim()}
                      onClick={() => setTraceTab("json")}
                    >
                      Raw JSON
                    </button>
                  </div>
                </div>
                {loadingTrace ? (
                  <p className="muted-small">Loading generation trace…</p>
                ) : (
                  <>
                    <div className="prompt-actions">
                      <span className="muted-small">
                        {traceTab === "prompt" ? "Exact prompt" : "Model output"}
                        {trace ? ` · ${trace.attempts} attempt(s) · ${trace.duration_ms} ms` : ""}
                      </span>
                      <button
                        type="button"
                        className="mini-action"
                        onClick={() =>
                          void copy(
                            traceTab === "prompt"
                              ? trace?.prompt ?? context?.prompt ?? ""
                              : JSON.stringify(trace?.response_json ?? {}, null, 2),
                          )
                        }
                      >
                        <Copy size={13} /> Copy
                      </button>
                    </div>
                    <pre className="prompt-preview">
                      {traceTab === "prompt"
                        ? trace?.prompt ?? context?.prompt ?? "No prompt snapshot available."
                        : JSON.stringify(trace?.response_json ?? {}, null, 2)}
                    </pre>
                  </>
                )}
              </section>

              <section className="drawer-section">
                <h3>Edit story</h3>
                <div className="drawer-form">
                  <label className="field">
                    <span>Title</span>
                    <input className="input" value={title} onChange={(event) => setTitle(event.target.value)} />
                  </label>
                  <div className="drawer-form__row">
                    <label className="field">
                      <span>Priority</span>
                      <select
                        className="input"
                        value={priority}
                        onChange={(event) => setPriority(event.target.value)}
                      >
                        {PRIORITIES.map((entry) => (
                          <option key={entry} value={entry}>
                            {entry}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Confidence</span>
                      <div className="confidence-readonly">{Math.round(story.confidence * 100)}%</div>
                    </label>
                  </div>
                  <label className="field">
                    <span>As a</span>
                    <input className="input" value={asA} onChange={(event) => setAsA(event.target.value)} />
                  </label>
                  <label className="field">
                    <span>I want</span>
                    <textarea className="input input--area" value={iWant} onChange={(event) => setIWant(event.target.value)} />
                  </label>
                  <label className="field">
                    <span>So that</span>
                    <textarea className="input input--area" value={soThat} onChange={(event) => setSoThat(event.target.value)} />
                  </label>
                  <label className="field">
                    <span>Acceptance criteria (one per line)</span>
                    <textarea
                      className="input input--area input--tall"
                      value={criteria}
                      onChange={(event) => setCriteria(event.target.value)}
                    />
                  </label>
                </div>
              </section>

              <section className="drawer-section">
                <h3>Regenerate with instruction</h3>
                <textarea
                  className="input input--area"
                  placeholder="e.g. Split into two stories and add a negative test case"
                  value={instruction}
                  onChange={(event) => setInstruction(event.target.value)}
                />
                <div className="drawer-section__actions">
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={<Refresh size={14} />}
                    loading={busy}
                    disabled={!instruction.trim()}
                    onClick={() => onRegenerate(instruction.trim())}
                  >
                    Regenerate
                  </Button>
                </div>
              </section>
            </div>

            <div className="drawer__foot">
              <Button variant="secondary" loading={busy} onClick={() => onSave(title, body)}>
                Save changes
              </Button>
              <div className="drawer__decisions">
                <Button
                  variant="danger"
                  icon={<XCircle size={14} />}
                  loading={busy}
                  onClick={() => onDecide("rejected", title, body)}
                >
                  Reject
                </Button>
                <Button
                  variant="primary"
                  icon={<CheckCircle size={14} />}
                  loading={busy}
                  onClick={() => onDecide("approved", title, body)}
                >
                  Approve
                </Button>
              </div>
            </div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
