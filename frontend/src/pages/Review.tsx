import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Item } from "../api/client";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Chip } from "../components/Chip";
import { ArrowLeft, CheckCircle, Clock, ListChecks, Refresh, XCircle } from "../components/Icons";
import { ReviewCard } from "../components/ReviewCard";
import { Skeleton, SkeletonLines } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { errorMessage } from "../lib/errors";
import { easePremium, softSpring } from "../lib/motion";

type TabId = "all" | "proposed" | "approved" | "rejected";

export default function Review() {
  const { id = "" } = useParams();
  const reduced = useReducedMotion();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [tab, setTab] = useState<TabId>("all");
  const [refreshing, setRefreshing] = useState(false);

  const projectsQuery = useQuery({ queryKey: ["projects"], queryFn: api.projects });
  const itemsQuery = useQuery({
    queryKey: ["items", id],
    queryFn: () => api.items(id),
    enabled: Boolean(id),
  });
  const treeQuery = useQuery({
    queryKey: ["tree", id],
    queryFn: () => api.tree(id),
    enabled: Boolean(id),
  });

  const project = projectsQuery.data?.find((entry) => entry.id === id);
  const items = itemsQuery.data ?? [];
  const tree = treeQuery.data ?? [];

  const nodeById = useMemo(
    () => new Map(tree.map((node) => [node.id, node])),
    [tree],
  );

  const counts = useMemo(() => {
    const approved = items.filter((item) => item.status === "approved").length;
    const edited = items.filter((item) => item.status === "edited").length;
    const rejected = items.filter((item) => item.status === "rejected").length;
    const proposed = items.filter((item) => item.status === "proposed").length;
    return {
      approved,
      edited,
      rejected,
      proposed,
      validated: approved + edited,
    };
  }, [items]);

  const percent = items.length
    ? Math.round((counts.validated / items.length) * 100)
    : 0;

  const tabs = useMemo(
    () =>
      [
        { id: "all" as const, label: "All", count: items.length },
        { id: "proposed" as const, label: "Proposed", count: counts.proposed },
        { id: "approved" as const, label: "Approved", count: counts.validated },
        { id: "rejected" as const, label: "Rejected", count: counts.rejected },
      ] satisfies { id: TabId; label: string; count: number }[],
    [items.length, counts],
  );

  const filtered = useMemo(() => {
    if (tab === "all") return items;
    if (tab === "approved") {
      return items.filter((item) => item.status === "approved" || item.status === "edited");
    }
    return items.filter((item) => item.status === tab);
  }, [items, tab]);

  const refreshQueue = async () => {
    if (refreshing) return;
    setRefreshing(true);
    try {
      await queryClient.invalidateQueries({ queryKey: ["items", id] });
      toast({
        tone: "info",
        title: "Review queue refreshed",
        message: "Latest generated items and decisions are loaded.",
      });
    } finally {
      setRefreshing(false);
    }
  };

  const act = async (item: Item, status: "approved" | "rejected") => {
    try {
      await api.review(item.id, { status });
      queryClient.setQueryData<Item[]>(["items", id], (previous) =>
        previous?.map((entry) => (entry.id === item.id ? { ...entry, status } : entry)),
      );
      void queryClient.invalidateQueries({ queryKey: ["items", id] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    } catch (error) {
      toast({
        tone: "error",
        title: "Could not save the decision",
        message: errorMessage(error),
      });
      throw error;
    }
  };

  const loading = itemsQuery.isLoading || projectsQuery.isLoading;

  return (
    <div className="page">
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
          <span>Review</span>
        </div>

        <div className="page-head">
          <div>
            <div className="eyebrow" style={{ marginBottom: 10 }}>
              <span className="eyebrow__dot" aria-hidden="true" />
              Human validation
            </div>
            <h1>Validate the backlog</h1>
            <p className="page-head__sub">
              Approve, edit or reject each item. Every decision is logged and only validated
              items are exported.
            </p>
          </div>
          <div className="page-head__actions">
            <Link to={`/p/${id}`} className="btn btn--secondary">
              <ArrowLeft size={15} />
              Back to workspace
            </Link>
            <Button
              variant="accent"
              icon={<Refresh size={15} />}
              loading={refreshing}
              onClick={() => void refreshQueue()}
            >
              Refresh queue
            </Button>
          </div>
        </div>

        {loading ? (
          <>
            <div className="review-top">
              <div className="card progress-card">
                <Skeleton width={90} height={12} />
                <Skeleton width="42%" height={30} />
                <Skeleton height={8} radius={999} />
              </div>
              <div className="card review-stats">
                <SkeletonLines lines={4} />
              </div>
            </div>
            <div className="review-list">
              {Array.from({ length: 3 }).map((_, index) => (
                <div key={index} className="card review-card">
                  <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                    <Skeleton width={52} height={20} radius={999} />
                    <Skeleton width="46%" height={16} />
                  </div>
                  <div style={{ marginTop: 16 }}>
                    <SkeletonLines lines={2} />
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : itemsQuery.isError ? (
          <Card className="state-card" pad={false}>
            <strong>Could not load the review queue</strong>
            <p>{errorMessage(itemsQuery.error)}</p>
          </Card>
        ) : (
          <>
            <div className="review-top">
              <Card className="progress-card" pad={false}>
                <div className="progress-card__row">
                  <div>
                    <div className="progress-card__label">Validated items</div>
                    <div className="progress-card__value">
                      {counts.validated}
                      <small>/ {items.length} items</small>
                    </div>
                  </div>
                  <Chip tone={percent === 100 && items.length > 0 ? "green" : "yellow"}>
                    {percent}% complete
                  </Chip>
                </div>
                <div
                  className="progress-track"
                  role="progressbar"
                  aria-valuenow={percent}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label="Validation progress"
                >
                  <motion.div
                    className="progress-fill"
                    initial={false}
                    animate={{ width: `${percent}%` }}
                    transition={{ duration: reduced ? 0 : 0.6, ease: easePremium }}
                  />
                </div>
                <div className="progress-card__legend">
                  <Chip tone="yellow" dot>
                    Proposed · {counts.proposed}
                  </Chip>
                  <Chip tone="green" dot>
                    Approved · {counts.approved}
                  </Chip>
                  <Chip tone="amber" dot>
                    Edited · {counts.edited}
                  </Chip>
                  <Chip tone="red" dot>
                    Rejected · {counts.rejected}
                  </Chip>
                </div>
              </Card>

              <Card className="review-stats" pad={false}>
                <div className="review-stat">
                  <span>
                    <Clock size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
                    Awaiting decision
                  </span>
                  <strong>{counts.proposed}</strong>
                </div>
                <div className="review-stat">
                  <span>
                    <CheckCircle size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
                    Approved
                  </span>
                  <strong>{counts.approved}</strong>
                </div>
                <div className="review-stat">
                  <span>
                    <ListChecks size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
                    Edited
                  </span>
                  <strong>{counts.edited}</strong>
                </div>
                <div className="review-stat">
                  <span>
                    <XCircle size={13} style={{ verticalAlign: -2, marginRight: 6 }} />
                    Rejected
                  </span>
                  <strong>{counts.rejected}</strong>
                </div>
              </Card>
            </div>

            <div className="review-toolbar">
              <div className="tab-bar" role="tablist" aria-label="Filter review items">
                {tabs.map((entry) => {
                  const active = tab === entry.id;
                  return (
                    <button
                      key={entry.id}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      className={`tab ${active ? "is-active" : ""}`.trim()}
                      onClick={() => setTab(entry.id)}
                    >
                      {active && (
                        <motion.span
                          layoutId="review-tab-pill"
                          className="tab__pill"
                          transition={reduced ? { duration: 0 } : softSpring}
                          aria-hidden="true"
                        />
                      )}
                      <span className="tab__label">
                        {entry.label}
                        <span className="tab__count">{entry.count}</span>
                      </span>
                    </button>
                  );
                })}
              </div>

              <span style={{ fontSize: 12.5, color: "var(--muted)" }}>
                Showing {filtered.length} of {items.length} items
              </span>
            </div>

            {items.length === 0 ? (
              <div className="review-empty">
                <strong>No backlog items yet</strong>
                Generate the backlog from the workspace, then come back to validate it.
                <div style={{ marginTop: 18 }}>
                  <Link to={`/p/${id}`} className="btn btn--primary">
                    Open workspace
                  </Link>
                </div>
              </div>
            ) : filtered.length === 0 ? (
              <div className="review-empty">
                <strong>Nothing in this filter</strong>
                Switch tabs to see the rest of the review queue.
              </div>
            ) : (
              <motion.div className="review-list" layout={!reduced}>
                <AnimatePresence initial={false} mode="popLayout">
                  {filtered.map((item, index) => (
                    <motion.div
                      key={item.id}
                      layout={!reduced}
                      initial={{ opacity: 0, y: reduced ? 0 : 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{
                        opacity: 0,
                        height: 0,
                        marginBottom: -12,
                        scale: reduced ? 1 : 0.98,
                      }}
                      transition={{
                        duration: reduced ? 0 : 0.24,
                        ease: easePremium,
                        delay: reduced ? 0 : Math.min(index, 10) * 0.04,
                      }}
                      style={{ overflow: "hidden" }}
                    >
                      <ReviewCard
                        item={item}
                        projectId={id}
                        sourceNode={nodeById.get(item.source_node_id)}
                        onAction={(status) => act(item, status)}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              </motion.div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
