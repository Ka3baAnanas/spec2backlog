import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type Node } from "../api/client";
import { fetchGraph, type Edge } from "../api/graph";
import { runPipeline } from "../api/run";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Chip } from "../components/Chip";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle,
  Download,
  FileText,
  Layers,
  Link2,
  ListChecks,
  Network,
  Play,
  Sparkles,
} from "../components/Icons";
import { Skeleton, SkeletonLines } from "../components/Skeleton";
import { StatTile } from "../components/StatTile";
import { Stepper } from "../components/Stepper";
import { useToast } from "../components/Toast";
import { TreeView } from "../components/TreeView";
import { errorMessage } from "../lib/errors";
import { easePremium, staggerContainer, staggerItem } from "../lib/motion";
import { projectRank, projectStatusMeta } from "../lib/status";

type LinkedNode = { node: Node; edge: Edge };

const PIPELINE_STEPS = [
  { label: "Upload", sub: "Source received" },
  { label: "Ingest", sub: "Tree + checklist" },
  { label: "Meaning graph", sub: "Related sections" },
  { label: "Generate", sub: "Epics & stories" },
  { label: "Review", sub: "Human validation" },
  { label: "Export", sub: "Excel" },
];

function WorkspaceSkeleton() {
  return (
    <div className="container page">
      <div className="page-head">
        <div style={{ flex: 1 }}>
          <Skeleton width={120} height={12} />
          <div style={{ marginTop: 12 }}>
            <Skeleton width="48%" height={30} />
          </div>
          <div style={{ marginTop: 12 }}>
            <Skeleton width="62%" height={13} />
          </div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Skeleton width={130} height={40} radius={10} />
          <Skeleton width={110} height={40} radius={10} />
        </div>
      </div>
      <div className="card stepper-card">
        <SkeletonLines lines={2} />
        <div style={{ display: "flex", gap: 20, marginTop: 24 }}>
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} width={36} height={36} radius={999} />
          ))}
        </div>
      </div>
      <div className="workspace-grid">
        <div className="card tree-card">
          <div className="tree-card__head">
            <Skeleton width={140} height={16} />
          </div>
          <div style={{ padding: 18 }}>
            <SkeletonLines lines={8} />
          </div>
        </div>
        <div className="detail-stack">
          <div className="card card--pad">
            <Skeleton width={80} height={12} />
            <div style={{ marginTop: 12 }}>
              <Skeleton width="56%" height={24} />
            </div>
            <div style={{ marginTop: 18 }}>
              <SkeletonLines lines={5} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function Project() {
  const { id = "" } = useParams();
  const [searchParams] = useSearchParams();
  const requestedNode = searchParams.get("node");
  const navigate = useNavigate();
  const reduced = useReducedMotion();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [graphSuccess, setGraphSuccess] = useState(false);
  const [generateSuccess, setGenerateSuccess] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const treeQuery = useQuery({
    queryKey: ["tree", id],
    queryFn: () => api.tree(id),
    enabled: Boolean(id),
  });
  const graphQuery = useQuery({
    queryKey: ["graph", id],
    queryFn: () => fetchGraph(id),
    enabled: Boolean(id),
  });
  const itemsQuery = useQuery({
    queryKey: ["items", id],
    queryFn: () => api.items(id),
    enabled: Boolean(id),
  });

  const project = projectsQuery.data?.find((entry) => entry.id === id);
  const tree = treeQuery.data ?? [];
  const graph = graphQuery.data ?? [];
  const items = itemsQuery.data ?? [];

  useEffect(() => {
    if (!tree.length) return;
    if (requestedNode && tree.some((node) => node.id === requestedNode)) {
      setSelectedId(requestedNode);
      return;
    }
    setSelectedId((previous) => {
      if (previous && tree.some((node) => node.id === previous)) return previous;
      return (
        tree.find((node) => node.is_leaf && node.text)?.id ??
        tree.find((node) => node.is_leaf)?.id ??
        tree[0]?.id ??
        null
      );
    });
  }, [tree, requestedNode]);

  const nodesById = useMemo(() => new Map(tree.map((node) => [node.id, node])), [tree]);

  const selected = useMemo(
    () => (selectedId ? nodesById.get(selectedId) ?? null : null),
    [selectedId, nodesById],
  );

  const linked = useMemo<LinkedNode[]>(() => {
    if (!selected) return [];
    const best = new Map<string, Edge>();
    for (const edge of graph) {
      if (edge.source !== selected.id && edge.target !== selected.id) continue;
      const otherId = edge.source === selected.id ? edge.target : edge.source;
      if (!nodesById.has(otherId)) continue;
      const existing = best.get(otherId);
      if (!existing || edge.score > existing.score) best.set(otherId, edge);
    }
    return Array.from(best.entries())
      .map(([otherId, edge]) => ({ node: nodesById.get(otherId) as Node, edge }))
      .sort((a, b) => b.edge.score - a.edge.score)
      .slice(0, 8);
  }, [graph, selected, nodesById]);

  const selectedItems = useMemo(
    () => (selected ? items.filter((item) => item.source_node_id === selected.id) : []),
    [items, selected],
  );

  const refreshPipeline = () => {
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
    void queryClient.invalidateQueries({ queryKey: ["graph", id] });
    void queryClient.invalidateQueries({ queryKey: ["items", id] });
  };

  const flash = (setter: (value: boolean) => void) => {
    setter(true);
    window.setTimeout(() => setter(false), 1600);
  };

  const buildGraph = useMutation({
    mutationFn: () => api.buildGraph(id),
    onSuccess: (result) => {
      const payload = result as { leaves?: number; edges?: number };
      refreshPipeline();
      flash(setGraphSuccess);
      toast({
        tone: "success",
        title: "Meaning graph built",
        message: `${payload?.edges ?? 0} related-section links across ${payload?.leaves ?? 0} leaves.`,
      });
    },
    onError: (error) => {
      toast({ tone: "error", title: "Could not build the graph", message: errorMessage(error) });
    },
  });

  const generate = useMutation({
    mutationFn: () => api.generate(id),
    onSuccess: (result) => {
      const payload = result as { items?: number };
      refreshPipeline();
      flash(setGenerateSuccess);
      toast({
        tone: "success",
        title: "Backlog generated",
        message: `${payload?.items ?? 0} items drafted. Review them before export.`,
      });
    },
    onError: (error) => {
      toast({ tone: "error", title: "Generation failed", message: errorMessage(error) });
    },
  });

  const runPipelineMutation = useMutation({
    mutationFn: () => runPipeline(id),
    onSuccess: () => {
      toast({
        tone: "info",
        title: "Live run started",
        message: "Opening the real-time pipeline view.",
      });
      navigate(`/p/${id}/live`);
    },
    onError: (error) => {
      toast({ tone: "error", title: "Could not start the live run", message: errorMessage(error) });
    },
  });

  const handleExport = async () => {
    if (!project || exporting) return;
    setExporting(true);
    try {
      const response = await fetch(api.exportUrl(id));
      if (!response.ok) {
        throw new Error((await response.text()) || `Export failed (${response.status})`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const slug = project.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "");
      anchor.href = url;
      anchor.download = `${slug || "backlog"}.xlsx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      flash(setExportSuccess);
      toast({
        tone: "success",
        title: "Export ready",
        message: "Validated and edited items were downloaded as an Excel workbook.",
      });
    } catch (error) {
      toast({ tone: "error", title: "Export failed", message: errorMessage(error) });
    } finally {
      setExporting(false);
    }
  };

  if (projectsQuery.isLoading && !project) {
    return <WorkspaceSkeleton />;
  }

  if (projectsQuery.isSuccess && !project) {
    return (
      <div className="page">
        <div className="container">
          <Card className="state-card" pad={false}>
            <strong>Project not found</strong>
            <p>This analysis may have been removed or the link is incomplete.</p>
            <div style={{ marginTop: 18 }}>
              <Link to="/" className="btn btn--secondary">
                Back to projects
              </Link>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  const status = projectStatusMeta(project?.status ?? "created");
  const rank = projectRank(project?.status ?? "created");
  const doneCount = project ? Math.min(PIPELINE_STEPS.length, rank + 1) : 0;
  const found = project?.checklist?.found ?? [];
  const missing = project?.checklist?.missing ?? [];
  const checklistTotal = found.length + missing.length;
  const checklistPercent = checklistTotal ? Math.round((found.length / checklistTotal) * 100) : 0;
  const leaves = tree.filter((node) => node.is_leaf).length;
  const approved = items.filter((item) => item.status === "approved" || item.status === "edited").length;

  return (
    <div className="page">
      <div className="container">
        <div className="breadcrumb">
          <Link to="/">Projects</Link>
          <span aria-hidden="true">/</span>
          <span>Workspace</span>
        </div>

        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 10 }}>
              <span className="eyebrow__dot" aria-hidden="true" />
              Workspace · {status.label}
            </div>
            <h1>{project?.name ?? "Analysis workspace"}</h1>
            <p className="page-head__sub">
              Inspect the document structure, connect related sections, generate the backlog and
              send it for human validation.
            </p>
          </div>

          <div className="page-head__actions">
            <Button
              variant="accent"
              icon={<Play size={15} />}
              loading={runPipelineMutation.isPending}
              title="Run graph and generation with live progress"
              onClick={() => runPipelineMutation.mutate()}
            >
              Run pipeline
            </Button>
            <Button
              variant="secondary"
              icon={<Network size={15} />}
              loading={buildGraph.isPending}
              success={graphSuccess}
              title="Build meaning graph"
              onClick={() => buildGraph.mutate()}
            >
              Build graph
            </Button>
            <Button
              variant="primary"
              icon={<Sparkles size={15} />}
              loading={generate.isPending}
              success={generateSuccess}
              onClick={() => generate.mutate()}
            >
              Generate backlog
            </Button>
            <Button
              variant="secondary"
              icon={<ListChecks size={15} />}
              onClick={() => navigate(`/p/${id}/review`)}
            >
              Review
            </Button>
            <Button
              variant="accent"
              icon={<Download size={15} />}
              loading={exporting}
              success={exportSuccess}
              title="Export validated backlog to Excel"
              onClick={() => void handleExport()}
            >
              Export
            </Button>
          </div>
        </div>

        <Stepper steps={PIPELINE_STEPS} doneCount={doneCount} title="Pipeline progress" />

        <motion.div
          className="stat-grid"
          variants={staggerContainer}
          initial="hidden"
          animate="show"
        >
          <StatTile
            label="Sections"
            value={tree.length}
            hint="Headings and leaves"
            icon={<Layers size={13} />}
          />
          <StatTile
            label="Leaf sections"
            value={leaves}
            hint="Generation candidates"
            icon={<FileText size={13} />}
          />
          <StatTile
            label="Meaning links"
            value={graph.length}
            hint="Related section pairs"
            icon={<Link2 size={13} />}
          />
          <StatTile
            label="Backlog items"
            value={items.length}
            hint={`${approved} validated`}
            icon={<ListChecks size={13} />}
          />
        </motion.div>

        <div className="workspace-grid">
          <Card className="tree-card" pad={false}>
            <div className="tree-card__head">
              <div>
                <h2>Document outline</h2>
                <p>
                  {tree.length} sections · {leaves} leaves
                </p>
              </div>
              <Chip tone={status.tone} dot>
                {status.label}
              </Chip>
            </div>
            <div className="tree-card__body">
              {treeQuery.isLoading ? (
                <div style={{ padding: 12 }}>
                  <SkeletonLines lines={10} />
                </div>
              ) : treeQuery.isError ? (
                <div className="tree-empty">{errorMessage(treeQuery.error)}</div>
              ) : tree.length === 0 ? (
                <div className="tree-empty">No sections were detected in this document.</div>
              ) : (
                <TreeView
                  nodes={tree}
                  selectedId={selectedId}
                  onSelect={(node) => setSelectedId(node.id)}
                />
              )}
            </div>
          </Card>

          <AnimatePresence mode="wait" initial={false}>
            {selected ? (
              <motion.div
                key={selected.id}
                className="detail-stack"
                initial={{ opacity: 0, y: reduced ? 0 : 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduced ? 0 : -8 }}
                transition={{ duration: reduced ? 0 : 0.22, ease: easePremium }}
              >
                <Card className="detail-card" pad={false}>
                  <div className="detail-card__head">
                    <div>
                      <div className="detail-card__num">
                        Section {selected.number || "—"}
                      </div>
                      <h2>{selected.title || "Untitled section"}</h2>
                    </div>
                    <div className="detail-card__chips">
                      <Chip tone={selected.is_leaf ? "yellow" : "default"}>
                        {selected.is_leaf ? "Leaf section" : "Heading"}
                      </Chip>
                      {(selected as Node & { is_global?: boolean }).is_global && (
                        <Chip tone="blue">Global context</Chip>
                      )}
                    </div>
                  </div>

                  {selected.lineage?.length > 0 && (
                    <div className="detail-card__lineage">
                      {selected.lineage.filter(Boolean).join(" › ")}
                    </div>
                  )}

                  <div
                    className={`detail-card__text ${selected.text?.trim() ? "" : "is-empty"}`.trim()}
                  >
                    {selected.text?.trim()
                      ? selected.text
                      : "This section has no body text. Its children carry the requirements."}
                  </div>

                  {selectedItems.length > 0 && (
                    <div style={{ marginTop: 18 }}>
                      <div className="detail-card__num">Backlog items from this section</div>
                      <div className="chip-wrap">
                        {selectedItems.slice(0, 6).map((item) => (
                          <Chip
                            key={item.id}
                            tone={item.status === "approved" ? "green" : item.status === "rejected" ? "red" : "outline"}
                          >
                            {item.kind} · {item.title}
                          </Chip>
                        ))}
                        {selectedItems.length > 6 && (
                          <Chip tone="outline">+{selectedItems.length - 6} more</Chip>
                        )}
                      </div>
                    </div>
                  )}
                </Card>

                <Card className="links-card" pad={false}>
                  <div className="card-head" style={{ marginBottom: 16 }}>
                    <div>
                      <h2>Linked sections</h2>
                      <p>Related requirements discovered by the meaning graph.</p>
                    </div>
                    <Chip tone={linked.length ? "yellow" : "outline"}>{linked.length}</Chip>
                  </div>

                  {graphQuery.isLoading ? (
                    <div className="skeleton-stack">
                      <Skeleton height={46} radius={9} />
                      <Skeleton height={46} radius={9} />
                      <Skeleton height={46} radius={9} />
                    </div>
                  ) : graphQuery.isError ? (
                    <div className="link-empty">{errorMessage(graphQuery.error)}</div>
                  ) : linked.length === 0 ? (
                    <div className="link-empty">
                      No linked sections yet. Build the meaning graph to connect related
                      requirements across the specification.
                    </div>
                  ) : (
                    <ul className="link-list">
                      {linked.map(({ node, edge }, index) => {
                        const percent = Math.max(4, Math.min(100, Math.round(edge.score * 100)));
                        return (
                          <motion.li
                            key={node.id}
                            initial={{ opacity: 0, x: reduced ? 0 : -6 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{
                              duration: reduced ? 0 : 0.24,
                              delay: reduced ? 0 : index * 0.04,
                              ease: easePremium,
                            }}
                          >
                            <button
                              type="button"
                              className="link-item"
                              onClick={() => setSelectedId(node.id)}
                            >
                              <Link2 size={15} style={{ color: "var(--muted)", flexShrink: 0 }} />
                              <span className="link-item__label">
                                <span style={{ color: "var(--muted)", fontWeight: 700, fontSize: 11 }}>
                                  {node.number}
                                </span>{" "}
                                {node.title || "Untitled section"}
                              </span>
                              <Chip
                                tone={edge.kind === "reference" ? "blue" : "outline"}
                                className="review-card__kind"
                              >
                                {edge.kind}
                              </Chip>
                              <span className="link-item__score">
                                <span>{percent}%</span>
                                <span className="link-item__bar">
                                  <i style={{ width: `${percent}%` }} />
                                </span>
                              </span>
                            </button>
                          </motion.li>
                        );
                      })}
                    </ul>
                  )}
                </Card>
              </motion.div>
            ) : (
              <motion.div
                key="no-selection"
                className="detail-stack"
                initial={{ opacity: 0, y: reduced ? 0 : 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? 0 : 0.22, ease: easePremium }}
              >
                <Card className="detail-card" pad={false}>
                  <div className="detail-empty">
                    <strong>Select a section</strong>
                    Choose any heading or leaf in the outline to inspect its source text and
                    linked requirements.
                  </div>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <Card className="checklist-card" pad={false}>
          <div className="card-head">
            <div>
              <h2>Completeness checklist</h2>
              <p>Expected specification sections detected during ingestion.</p>
            </div>
            <Chip tone={missing.length ? "amber" : checklistTotal ? "green" : "outline"}>
              {checklistTotal ? `${found.length} / ${checklistTotal}` : "No checklist"}
            </Chip>
          </div>

          {checklistTotal === 0 ? (
            <div className="link-empty">
              No checklist was produced for this document. Re-upload the source to rebuild it.
            </div>
          ) : (
            <>
              <div className="checklist-grid">
                <div className="checklist-col">
                  <h3>
                    <CheckCircle size={14} style={{ color: "var(--green)" }} />
                    Found
                    <span className="checklist-col__count">{found.length}</span>
                  </h3>
                  <motion.div
                    className="chip-wrap"
                    variants={staggerContainer}
                    initial="hidden"
                    animate="show"
                  >
                    {found.length === 0 ? (
                      <span style={{ color: "var(--muted)", fontSize: 12.5 }}>None detected</span>
                    ) : (
                      found.map((entry) => (
                        <motion.span key={entry} variants={staggerItem}>
                          <Chip tone="green" dot>
                            {entry}
                          </Chip>
                        </motion.span>
                      ))
                    )}
                  </motion.div>
                </div>

                <div className="checklist-col">
                  <h3>
                    <AlertTriangle size={14} style={{ color: "var(--muted-2)" }} />
                    Missing
                    <span className="checklist-col__count">{missing.length}</span>
                  </h3>
                  <motion.div
                    className="chip-wrap"
                    variants={staggerContainer}
                    initial="hidden"
                    animate="show"
                  >
                    {missing.length === 0 ? (
                      <span style={{ color: "var(--muted)", fontSize: 12.5 }}>
                        Nothing missing — the document looks complete.
                      </span>
                    ) : (
                      missing.map((entry) => (
                        <motion.span key={entry} variants={staggerItem}>
                          <Chip tone="outline" dot>
                            {entry}
                          </Chip>
                        </motion.span>
                      ))
                    )}
                  </motion.div>
                </div>
              </div>

              <div className="checklist-progress">
                <div className="mini-progress" aria-hidden="true">
                  <motion.div
                    className="mini-progress__fill"
                    initial={{ width: 0 }}
                    animate={{ width: `${checklistPercent}%` }}
                    transition={{
                      duration: reduced ? 0 : 0.7,
                      ease: easePremium,
                      delay: 0.1,
                    }}
                  />
                </div>
                <span>{checklistPercent}% complete</span>
              </div>
            </>
          )}
        </Card>

        <div style={{ marginTop: 22, display: "flex", justifyContent: "flex-end" }}>
          <Link to={`/p/${id}/review`} className="btn btn--ghost">
            Continue to review <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  );
}
