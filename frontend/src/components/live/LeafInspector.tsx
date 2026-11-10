import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { Item, Node } from "../../api/client";
import { fetchTrace } from "../../api/run";
import type { RunEdge } from "../../lib/runState";
import { Chip } from "../Chip";
import {
  ChevronDown,
  ChevronRight,
  Copy,
  FileText,
  Link2,
  Sparkles,
} from "../Icons";
import { SkeletonLines } from "../Skeleton";

function CopyButton({
  copied,
  onCopy,
}: {
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <button type="button" className="live-copy" onClick={onCopy}>
      <Copy size={12} />
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function LeafInspector({
  projectId,
  selectedNode,
  nodesById,
  edges,
  items,
  onSelect,
}: {
  projectId: string;
  selectedNode: Node | null;
  nodesById: Map<string, Node>;
  edges: RunEdge[];
  items: Item[];
  onSelect: (node: Node) => void;
}) {
  const reduced = useReducedMotion();
  const [showTrace, setShowTrace] = useState(false);
  const [copied, setCopied] = useState<"prompt" | "raw" | null>(null);
  const [promptOpen, setPromptOpen] = useState(true);
  const [rawOpen, setRawOpen] = useState(true);

  const traceQuery = useQuery({
    queryKey: ["trace", projectId, selectedNode?.id],
    queryFn: () => fetchTrace(projectId, selectedNode!.id),
    enabled: showTrace && Boolean(selectedNode),
    retry: false,
  });

  useEffect(() => {
    setShowTrace(false);
    setCopied(null);
  }, [selectedNode?.id]);

  const linked = useMemo(() => {
    if (!selectedNode) return [];
    const byOther = new Map<string, { node: Node; edge: RunEdge }>();
    for (const edge of edges) {
      const otherId =
        edge.source === selectedNode.id
          ? edge.target
          : edge.target === selectedNode.id
            ? edge.source
            : null;
      if (!otherId) continue;
      const node = nodesById.get(otherId);
      if (!node) continue;
      const existing = byOther.get(otherId);
      const better =
        !existing ||
        (edge.kind === "reference" && existing.edge.kind !== "reference") ||
        (edge.kind === existing.edge.kind && edge.score > existing.edge.score);
      if (better) byOther.set(otherId, { node, edge });
    }
    return Array.from(byOther.values()).sort((left, right) => {
      if (left.edge.kind !== right.edge.kind) return left.edge.kind === "reference" ? -1 : 1;
      return right.edge.score - left.edge.score;
    });
  }, [selectedNode, edges, nodesById]);

  const leafItems = useMemo(
    () => (selectedNode ? items.filter((item) => item.source_node_id === selectedNode.id) : []),
    [items, selectedNode],
  );
  const epic = leafItems.find((item) => item.kind === "epic");
  const stories = leafItems.filter((item) => item.kind === "story");
  const tests = leafItems.filter((item) => item.kind === "test");
  const questions = useMemo(() => {
    const found = new Set<string>();
    for (const item of leafItems) {
      for (const question of item.questions ?? []) found.add(question);
    }
    return Array.from(found);
  }, [leafItems]);

  const trace = traceQuery.data;
  const rawJson = JSON.stringify(trace?.response_json ?? null, null, 2);

  const copy = async (value: string, key: "prompt" | "raw") => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(key);
      window.setTimeout(() => setCopied(null), 1200);
    } catch {
      setCopied(null);
    }
  };

  if (!selectedNode) {
    return (
      <div className="live-inspector">
        <div className="live-panel__head">
          <div>
            <h2>Inspector</h2>
            <p>Selected leaf details</p>
          </div>
        </div>
        <div className="live-inspector__empty">
          <Sparkles size={22} />
          <strong>Select a section</strong>
          <p>Click a section in the document, a leaf tile or a graph node to inspect it.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="live-inspector">
      <div className="live-panel__head">
        <div>
          <h2>Inspector</h2>
          <p>{leafItems.length} generated item{leafItems.length === 1 ? "" : "s"}</p>
        </div>
        <Chip tone={selectedNode.is_leaf ? "yellow" : "default"}>
          {selectedNode.is_leaf ? "Leaf" : "Heading"}
        </Chip>
      </div>

      <div className="live-inspector__scroll">
        <div className="live-inspector__title">
          <span>{selectedNode.number || "§"}</span>
          <h3>{selectedNode.title || "Untitled section"}</h3>
        </div>

        {selectedNode.lineage?.length > 0 && (
          <div className="live-breadcrumb">{selectedNode.lineage.filter(Boolean).join(" › ")}</div>
        )}

        <div className="live-inspector__section">
          <div className="live-inspector__label">
            <FileText size={12} /> Source text
          </div>
          <div className={`live-source-text ${selectedNode.text?.trim() ? "" : "is-empty"}`.trim()}>
            {selectedNode.text?.trim() || "This section has no body text. Its children carry the requirements."}
          </div>
        </div>

        <div className="live-inspector__section">
          <div className="live-inspector__label">
            <Link2 size={12} /> Linked sections
            <span>{linked.length}</span>
          </div>
          {linked.length === 0 ? (
            <div className="live-mini-empty">No links discovered for this section yet.</div>
          ) : (
            <ul className="live-links">
              {linked.map(({ node, edge }) => (
                <li key={`${node.id}:${edge.kind}`}>
                  <button type="button" onClick={() => onSelect(node)}>
                    <span className="live-links__title">
                      <b>{node.number || "§"}</b> {node.title || "Untitled section"}
                    </span>
                    <span className={`live-links__why is-${edge.kind}`}>
                      {edge.kind === "reference"
                        ? `explicit reference §${node.number || "?"}`
                        : `similarity ${Math.round(edge.score * 100)}%`}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="live-inspector__section">
          <div className="live-inspector__label">
            <Sparkles size={12} /> Generated items
            <span>{leafItems.length}</span>
          </div>
          {leafItems.length === 0 ? (
            <div className="live-mini-empty">
              No items yet. They appear after this leaf is generated.
            </div>
          ) : (
            <div className="live-generated">
              {epic && (
                <div>
                  <span className="live-generated__kind">Epic</span>
                  <strong>{epic.title}</strong>
                </div>
              )}
              {stories.length > 0 && (
                <div>
                  <span className="live-generated__kind">Stories</span>
                  <ul>
                    {stories.map((story) => (
                      <li key={story.id}>{story.title || "Untitled story"}</li>
                    ))}
                  </ul>
                </div>
              )}
              {tests.length > 0 && (
                <div>
                  <span className="live-generated__kind">Tests</span>
                  <ul>
                    {tests.map((test) => (
                      <li key={test.id}>{test.title || "Untitled test"}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {questions.length > 0 && (
          <div className="live-inspector__section">
            <div className="live-inspector__label">Questions for the client</div>
            <ul className="live-questions">
              {questions.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ul>
          </div>
        )}

        <div className="live-inspector__section">
          <button
            type="button"
            className={`live-trace-toggle ${showTrace ? "is-open" : ""}`.trim()}
            onClick={() => setShowTrace((value) => !value)}
            aria-expanded={showTrace}
          >
            {showTrace ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            Show what the AI saw
          </button>

          <AnimatePresence initial={false}>
            {showTrace && (
              <motion.div
                className="live-trace"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: reduced ? 0 : 0.22, ease: [0.22, 1, 0.36, 1] }}
              >
                {traceQuery.isLoading ? (
                  <SkeletonLines lines={4} />
                ) : traceQuery.isError || !trace ? (
                  <div className="live-mini-empty">
                    No trace recorded yet. The generation trace appears once this leaf has been
                    attempted.
                  </div>
                ) : (
                  <>
                    <div className="live-trace__meta">
                      <span>{trace.status}</span>
                      <span>{trace.duration_ms} ms</span>
                      <span>{trace.attempts} attempt{trace.attempts === 1 ? "" : "s"}</span>
                      <span>{trace.neighbours.length} neighbours</span>
                    </div>

                    <div className="live-trace__block">
                      <div className="live-trace__block-head">
                        <button
                          type="button"
                          className="live-trace__summary"
                          onClick={() => setPromptOpen((value) => !value)}
                          aria-expanded={promptOpen}
                        >
                          {promptOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                          Exact prompt
                        </button>
                        <CopyButton copied={copied === "prompt"} onCopy={() => void copy(trace.prompt, "prompt")} />
                      </div>
                      {promptOpen && <pre className="live-code">{trace.prompt}</pre>}
                    </div>

                    <div className="live-trace__block">
                      <div className="live-trace__block-head">
                        <button
                          type="button"
                          className="live-trace__summary"
                          onClick={() => setRawOpen((value) => !value)}
                          aria-expanded={rawOpen}
                        >
                          {rawOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                          Raw JSON response
                        </button>
                        <CopyButton copied={copied === "raw"} onCopy={() => void copy(rawJson, "raw")} />
                      </div>
                      {rawOpen && <pre className="live-code">{rawJson}</pre>}
                    </div>
                  </>
                )}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
