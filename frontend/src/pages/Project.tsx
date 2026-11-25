import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, type Section, type SectionRole } from "../api/client";
import { Card } from "../components/Card";
import { Chip } from "../components/Chip";
import { History } from "../components/Icons";
import { ActivityDrawer } from "../components/product/ActivityDrawer";
import { AskTab } from "../components/product/AskTab";
import { BacklogTab } from "../components/product/BacklogTab";
import { PipelineTab } from "../components/product/PipelineTab";
import { QuestionsTab } from "../components/product/QuestionsTab";
import { Skeleton, SkeletonLines } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { useRunStreamContext } from "../hooks/useRunStream";
import { errorMessage } from "../lib/errors";
import { softSpring } from "../lib/motion";
import { projectStatusMeta } from "../lib/status";

type TabId = "pipeline" | "backlog" | "questions" | "ask";

const TABS: { id: TabId; label: string; beta?: boolean }[] = [
  { id: "pipeline", label: "Pipeline" },
  { id: "backlog", label: "Backlog" },
  { id: "questions", label: "Open questions" },
  { id: "ask", label: "Ask", beta: true },
];

function statusStepIndex(status: string): number {
  switch (status) {
    case "uploaded":
    case "parsed":
      return 0;
    case "structured":
      return 1;
    case "linked":
    case "awaiting_context_approval":
      return 2;
    case "generating":
      return 3;
    case "generated":
    case "in_review":
    case "approved":
    case "exported":
      return 4;
    default:
      return 0;
  }
}

function ProjectSkeleton() {
  return (
    <div className="page">
      <div className="container">
        <div className="project-skeleton">
          <Skeleton width={120} height={12} />
          <Skeleton width="46%" height={34} />
          <Skeleton width={320} height={18} />
        </div>
        <div className="card project-skeleton-card">
          <SkeletonLines lines={6} />
        </div>
      </div>
    </div>
  );
}

export default function Project() {
  const { id = "" } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const toast = useToast();
  const reduced = useReducedMotion();

  const rawTab = searchParams.get("tab");
  const tab: TabId = TABS.some((entry) => entry.id === rawTab) ? (rawTab as TabId) : "pipeline";

  const setTab = useCallback(
    (next: TabId) => {
      const params = new URLSearchParams(searchParams);
      if (next === "pipeline") params.delete("tab");
      else params.set("tab", next);
      setSearchParams(params, { replace: true });
      window.scrollTo({ top: 0, behavior: "auto" });
    },
    [searchParams, setSearchParams],
  );

  const projectQuery = useQuery({
    queryKey: ["project", id],
    queryFn: () => api.project(id),
    enabled: Boolean(id),
  });
  const documentQuery = useQuery({
    queryKey: ["document", id],
    queryFn: () => api.document(id),
    enabled: Boolean(id),
    retry: false,
  });
  const sectionsQuery = useQuery({
    queryKey: ["sections", id],
    queryFn: () => api.sections(id),
    enabled: Boolean(id),
  });
  const linksQuery = useQuery({
    queryKey: ["links", id],
    queryFn: () => api.links(id),
    enabled: Boolean(id),
  });
  const pipelineQuery = useQuery({
    queryKey: ["pipeline", id],
    queryFn: () => api.pipelineStatus(id),
    enabled: Boolean(id),
    refetchInterval: (query) => (query.state.data?.status === "generating" ? 1200 : false),
  });
  const backlogQuery = useQuery({
    queryKey: ["backlog", id],
    queryFn: () => api.backlog(id),
    enabled: Boolean(id) && projectQuery.data?.status !== "generating",
  });
  const questionsQuery = useQuery({
    queryKey: ["questions", id],
    queryFn: () => api.questions(id),
    enabled: Boolean(id),
  });
  const coverageQuery = useQuery({
    queryKey: ["coverage", id],
    queryFn: () => api.coverage(id),
    enabled: Boolean(id),
  });

  const { state: runState } = useRunStreamContext();

  const project = projectQuery.data;
  const sections = sectionsQuery.data ?? [];
  const links = linksQuery.data ?? [];

  const [pinnedStep, setPinnedStep] = useState<number | null>(0);
  const [activityOpen, setActivityOpen] = useState(false);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(null);
  const startedGeneration = useRef(false);
  const navigatedToBacklog = useRef(false);

  const contextQuery = useQuery({
    queryKey: ["context", selectedSectionId],
    queryFn: () => api.context(selectedSectionId!),
    enabled: Boolean(selectedSectionId),
  });

  const roleMutation = useMutation({
    mutationFn: ({ section, role }: { section: Section; role: SectionRole }) =>
      api.patchSection(section.id, { role }),
    onSuccess: (updated) => {
      toast({
        tone: "info",
        title: "Role updated",
        message: `${updated.title || "Section"} is now ${updated.role}.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["sections", id] });
      void queryClient.invalidateQueries({ queryKey: ["context"] });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", id] });
      void queryClient.invalidateQueries({ queryKey: ["project", id] });
    },
    onError: (error) => toast({ tone: "error", title: "Could not change role", message: errorMessage(error) }),
  });

  const linkMutation = useMutation({
    mutationFn: ({ linkId, enabled }: { linkId: number; enabled: boolean }) =>
      api.patchLink(linkId, { enabled }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["links", id] });
      void queryClient.invalidateQueries({ queryKey: ["context"] });
    },
    onError: (error) => toast({ tone: "error", title: "Could not update link", message: errorMessage(error) }),
  });

  const saveManualContextMutation = useMutation({
    mutationFn: ({
      sectionId,
      title,
      text,
    }: {
      sectionId: string | null;
      title: string;
      text: string;
    }) =>
      sectionId
        ? api.updateManualContext(sectionId, { title, text })
        : api.createManualContext(id, { title, text }),
    onSuccess: (updated, variables) => {
      toast({
        tone: "success",
        title: variables.sectionId ? "Manual context updated" : "Manual context added",
        message: `${updated.title} is included in the global context of every prompt.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["sections", id] });
      void queryClient.invalidateQueries({ queryKey: ["context"] });
      void queryClient.invalidateQueries({ queryKey: ["project", id] });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", id] });
    },
    onError: (error) =>
      toast({ tone: "error", title: "Could not save manual context", message: errorMessage(error) }),
  });

  const saveInstructionsMutation = useMutation({
    mutationFn: ({ sectionId, text }: { sectionId: string; text: string }) =>
      api.patchSection(sectionId, { extra_instructions: text }),
    onSuccess: () => {
      toast({
        tone: "success",
        title: "Instructions saved",
        message: "They will be appended to this section's prompt at generation.",
      });
      void queryClient.invalidateQueries({ queryKey: ["sections", id] });
      void queryClient.invalidateQueries({ queryKey: ["context"] });
    },
    onError: (error) =>
      toast({ tone: "error", title: "Could not save instructions", message: errorMessage(error) }),
  });

  const deleteManualContextMutation = useMutation({
    mutationFn: (section: Section) => api.deleteManualContext(section.id),
    onSuccess: (_, section) => {
      toast({
        tone: "info",
        title: "Manual context deleted",
        message: `${section.title} was removed from the outline.`,
      });
      void queryClient.invalidateQueries({ queryKey: ["sections", id] });
      void queryClient.invalidateQueries({ queryKey: ["context"] });
      void queryClient.invalidateQueries({ queryKey: ["project", id] });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", id] });
    },
    onError: (error) =>
      toast({ tone: "error", title: "Could not delete manual context", message: errorMessage(error) }),
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      await api.approveContext(id);
      return api.generate(id);
    },
    onSuccess: () => {
      startedGeneration.current = true;
      navigatedToBacklog.current = false;
      setPinnedStep(null);
      toast({
        tone: "info",
        title: "Generation started",
        message: "Only requirement sections are being generated.",
      });
      void queryClient.invalidateQueries({ queryKey: ["project", id] });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", id] });
      void queryClient.invalidateQueries({ queryKey: ["backlog", id] });
      void queryClient.invalidateQueries({ queryKey: ["coverage", id] });
      void queryClient.invalidateQueries({ queryKey: ["questions", id] });
    },
    onError: (error) =>
      toast({ tone: "error", title: "Could not start generation", message: errorMessage(error) }),
  });

  const retryMutation = useMutation({
    mutationFn: () => api.retryFailed(id),
    onSuccess: () => {
      startedGeneration.current = true;
      navigatedToBacklog.current = false;
      setPinnedStep(null);
      toast({ tone: "info", title: "Retry started", message: "Only failed sections will run again." });
      void queryClient.invalidateQueries({ queryKey: ["pipeline", id] });
      void queryClient.invalidateQueries({ queryKey: ["project", id] });
      void queryClient.invalidateQueries({ queryKey: ["backlog", id] });
      void queryClient.invalidateQueries({ queryKey: ["coverage", id] });
      void queryClient.invalidateQueries({ queryKey: ["questions", id] });
    },
    onError: (error) => toast({ tone: "error", title: "Could not retry", message: errorMessage(error) }),
  });

  useEffect(() => {
    setSelectedSectionId((current) =>
      current && sections.some((section) => section.id === current) ? current : null,
    );
  }, [sections]);

  useEffect(() => {
    if (project?.status === "generating") startedGeneration.current = true;
  }, [project?.status]);

  const failedSections = Number(runState.generation.failed ?? 0);
  useEffect(() => {
    if (runState.stages.generation.status !== "done") return;
    if (!startedGeneration.current || navigatedToBacklog.current) return;
    if (failedSections > 0) return;
    navigatedToBacklog.current = true;
    setPinnedStep(null);
    setTab("backlog");
    toast({
      tone: "success",
      title: "Backlog generated",
      message: "Review the stories, then approve the backlog.",
    });
    void queryClient.invalidateQueries({ queryKey: ["project", id] });
    void queryClient.invalidateQueries({ queryKey: ["pipeline", id] });
    void queryClient.invalidateQueries({ queryKey: ["backlog", id] });
    void queryClient.invalidateQueries({ queryKey: ["coverage", id] });
    void queryClient.invalidateQueries({ queryKey: ["questions", id] });
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
  }, [runState.stages.generation.status, failedSections, id, queryClient, setTab, toast]);

  useEffect(() => {
    if (runState.stages.generation.status === "active" && runState.lastEventId > 0) {
      setPinnedStep(null);
    }
  }, [runState.lastEventId, runState.stages.generation.status]);

  const eventStep = useMemo(() => {
    if (
      runState.stages.generation.status !== "pending" ||
      Object.keys(runState.leaves).length > 0
    ) {
      return 3;
    }
    if (runState.stages.knowledge.status === "done") return 2;
    if (runState.stages.structure.status === "done") return 1;
    return 0;
  }, [runState.stages.generation.status, runState.stages.knowledge.status, runState.stages.structure.status, runState.leaves]);

  const statusStep = project ? statusStepIndex(project.status) : 0;
  const autoStep = Math.max(statusStep, eventStep);
  const activeStep = pinnedStep ?? autoStep;

  const openBacklog = useCallback(async () => {
    setPinnedStep(null);
    setTab("backlog");
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["backlog", id] }),
      queryClient.invalidateQueries({ queryKey: ["coverage", id] }),
      queryClient.invalidateQueries({ queryKey: ["questions", id] }),
    ]);
  }, [id, queryClient, setTab]);

  const handleStepSelect = (index: number) => {
    if (index >= 4) {
      void openBacklog();
      return;
    }
    setPinnedStep(index);
  };

  const handleOpenBacklog = () => {
    void openBacklog();
  };

  const refreshEverything = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ["project", id] });
    void queryClient.invalidateQueries({ queryKey: ["pipeline", id] });
    void queryClient.invalidateQueries({ queryKey: ["backlog", id] });
    void queryClient.invalidateQueries({ queryKey: ["coverage", id] });
    void queryClient.invalidateQueries({ queryKey: ["questions", id] });
    void queryClient.invalidateQueries({ queryKey: ["projects"] });
  }, [id, queryClient]);

  if (projectQuery.isLoading && !project) return <ProjectSkeleton />;

  if (projectQuery.isSuccess && !project) {
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

  if (projectQuery.isError) {
    return (
      <div className="page">
        <div className="container">
          <Card className="state-card" pad={false}>
            <strong>Could not load the project</strong>
            <p>{errorMessage(projectQuery.error)}</p>
          </Card>
        </div>
      </div>
    );
  }

  if (!project) return <ProjectSkeleton />;

  const status = projectStatusMeta(project.status);

  return (
    <div className="page project-page">
      <div className="container">
        <div className="breadcrumb">
          <Link to="/">Projects</Link>
          <span aria-hidden="true">/</span>
          <span>{project.name}</span>
        </div>

        <div className="project-head">
          <div className="project-head__main">
            <div className="eyebrow">
              <span className="eyebrow__dot" aria-hidden="true" />
              EY Cortex AI · Traceability workspace
            </div>
            <h1>{project.name}</h1>
            <div className="project-head__meta">
              <Chip tone={status.tone} dot>
                {status.label}
              </Chip>
              <span>{sections.length} sections</span>
              <span>{links.filter((link) => link.enabled).length} enabled links</span>
              {project.context_approved && <span>Context approved</span>}
            </div>
          </div>
          <button
            type="button"
            className="activity-button"
            onClick={() => setActivityOpen(true)}
            aria-haspopup="dialog"
          >
            <History size={14} />
            <span>Activity</span>
            <span className="activity-button__count">{runState.events.length}</span>
          </button>
        </div>

        {project.status === "failed" && project.error && (
          <div className="project-error">
            <strong>Pipeline failed</strong>
            <p>{project.error}</p>
          </div>
        )}

        {runState.demoMode && (
          <div className="demo-banner" role="status">
            <span className="demo-banner__dot" aria-hidden="true" />
            Demo mode: generated without the AI model
          </div>
        )}

        <div className="project-tabs">
          <div className="tab-bar" role="tablist" aria-label="Project sections">
            {TABS.map((entry) => {
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
                      layoutId="project-tab-pill"
                      className="tab__pill"
                      transition={reduced ? { duration: 0 } : softSpring}
                      aria-hidden="true"
                    />
                  )}
                  <span className="tab__label">
                    {entry.label}
                    {entry.beta && <span className="tab__beta">Beta</span>}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        <div className="tab-content">
          {tab === "pipeline" && (
            <PipelineTab
              project={project}
              document={documentQuery.data}
              sections={sections}
              links={links}
              activeStep={activeStep}
              onStepSelect={handleStepSelect}
              selectedSectionId={selectedSectionId}
              onSelectSection={(section) => setSelectedSectionId(section.id)}
              context={contextQuery.data}
              contextLoading={contextQuery.isLoading}
              onRoleChange={(section, role) => roleMutation.mutate({ section, role })}
              updatingRole={roleMutation.isPending ? roleMutation.variables?.section.id ?? null : null}
              onToggleLink={(link, enabled) => linkMutation.mutate({ linkId: link.id, enabled })}
              togglingLink={linkMutation.isPending ? linkMutation.variables?.linkId ?? null : null}
              onApproveAndGenerate={() => generateMutation.mutate()}
              approvingGenerating={generateMutation.isPending}
              runState={runState}
              retrying={retryMutation.isPending}
              onRetry={() => retryMutation.mutate()}
              onOpenBacklog={handleOpenBacklog}
              onSaveManualContext={(sectionId, title, text) =>
                saveManualContextMutation.mutate({ sectionId, title, text })
              }
              onDeleteManualContext={(section) => deleteManualContextMutation.mutate(section)}
              manualSaving={saveManualContextMutation.isPending}
              manualDeletingId={
                deleteManualContextMutation.isPending
                  ? deleteManualContextMutation.variables?.id ?? null
                  : null
              }
              onClearSelection={() => setSelectedSectionId(null)}
              onSaveExtraInstructions={(sectionId, text) =>
                saveInstructionsMutation.mutate({ sectionId, text })
              }
              savingInstructions={saveInstructionsMutation.isPending}
            />
          )}

          {tab === "backlog" && (
            <BacklogTab
              projectId={id}
              projectName={project.name}
              backlog={backlogQuery.data}
              coverage={coverageQuery.data}
              sections={sections}
              loading={backlogQuery.isLoading || backlogQuery.isFetching}
              error={backlogQuery.error}
              onRefresh={refreshEverything}
            />
          )}

          {tab === "questions" && (
            <QuestionsTab
              projectId={id}
              projectName={project.name}
              questions={questionsQuery.data ?? []}
              sections={sections}
              loading={questionsQuery.isLoading}
              onRefresh={refreshEverything}
            />
          )}

          {tab === "ask" && <AskTab projectId={id} sections={sections} />}
        </div>

        {pipelineQuery.data?.error && tab === "pipeline" && (
          <p className="muted-small" style={{ marginTop: 16 }}>
            {pipelineQuery.data.error}
          </p>
        )}
      </div>

      <ActivityDrawer
        open={activityOpen}
        events={runState.events}
        onClose={() => setActivityOpen(false)}
      />
    </div>
  );
}

