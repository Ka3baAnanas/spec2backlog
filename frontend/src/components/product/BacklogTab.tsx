import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type {
  BacklogResponse,
  Coverage,
  EpicNode,
  ItemStatus,
  Section,
  StoryNode,
} from "../../api/client";
import { api } from "../../api/client";
import { errorMessage } from "../../lib/errors";
import { confidenceMeta, itemStatusMeta } from "../../lib/status";
import { Button } from "../Button";
import { Chip } from "../Chip";
import { useToast } from "../Toast";
import { CheckCircle, ChevronDown, Download, ListChecks, Sparkles } from "../Icons";
import { StoryDrawer } from "./StoryDrawer";

const FILTERS: { id: "all" | ItemStatus; label: string }[] = [
  { id: "all", label: "All" },
  { id: "proposed", label: "Proposed" },
  { id: "approved", label: "Approved" },
  { id: "edited", label: "Edited" },
  { id: "rejected", label: "Rejected" },
];

function priorityTone(priority: string): "red" | "amber" | "outline" {
  if (priority === "must") return "red";
  if (priority === "should") return "amber";
  return "outline";
}

function storiesOf(epic: EpicNode): StoryNode[] {
  return epic.features?.length ? epic.features.flatMap((feature) => feature.stories) : epic.stories;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function BacklogTab({
  projectId,
  projectName,
  backlog,
  coverage,
  sections,
  loading,
  error,
  onRefresh,
}: {
  projectId: string;
  projectName: string;
  backlog?: BacklogResponse;
  coverage?: Coverage;
  sections: Section[];
  loading: boolean;
  error?: unknown;
  onRefresh: () => void;
}) {
  const reduced = useReducedMotion();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [selectedEpicId, setSelectedEpicId] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | ItemStatus>("all");
  const [selectedStoryId, setSelectedStoryId] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);

  const epics = backlog?.epics ?? [];

  useEffect(() => {
    if (!epics.length) {
      setSelectedEpicId(null);
      return;
    }
    setSelectedEpicId((current) =>
      current && epics.some((epic) => epic.id === current) ? current : epics[0].id,
    );
  }, [epics]);

  const selectedEpic = useMemo(
    () => epics.find((epic) => epic.id === selectedEpicId) ?? epics[0] ?? null,
    [epics, selectedEpicId],
  );

  const featureGroups = useMemo(() => {
    if (!selectedEpic) return [];
    const features = selectedEpic.features?.length
      ? selectedEpic.features
      : [{ id: `${selectedEpic.id}-all`, title: "", body: {}, stories: selectedEpic.stories }];
    return features
      .map((feature) => ({
        id: feature.id,
        title: feature.title,
        summary: String((feature.body as Record<string, unknown>)?.summary ?? ""),
        stories:
          filter === "all"
            ? feature.stories
            : feature.stories.filter((story) => story.status === filter),
      }))
      .filter((feature) => feature.stories.length > 0);
  }, [selectedEpic, filter]);

  const filteredCount = featureGroups.reduce((total, feature) => total + feature.stories.length, 0);
  const allStories = useMemo(() => epics.flatMap((epic) => storiesOf(epic)), [epics]);
  const selectedStory = useMemo(
    () => allStories.find((story) => story.id === selectedStoryId) ?? null,
    [allStories, selectedStoryId],
  );

  const sourceSection = useMemo(
    () => sections.find((section) => section.id === selectedStory?.source_section_id),
    [sections, selectedStory],
  );

  const contextQuery = useQuery({
    queryKey: ["context", selectedStory?.source_section_id],
    queryFn: () => api.context(selectedStory!.source_section_id),
    enabled: Boolean(selectedStory),
  });

  const traceQuery = useQuery({
    queryKey: ["trace", selectedStory?.id],
    queryFn: () => api.itemTrace(selectedStory!.id),
    enabled: Boolean(selectedStory),
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: ({ title, body }: { title: string; body: Record<string, unknown> }) =>
      api.patchItem(selectedStory!.id, { title, body }),
    onSuccess: () => {
      toast({ tone: "success", title: "Story saved", message: "The backlog now reflects your edit." });
      void queryClient.invalidateQueries({ queryKey: ["backlog", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["trace", selectedStory?.id] });
    },
    onError: (error) => toast({ tone: "error", title: "Could not save", message: errorMessage(error) }),
  });

  const decideMutation = useMutation({
    mutationFn: ({
      status,
      title,
      body,
    }: {
      status: ItemStatus;
      title: string;
      body: Record<string, unknown>;
    }) => api.patchItem(selectedStory!.id, { title, body, status }),
    onSuccess: (_, variables) => {
      toast({
        tone: variables.status === "rejected" ? "info" : "success",
        title: variables.status === "rejected" ? "Story rejected" : "Story approved",
        message: `${selectedStory?.key ?? "Story"} is now ${variables.status}.`,
      });
      setSelectedStoryId(null);
      void queryClient.invalidateQueries({ queryKey: ["backlog", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["coverage", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
    },
    onError: (error) => toast({ tone: "error", title: "Could not save decision", message: errorMessage(error) }),
  });

  const regenerateMutation = useMutation({
    mutationFn: (instruction: string) => api.regenerateItem(selectedStory!.id, instruction),
    onSuccess: () => {
      toast({ tone: "success", title: "Story regenerated", message: "The item was replaced using your instruction." });
      void queryClient.invalidateQueries({ queryKey: ["backlog", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["trace", selectedStory?.id] });
      void queryClient.invalidateQueries({ queryKey: ["context", selectedStory?.source_section_id] });
      onRefresh();
    },
    onError: (error) => toast({ tone: "error", title: "Regeneration failed", message: errorMessage(error) }),
  });

  const approveAllMutation = useMutation({
    mutationFn: () => api.approveBacklog(projectId),
    onSuccess: (result) => {
      toast({
        tone: "success",
        title: "Backlog approved",
        message: `${result.approved} item(s) approved. You can export now.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["backlog", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["coverage", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      onRefresh();
    },
    onError: (error) => toast({ tone: "error", title: "Could not approve backlog", message: errorMessage(error) }),
  });

  const exportMutation = useMutation({
    mutationFn: (format: "xlsx" | "docx") => api.exportFile(projectId, format),
    onSuccess: (blob, format) => {
      const slug = projectName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
      downloadBlob(blob, `${slug || "backlog"}.${format}`);
      toast({ tone: "success", title: "Export ready", message: `Downloaded ${format.toUpperCase()} backlog.` });
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      setExportOpen(false);
    },
    onError: (error) => toast({ tone: "error", title: "Export failed", message: errorMessage(error) }),
  });

  const approvedCount = allStories.filter((story) => story.status === "approved" || story.status === "edited").length;
  const coveragePercent = coverage?.coverage ?? 0;

  const drawerBusy =
    saveMutation.isPending || decideMutation.isPending || regenerateMutation.isPending;

  return (
    <div className="backlog">
      <div className="backlog-top">
        <div className="backlog-filters" role="group" aria-label="Filter stories by status">
          {FILTERS.map((entry) => (
            <button
              key={entry.id}
              type="button"
              className={`filter-pill ${filter === entry.id ? "is-active" : ""}`.trim()}
              onClick={() => setFilter(entry.id)}
            >
              {entry.label}
            </button>
          ))}
        </div>

        <div className="backlog-top__right">
          <Chip tone={coveragePercent >= 99 ? "green" : coveragePercent > 0 ? "blue" : "outline"}>
            Coverage {coveragePercent}%
          </Chip>
          <Chip tone="outline">
            {approvedCount}/{allStories.length} approved
          </Chip>
          <div className="export-menu">
            <Button
              variant="secondary"
              size="sm"
              icon={<Download size={14} />}
              onClick={() => setExportOpen((open) => !open)}
              aria-expanded={exportOpen}
            >
              Export <ChevronDown size={13} />
            </Button>
            <AnimatePresence>
              {exportOpen && (
                <motion.div
                  className="export-menu__panel"
                  initial={{ opacity: 0, y: reduced ? 0 : -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: reduced ? 0 : -4 }}
                  transition={{ duration: reduced ? 0 : 0.16 }}
                >
                  <button
                    type="button"
                    onClick={() => exportMutation.mutate("xlsx")}
                    disabled={exportMutation.isPending}
                  >
                    Excel <span>.xlsx</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => exportMutation.mutate("docx")}
                    disabled={exportMutation.isPending}
                  >
                    Word <span>.docx</span>
                  </button>
                  <button type="button" disabled>
                    Jira <span className="soon-badge">Soon</span>
                  </button>
                  <button type="button" disabled>
                    Azure DevOps <span className="soon-badge">Soon</span>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
          <Button
            variant="primary"
            size="sm"
            icon={<CheckCircle size={14} />}
            loading={approveAllMutation.isPending}
            onClick={() => approveAllMutation.mutate()}
            disabled={!allStories.length}
          >
            Approve all
          </Button>
        </div>
      </div>

      {error ? (
        <div className="backlog-empty card card--pad">
          <ListChecks size={22} />
          <strong>Could not load backlog</strong>
          <p>{errorMessage(error)}</p>
          <Button variant="secondary" size="sm" onClick={onRefresh}>
            Retry
          </Button>
        </div>
      ) : loading ? (
        <div className="backlog-empty card card--pad">
          <Sparkles size={20} />
          <strong>Loading backlog...</strong>
        </div>
      ) : !epics.length ? (
        <div className="backlog-empty card card--pad">
          <ListChecks size={22} />
          <strong>No backlog yet</strong>
          <p>Approve the context and start generation from the Pipeline tab.</p>
        </div>
      ) : (
        <div className="backlog-layout">
          <aside className="backlog-epics" aria-label="Epics">
            <div className="backlog-epics__head">
              <h2>Epics</h2>
              <Chip tone="outline">{epics.length}</Chip>
            </div>
            <div className="backlog-epics__list">
              {epics.map((epic) => {
                const epicStories = storiesOf(epic);
                const approved = epicStories.filter(
                  (story) => story.status === "approved" || story.status === "edited",
                ).length;
                const percent = epicStories.length ? Math.round((approved / epicStories.length) * 100) : 0;
                return (
                  <button
                    key={epic.id}
                    type="button"
                    className={`backlog-epic ${epic.id === selectedEpic?.id ? "is-active" : ""}`.trim()}
                    onClick={() => setSelectedEpicId(epic.id)}
                  >
                    <span className="backlog-epic__key">{epic.key}</span>
                    <span className="backlog-epic__title">{epic.title || "Untitled epic"}</span>
                    <span className="backlog-epic__bar" aria-hidden="true">
                      <i style={{ width: `${percent}%` }} />
                    </span>
                    <span className="backlog-epic__meta">
                      {approved}/{epic.stories.length} approved · {epic.stories.length} stories
                    </span>
                  </button>
                );
              })}
            </div>
          </aside>

          <section className="backlog-stories" aria-label="Stories">
            <div className="backlog-stories__head">
              <div>
                <span className="backlog-stories__key">{selectedEpic?.key}</span>
                <h2>{selectedEpic?.title || "Epic"}</h2>
                <p>
                  {String((selectedEpic?.body as Record<string, unknown>)?.summary ?? "") ||
                    `${filteredCount} story${filteredCount === 1 ? "" : "ies"}`}
                  {filter !== "all" ? ` · ${filter}` : ""}
                </p>
              </div>
            </div>

            {featureGroups.length === 0 ? (
              <div className="backlog-empty card card--pad">
                <strong>No stories in this filter</strong>
                <p>Switch the status filter to see the rest of the epic.</p>
              </div>
            ) : (
              <div className="backlog-features">
                {featureGroups.map((feature) => (
                  <section key={feature.id} className="backlog-feature">
                    {feature.title && (
                      <div className="backlog-feature__head">
                        <div>
                          <h3>{feature.title}</h3>
                          {feature.summary && <p>{feature.summary}</p>}
                        </div>
                        <span>{feature.stories.length}</span>
                      </div>
                    )}
                    <div className="story-list">
                      {feature.stories.map((story) => (
                        <StoryCard
                          key={story.id}
                          story={story}
                          sourceSection={sections.find((section) => section.id === story.source_section_id)}
                          onOpen={() => setSelectedStoryId(story.id)}
                        />
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      <StoryDrawer
        story={selectedStory}
        sourceSection={sourceSection}
        context={contextQuery.data}
        trace={traceQuery.data}
        loadingContext={contextQuery.isLoading}
        loadingTrace={traceQuery.isLoading}
        busy={drawerBusy}
        onClose={() => setSelectedStoryId(null)}
        onSave={(title, body) => saveMutation.mutate({ title, body })}
        onDecide={(status, title, body) => decideMutation.mutate({ status, title, body })}
        onRegenerate={(instruction) => regenerateMutation.mutate(instruction)}
      />
    </div>
  );
}

function StoryCard({
  story,
  sourceSection,
  onOpen,
}: {
  story: StoryNode;
  sourceSection?: Section;
  onOpen: () => void;
}) {
  const body = story.body;
  const criteria = Array.isArray(body.acceptance_criteria) ? body.acceptance_criteria : [];
  const priority = String(body.priority ?? "should");
  const estimate = String(body.estimate ?? "");
  const description = String(body.description ?? "");
  const confidence = confidenceMeta(story.confidence);
  return (
    <motion.button
      type="button"
      className="story-card card"
      onClick={onOpen}
      whileHover={{ y: -1 }}
      transition={{ duration: 0.16 }}
    >
      <div className="story-card__top">
        <span className="story-card__key">{story.key}</span>
        <Chip tone={itemStatusMeta(story.status).tone}>{itemStatusMeta(story.status).label}</Chip>
      </div>
      <h3>{story.title}</h3>
      {description && <p className="story-card__description">{description}</p>}

      <div className="story-card__meta">
        <Chip tone={priorityTone(priority)}>{priority}</Chip>
        {estimate && <Chip tone="outline">{estimate}</Chip>}
        <span
          className="story-card__confidence"
          title={`${Math.round(story.confidence * 100)}% confidence`}
        >
          <span className="mini-progress" aria-hidden="true">
            <i style={{ width: `${Math.round(story.confidence * 100)}%` }} />
          </span>
          {confidence.label} confidence
        </span>
        {sourceSection && (
          <span className="story-card__source">
            §{sourceSection.number || "n/a"} {sourceSection.title}
          </span>
        )}
      </div>

      {criteria.length > 0 && (
        <ul className="story-card__criteria">
          {criteria.slice(0, 3).map((criterion) => (
            <li key={String(criterion)}>{String(criterion)}</li>
          ))}
          {criteria.length > 3 && <li className="muted-small">+{criteria.length - 3} more criteria</li>}
        </ul>
      )}

      <div className="story-card__tests">
        <span>
          {story.tests.length} test{story.tests.length === 1 ? "" : "s"}
        </span>
        {story.tests.slice(0, 2).map((test) => (
          <span key={test.id} className="story-card__test">
            {test.key}
          </span>
        ))}
      </div>
    </motion.button>
  );
}

