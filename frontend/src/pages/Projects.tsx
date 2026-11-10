import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, type Project } from "../api/client";
import { Card } from "../components/Card";
import { Chip } from "../components/Chip";
import { Dropzone } from "../components/Dropzone";
import {
  ArrowRight,
  Clock,
  Folder,
  ListChecks,
  ShieldCheck,
  Sparkles,
  Target,
  UploadCloud,
} from "../components/Icons";
import { ProjectCardSkeleton } from "../components/Skeleton";
import { StatTile } from "../components/StatTile";
import { useToast } from "../components/Toast";
import { errorMessage } from "../lib/errors";
import { staggerContainer, staggerItem } from "../lib/motion";
import { projectStatusMeta } from "../lib/status";

function ProjectCard({ project }: { project: Project }) {
  const reduced = useReducedMotion();
  const found = project.checklist?.found?.length ?? 0;
  const missing = project.checklist?.missing?.length ?? 0;
  const total = found + missing;
  const percent = total ? Math.round((found / total) * 100) : 0;
  const status = projectStatusMeta(project.status);

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
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 10,
              marginTop: 7,
              fontSize: 11.5,
              color: "var(--muted)",
            }}
          >
            <span>{total ? `${found} of ${total} expected sections found` : "Checklist pending"}</span>
            <span>{total ? `${percent}%` : "—"}</span>
          </div>
        </div>

        <div className="project-card__meta">
          <span>Workspace & traceability</span>
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
        title: "Specification ingested",
        message: `“${project.name}” is ready. The document tree has been built.`,
      });
      setProjectName("");
      navigate(`/p/${project.id}`);
    },
    onError: (uploadError) => {
      toast({
        tone: "error",
        title: "Upload failed",
        message: errorMessage(uploadError),
      });
    },
  });

  const projects = data ?? [];

  const stats = useMemo(() => {
    const inProgress = projects.filter((project) =>
      ["ingested", "graph_built", "generated"].includes(project.status),
    ).length;
    const ready = projects.filter((project) =>
      ["validated", "exported"].includes(project.status),
    ).length;
    let found = 0;
    let total = 0;
    for (const project of projects) {
      found += project.checklist?.found?.length ?? 0;
      total += (project.checklist?.found?.length ?? 0) + (project.checklist?.missing?.length ?? 0);
    }
    return {
      inProgress,
      ready,
      coverage: total ? Math.round((found / total) * 100) : 0,
    };
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
      <section className="hero">
        <div className="hero__beam" aria-hidden="true">
          <img src="/ey-beam.svg" alt="" />
        </div>
        {!reduced && (
          <motion.div
            className="hero__sweep"
            aria-hidden="true"
            initial={{ x: "-70%" }}
            animate={{ x: "220%" }}
            transition={{ duration: 7.5, repeat: Infinity, repeatDelay: 2.4, ease: "easeInOut" }}
          />
        )}

        <div className="container hero-inner">
          <motion.div
            initial={{ opacity: 0, y: reduced ? 0 : 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="hero__eyebrow">
              <span aria-hidden="true" />
              EY Cortex AI · Business analysis
            </div>
            <h1>
              From specification to <span className="accent">backlog</span>, in minutes
            </h1>
            <p className="hero__lede">
              Upload a functional specification. We extract its structure, connect related
              sections, and generate a traceable epic, story and test backlog for your
              business analysts to validate.
            </p>
            <div className="hero__meta">
              <span className="hero__meta-item">
                <Sparkles size={14} /> Structure extracted automatically
              </span>
              <span className="hero__meta-item">
                <Target size={14} /> Every item traced to its source
              </span>
              <span className="hero__meta-item">
                <ShieldCheck size={14} /> Human validation built in
              </span>
            </div>
          </motion.div>
        </div>
      </section>

      <div className="container">
        <div className="upload-wrap">
          <Card className="upload-card" pad={false}>
            <Dropzone
              onFile={handleFile}
              busy={upload.isPending}
              disabled={upload.isPending}
              busyLabel="Reading document, extracting headings and tables…"
            />

            <div className="upload-card__side">
              <div>
                <div className="eyebrow" style={{ marginBottom: 8 }}>
                  <span className="eyebrow__dot" aria-hidden="true" />
                  New analysis
                </div>
                <h2>Turn a document into a validated backlog</h2>
                <p style={{ marginTop: 8 }}>
                  Add an optional project name, then drop the specification. The pipeline runs
                  in your environment.
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

              <div className="chip-wrap" style={{ marginTop: 0 }}>
                <Chip tone="outline">DOCX</Chip>
                <Chip tone="outline">PDF</Chip>
                <Chip tone="outline">≤ 25 MB</Chip>
              </div>

              <div className="upload-card__foot">
                <ShieldCheck size={14} />
                Private by design · no data leaves your tenant
              </div>
            </div>
          </Card>
        </div>

        <motion.div
          className="stat-grid"
          variants={staggerContainer}
          initial="hidden"
          animate="show"
        >
          <StatTile
            label="Projects"
            value={projects.length}
            hint="Specifications analysed"
            icon={<Folder size={13} />}
          />
          <StatTile
            label="In progress"
            value={stats.inProgress}
            hint="Graph or generation running"
            icon={<Clock size={13} />}
          />
          <StatTile
            label="Ready to export"
            value={stats.ready}
            hint="Validated backlogs"
            icon={<Target size={13} />}
          />
          <StatTile
            label="Checklist coverage"
            value={stats.coverage}
            suffix="%"
            hint="Expected sections found"
            icon={<ListChecks size={13} />}
          />
        </motion.div>

        <section className="projects-section" id="projects">
          <div className="section-head">
            <div>
              <h2 className="section-title">Recent projects</h2>
              <p>Pick up where your analysis team left off.</p>
            </div>
            <Chip tone="default">{projects.length} total</Chip>
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
              <span>Drop a specification above to create your first analysis.</span>
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

        <section id="workflow" style={{ marginTop: 44 }}>
          <div className="section-head">
            <div>
              <h2 className="section-title">How the pipeline works</h2>
              <p>A transparent, auditable path from document to delivery.</p>
            </div>
          </div>
          <div className="workflow">
            {[
              {
                index: "01",
                title: "Ingest",
                text: "Headings, tables and text are extracted with a completeness checklist.",
              },
              {
                index: "02",
                title: "Connect",
                text: "A meaning graph links related sections and explicit references.",
              },
              {
                index: "03",
                title: "Generate",
                text: "Epics, stories, acceptance criteria and tests are drafted per section.",
              },
              {
                index: "04",
                title: "Validate",
                text: "Business analysts approve, edit or reject, then export to Excel.",
              },
            ].map((step) => (
              <div className="workflow__step" key={step.index}>
                <div className="workflow__index">{step.index}</div>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
