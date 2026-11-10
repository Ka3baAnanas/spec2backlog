import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef } from "react";
import type { Node } from "../../api/client";
import type { LeafRunState, RunState } from "../../lib/runState";
import { Chip } from "../Chip";
import { FileText } from "../Icons";

function dotClass(state: LeafRunState | undefined): string {
  if (!state || state === "waiting") return "is-waiting";
  if (state === "failed") return "is-failed";
  if (state === "done" || state === "retried") return "is-done";
  return "is-active";
}

export function LiveDocumentPanel({
  nodes,
  state,
  selectedId,
  currentNodeId,
  onSelect,
}: {
  nodes: Node[];
  state: RunState;
  selectedId: string | null;
  currentNodeId: string | null;
  onSelect: (node: Node) => void;
}) {
  const reduced = useReducedMotion();
  const rowRefs = useRef(new Map<string, HTMLButtonElement>());
  const bodyRef = useRef<HTMLDivElement>(null);

  const focusNode = useMemo(
    () => nodes.find((node) => node.id === selectedId) ?? nodes.find((node) => node.id === currentNodeId),
    [nodes, selectedId, currentNodeId],
  );

  useEffect(() => {
    if (!currentNodeId) return;
    const row = rowRefs.current.get(currentNodeId);
    if (!row) return;
    row.scrollIntoView({
      behavior: reduced ? "auto" : "smooth",
      block: "nearest",
      inline: "nearest",
    });
  }, [currentNodeId, reduced]);

  return (
    <div className="live-document">
      <div className="live-panel__head">
        <div>
          <h2>Document</h2>
          <p>{nodes.length} sections · source of truth</p>
        </div>
        {currentNodeId && (
          <Chip tone="yellow" dot>
            Processing
          </Chip>
        )}
      </div>

      <div className="live-document__body" ref={bodyRef}>
        {nodes.length === 0 ? (
          <div className="live-empty">The document tree is empty.</div>
        ) : (
          <div className="live-doc-tree" role="tree" aria-label="Document sections">
            {nodes.map((node) => {
              const runtime = state.leaves[node.id];
              const isCurrent = currentNodeId === node.id;
              const isSelected = selectedId === node.id;
              const isLeaf = node.is_leaf && !node.is_global && !node.is_front_matter;
              return (
                <button
                  key={node.id}
                  type="button"
                  role="treeitem"
                  aria-selected={isSelected}
                  aria-current={isCurrent ? "true" : undefined}
                  ref={(element) => {
                    if (element) rowRefs.current.set(node.id, element);
                    else rowRefs.current.delete(node.id);
                  }}
                  className={[
                    "live-doc-row",
                    isCurrent ? "is-current" : "",
                    isSelected ? "is-selected" : "",
                    node.is_front_matter ? "is-front-matter" : "",
                  ]
                    .filter(Boolean)
                    .join(" ")}
                  style={{ paddingLeft: 10 + Math.max(0, node.level - 1) * 14 }}
                  onClick={() => onSelect(node)}
                  title={`${node.number || "Section"} ${node.title}`}
                >
                  {isCurrent && (
                    <motion.span
                      layoutId="live-current-section"
                      className="live-doc-row__current-bg"
                      transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 380, damping: 38 }}
                      aria-hidden="true"
                    />
                  )}
                  <span className="live-doc-row__num">{node.number || "§"}</span>
                  <span className="live-doc-row__label">{node.title || "Untitled section"}</span>
                  {isLeaf && (
                    <span
                      className={`live-doc-row__dot ${dotClass(runtime?.state)}`}
                      aria-label={runtime?.state ?? "waiting"}
                    />
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>

      <div className="live-document__preview">
        <div className="live-document__preview-label">
          <FileText size={12} />
          {focusNode ? `${focusNode.number || "§"} ${focusNode.title || "Untitled"}` : "Select a section"}
        </div>
        <p className={focusNode?.text?.trim() ? "" : "is-empty"}>
          {focusNode?.text?.trim()
            ? focusNode.text.slice(0, 260)
            : "This section has no body text. Its children carry the requirements."}
        </p>
      </div>
    </div>
  );
}
