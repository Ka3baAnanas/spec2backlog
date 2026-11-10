import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type Node } from "../api/client";
import { retryFailedLeaves, runPipeline } from "../api/run";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Chip } from "../components/Chip";
import { ActivityLog } from "../components/live/ActivityLog";
import { LeafGrid } from "../components/live/LeafGrid";
import { LeafInspector } from "../components/live/LeafInspector";
import { LiveDocumentPanel } from "../components/live/LiveDocumentPanel";
import { MeaningGraph } from "../components/live/MeaningGraph";
import { PartialSuccess } from "../components/live/PartialSuccess";
import { PipelineChecklist } from "../components/live/PipelineChecklist";
import { AlertTriangle, ArrowLeft, ListChecks, Play, Sparkles } from "../components/Icons";
import { Skeleton, SkeletonLines } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { useRunStream, type RunConnection } from "../hooks/useRunStream";
import { errorMessage } from "../lib/errors";
import { easePremium } from "../lib/motion";
import { projectStatusMeta } from "../lib/status";

const CONNECTION_META: Record<RunConnection, { label: string; tone: "green" | "amber" | "blue" | "yellow" | "red" | "default" }> = {
  idle: { label: "Idle", tone: "default" },
  connecting: { label: "Connecting", tone: "blue" },
  live: { label: "Live", tone: "green" },
  reconnecting: { label: "Reconnecting", tone: "amber" },
  replaying: { label: "Replay 20Ã—", tone: "yellow" },
  error: { label: "Stream error", tone: "red" },
};

function LiveSkeleton() {
  return (
    <div className="page">
      <div className="container">
        <div className="live-skeleton-head">
          <Skeleton width={90} height={12} />
          <Skeleton width="42%" height={30} />
        </div>
        <div className="live-layout">
          {Array.from({ length: 3 }).map((_, column) => (
            <div className="live-column" key={column}>
              <Card className="live-panel live-panel--pad">
                <Skeleton width={120} height={16} />
                <div style={{ marginTop: 18 }}>
                  <SkeletonLines lines={column === 1 ? 12 : 7} />
                </div>
              </Card>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function Live() {
  const { id = "" } = useParams();
  const [searchParams] = useSearchParams();
  const requestedNode = searchParams.get("node");
  const reduced = useReducedMotion();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { state, connection, replaying, replay, error: streamError } = useRunStream(id);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectionPinned, setSelectionPinned] = useState(false);
  const selectNode = (node: Node) => {
    setSelectedId(node.id);
    setSelectionPinned(true);
  };

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const treeQuery = useQuery({
    queryKey: ["tree", id],
    queryFn: () => api.tree(id),
    enabled: Boolean(id),
  });
  const itemsQuery = useQuery({
    queryKey: ["items", id],
    queryFn: () => api.items(id),
    enabled: Boolean(id),
  });

  const project = projectsQuery.data?.find((entry) => entry.id === id);
  const tree = treeQuery.data ?? [];
  const items = itemsQuery.data ?? [];
  const nodesById = useMemo(() => new Map(tree.map((node) => [node.id, node])), [tree]);
  const leaves = useMemo(
    () => tree.filter((node) => node.is_leaf && !node.is_global && !node.is_front_matter),
    [tree],
  );
  const graphLeaves = useMemo(
    () => tree.filter((node) => node.is_leaf && !node.is_front_matter),
    [tree],
  );
  const selectedNode = selectedId ? nodesById.get(selectedId) ?? null : null;

  const startRun = useMutation({
    mutationFn: () => runPipeline(id),
    onSuccess: () => {
      toast({
        tone: "info",
        title: "Pipeline started",
        message: "Events will stream into this page as each stage runs.",
      });
    },
    onError: (caught) => {
      toast({ tone: "error", title: "Could not start the pipeline", message: errorMessage(caught) });
    },
  });

  const retryFailed = useMutation({
    mutationFn: () => retryFailedLeaves(id),
    onSuccess: (result) => {
      toast({
        tone: "success",
        title: "Retry started",
        message: `${result.items} item${result.items === 1 ? "" : "s"} created for the failed leaves.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["items", id] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (caught) => {
      toast({ tone: "error", title: "Retry failed", message: errorMessage(caught) });
    },
  });

  useEffect(() => {
    if (requestedNode && tree.some((node) => node.id === requestedNode)) {
      setSelectedId(requestedNode);
      setSelectionPinned(true);
    }
  }, [requestedNode, tree]);

  useEffect(() => {
    if (selectionPinned) return;
    if (state.currentNodeId) setSelectedId(state.currentNodeId);
  }, [state.currentNodeId, selectionPinned]);

  const generationDone = state.stages.generation.status === "done";
  useEffect(() => {
    if (!generationDone) return;
    void queryClient.invalidateQueries({ queryKey: ["items", id] });
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
  }, [generationDone, id, queryClient]);

  if ((projectsQuery.isLoading && !project) || treeQuery.isLoading) return <LiveSkeleton />;

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

  if (treeQuery.isError) {
    return (
      <div className="page">
        <div className="container">
          <Card className="state-card" pad={false}>
            <strong>Could not load the document</strong>
            <p>{errorMessage(treeQuery.error)}</p>
          </Card>
        </div>
      </div>
    );
  }

  const status = projectStatusMeta(project?.status ?? "created");
  const connectionMeta = CONNECTION_META[connection];
  const idle = state.events.length === 0 && !replaying && !state.error;

  return (
    <div className="page live-page">
      <div className="container">
        <div className="breadcrumb">
          <Link to="/">Projects</Link>
          <span aria-hidden="true">/</span>
          <Link to={`/p/${id}`} className="breadcrumb__project">
            {project?.name ?? "Workspace"}
          </Link>
          <span className="breadcrumb__sep-project" aria-hidden="true">
            /
          </span>
          <span>Live run</span>
        </div>

        <div className="page-head live-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 10 }}>
              <span className="eyebrow__dot" aria-hidden="true" />
              Live run Â· {status.label}
            </div>
            <h1>{project?.name ?? "Live pipeline"}</h1>
            <p className="page-head__sub">
              Every highlight, counter and link below is driven by a backend run event.
            </p>
          </div>
          <div className="page-head__actions live-head__actions">
            <Chip tone={connectionMeta.tone} dot>
              {connectionMeta.label}
            </Chip>
            <Link to={`/p/${id}`} className="btn btn--secondary">
              <ArrowLeft size={15} />
              Workspace
            </Link>
            <Link to={`/p/${id}/review`} className="btn btn--secondary">
              <ListChecks size={15} />
              Review
            </Link>
            <Button
              variant="accent"
              icon={<Play size={15} />}
              loading={startRun.isPending}
              onClick={() => startRun.mutate()}
            >
              Run pipeline
            </Button>
          </div>
        </div>

        {streamError && (
          <div className="live-banner is-warning">
            <AlertTriangle size={16} />
            <span>{streamError}</span>
          </div>
        )}
        {state.error && (
          <div className="live-banner is-error">
            <AlertTriangle size={16} />
            <span>{state.error}</span>
          </div>
        )}

        {idle ? (
          <motion.div
            className="live-idle"
            initial={{ opacity: 0, y: reduced ? 0 : 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: reduced ? 0 : 0.25, ease: easePremium }}
          >
            <span className="live-idle__icon" aria-hidden="true">
              <Sparkles size={20} />
            </span>
            <div>
              <strong>No run events yet</strong>
              <p>
                Start the pipeline to ingest the tree, embed the leaves, build the meaning graph and
                generate the backlog. The page will fill in as events arrive.
              </p>
            </div>
            <Button
              variant="primary"
              icon={<Play size={15} />}
              loading={startRun.isPending}
              onClick={() => startRun.mutate()}
            >
              Run pipeline
            </Button>
          </motion.div>
        ) : null}

        <div className="live-layout">
          <div className="live-column live-column--document">
            <Card className="live-panel live-panel--document" pad={false}>
              <LiveDocumentPanel
                nodes={tree}
                state={state}
                selectedId={selectedId}
                currentNodeId={state.currentNodeId}
                onSelect={selectNode}
              />
            </Card>
          </div>

          <div className="live-column live-column--center">
            <Card className="live-panel live-panel--checklist" pad={false}>
              <div className="live-panel__head">
                <div>
                  <h2>Pipeline</h2>
                  <p>Live counters from the backend event data</p>
                </div>
                <Chip tone={generationDone ? "green" : connection === "live" ? "yellow" : "outline"} dot>
                  {generationDone ? "Complete" : connection === "live" ? "Running" : "Standby"}
                </Chip>
              </div>
              <PipelineChecklist state={state} projectStatus={project?.status} />
            </Card>

            <Card className="live-panel live-panel--leaves" pad={false}>
              <div className="live-panel__head">
                <div>
                  <h2>Leaf grid</h2>
                  <p>One tile per generated leaf Â· colors follow real lifecycle events</p>
                </div>
              </div>
              <LeafGrid
                leaves={leaves}
                state={state}
                selectedId={selectedId}
                onSelect={selectNode}
              />
            </Card>

            <PartialSuccess
              leaves={leaves}
              state={state}
              retrying={retryFailed.isPending}
              onRetry={() => retryFailed.mutate()}
            />

            <Card className="live-panel live-panel--graph" pad={false}>
              <MeaningGraph
                leaves={graphLeaves}
                state={state}
                selectedId={selectedId}
                onSelect={selectNode}
              />
            </Card>

            <Card className="live-panel live-panel--log" pad={false}>
              <ActivityLog
                events={state.events}
                replay={() => void replay()}
                replaying={replaying}
              />
            </Card>
          </div>

          <div className="live-column live-column--inspector">
            <Card className="live-panel live-panel--inspector" pad={false}>
              <LeafInspector
                projectId={id}
                selectedNode={selectedNode}
                nodesById={nodesById}
                edges={state.edges}
                items={items}
                onSelect={selectNode}
              />
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
