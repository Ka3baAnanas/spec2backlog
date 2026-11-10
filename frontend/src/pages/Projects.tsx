import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Project } from "../api/client";
import { Card } from "../components/Card";
import { Chip } from "../components/Chip";
import { Dropzone } from "../components/Dropzone";
import { ArrowRight, Folder, ListChecks, ShieldCheck, Sparkles, UploadCloud } from "../components/Icons";
import { ProjectCardSkeleton } from "../components/Skeleton";
import { useToast } from "../components/Toast";
import { errorMessage } from "../lib/errors";
import { staggerContainer, staggerItem } from "../lib/motion";
import { projectStatusMeta } from "../lib/status";

const STEPS = ["Document", "Structure", "Context", "Generation", "Backlog"];

function stepForStatus(status: string): number {
  switch (status) {
    case "uploaded":
    case "parsed":
      return 1;
    case "structured":
      return 2;
    case "linked":
    case "awaiting_context_approval":
      return 3;
    case "generating":
      return 4;
    case "generated":
    case "in_review":
    case "approved":
    case "exported":
      return 5;
    default:
      return 0;
  }
}

function ProjectCard({ project }: { project: Project }) {
  const reduced = useReducedMotion();
  const status = projectStatusMeta(project.status);
  const step = stepForStatus(project.status);
  const percent = step === 0 ? 0 : Math.round((step / STEPS.length) * 100);
  const found = project.checklist?.found?.length ?? 0;
  const total = found + (project.checklist?.missing?.length ?? 0);

  return (
    <motion.div variants={staggerItem}>
      <Link to={`/p/${project.id}`} className="card card--interactive project-card">
        <div className="project-card__top">
          <span className="project-card__mark" aria-hidden="true">
            <Folder size={17} />
          </span>
          <Chip tone={status.tone} dot>
            {status.label}
          </Chip>
        </div>

        <div className="project-card__title" title={project.name}>
          {project.name}
        </div>

        <div>
          <div className="mini-progress" aria-hidden="true">
            <motion.div
              className="mini-progress__fill"
              initial={{ width: 0 }}
              animate={{ width: `${percent}%` }}
              transition={{ duration: reduced ? 0 : 0.6, ease: [0.22, 1, 0.36, 1], delay: 0.08 }}
            />
          </div>
          <div className="project-card__steps">
            <span>{step === 0 ? "Needs attention" : `Step ${step} of 5 · ${STEPS[step - 1]}`}</span>
            <span>{total ? `${found}/${total} sections` : "Checklist pending"}</span>
          </div>
        </div>

        <div className="project-card__meta">
          <span>{project.context_approved ? "Context approved" : "Traceability workspace"}</span>
          <span className="project-card__link">
            Open <ArrowRight size={13} />
          </span>
        </div>
      </Link>
    </motion.div>
  );
}

export default function Projects() {
  const reduced = useReducedMotion();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const toast = useToast();
  const [projectName, setProjectName] = useState("");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["projects"],
    queryFn: api.projects,
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      const fallback = file.name.replace(/\.[^.]+$/, "");
      return api.upload(projectName.trim() || fallback, file);
    },
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast({
        tone: "success",
        title: "Specification prepared",
        message: "The document is parsed, structured and linked. Review the context next.",
      });
      setProjectName("");
      navigate(`/p/${project.id}`);
    },
    onError: (uploadError) => {
      toast({ tone: "error", title: "Upload failed", message: errorMessage(uploadError) });
    },
  });

  const projects = data ?? [];
  const stats = useMemo(() => {
    const inProgress = projects.filter((project) =>
      ["parsed", "structured", "linked", "awaiting_context_approval", "generating"].includes(project.status),
    ).length;
    const ready = projects.filter((project) => ["approved", "exported"].includes(project.status)).length;
    return { inProgress, ready };
  }, [projects]);

  const handleFile = (file: File) => {
    if (!/\.(docx|pdf)$/i.test(file.name)) {
      toast({
        tone: "error",
        title: "Unsupported file",
        message: "Please choose a Word (.docx) or PDF document.",
      });
      return;
    }
    upload.mutate(file);
  };

  return (
    <div className="page page--home">
      <section className="hero hero--compact">
        {!reduced && (
          <motion.div
            className="hero__sweep"
            aria-hidden="true"
            initial={{ x: "-70%" }}
            animate={{ x: "220%" }}
            transition={{ duration: 9, repeat: Infinity, repeatDelay: 4, ease: "easeInOut" }}
          />
        )}
        <div className="container hero-inner">
          <div className="hero__eyebrow">
            <span aria-hidden="true" />
            EY Cortex AI · Business analysis
          </div>
          <h1>
            From specification to <span className="accent">validated backlog</span>
          </h1>
          <p className="hero__lede">
            Upload a functional specification. We prepare the document, expose the structure and
            links, then wait for your context approval before generating a traceable backlog.
          </p>
          <div className="hero__meta">
            <span className="hero__meta-item">
              <Sparkles size={14} /> 5 calm steps
            </span>
            <span className="hero__meta-item">
              <ShieldCheck size={14} /> 2 human checkpoints
            </span>
            <span className="hero__meta-item">
              <ListChecks size={14} /> Every item traced to its source
            </span>
          </div>
        </div>
      </section>

      <div className="container">
        <div className="upload-wrap">
          <Card className="upload-card" pad={false}>
            <Dropzone
              onFile={handleFile}
              busy={upload.isPending}
              disabled={upload.isPending}
              busyLabel="Parsing, structuring and linking the specification…"
            />
            <div className="upload-card__side">
              <div>
                <div className="eyebrow" style={{ marginBottom: 8 }}>
                  <span className="eyebrow__dot" aria-hidden="true" />
                  New analysis
                </div>
                <h2>Drop a specification to begin</h2>
                <p style={{ marginTop: 8 }}>
                  Steps 1–3 run automatically. You approve the context before anything is generated.
                </p>
              </div>

              <div className="field">
                <label htmlFor="project-name">Project name (optional)</label>
                <input
                  id="project-name"
                  className="input"
                  value={projectName}
                  onChange={(event) => setProjectName(event.target.value)}
                  placeholder="e.g. Payments — SEPA transfer"
                  maxLength={120}
                  disabled={upload.isPending}
                />
              </div>

              <div className="upload-card__foot">
                <ShieldCheck size={14} />
                Offline demo when no provider key is configured
              </div>
            </div>
          </Card>
        </div>

        <section className="projects-section" id="projects">
          <div className="section-head">
            <div>
              <h2 className="section-title">Projects</h2>
              <p>
                {projects.length} specification{projects.length === 1 ? "" : "s"} ·{" "}
                {stats.inProgress} in progress · {stats.ready} ready
              </p>
            </div>
            <Chip tone="outline">{projects.length} total</Chip>
          </div>

          {isLoading ? (
            <div className="project-grid" aria-busy="true" aria-label="Loading projects">
              <ProjectCardSkeleton />
              <ProjectCardSkeleton />
              <ProjectCardSkeleton />
            </div>
          ) : isError ? (
            <div className="projects-empty">
              <strong>Could not load projects</strong>
              <span>{errorMessage(error)}</span>
            </div>
          ) : projects.length === 0 ? (
            <div className="projects-empty">
              <UploadCloud size={26} />
              <strong>No projects yet</strong>
              <span>Drop a specification above to create the first analysis.</span>
            </div>
          ) : (
            <motion.div
              className="project-grid"
              variants={staggerContainer}
              initial="hidden"
              animate="show"
            >
              {projects.map((project) => (
                <ProjectCard key={project.id} project={project} />
              ))}
            </motion.div>
          )}
        </section>
      </div>
    </div>
  );
}
