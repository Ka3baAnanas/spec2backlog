import { motion, useReducedMotion } from "framer-motion";
import { Link, useLocation } from "react-router-dom";
import { useRunStreamContext } from "../hooks/useRunStream";
import { selectGenerationStats } from "../lib/runState";

export function Header() {
  const location = useLocation();
  const reduced = useReducedMotion();
  const segments = location.pathname.split("/").filter(Boolean);
  const projectId = segments[0] === "p" ? segments[1] : undefined;
  const stream = useRunStreamContext();
  const stats = selectGenerationStats(stream.state, 0);
  const generating =
    stream.state.stages.generation.status === "active" && Boolean(stream.projectId);

  return (
    <header className="site-header">
      <div className="container header-inner">
        <Link to="/" className="brand" aria-label="Spec2Backlog home">
          <img className="brand__logo" src="/ey-logo-dark.svg" alt="EY" />
          <span className="brand__divider" aria-hidden="true" />
          <span className="brand__name">
            Spec2Backlog <span>/ Cortex AI</span>
          </span>
        </Link>

        <nav className="main-nav" aria-label="Primary">
          <Link
            to="/"
            className={`nav-link ${!projectId ? "is-active" : ""}`.trim()}
            aria-current={!projectId ? "page" : undefined}
          >
            Projects
            {!projectId && (
              <motion.span
                layoutId="nav-underline"
                className="nav-link__underline"
                transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }}
              />
            )}
          </Link>
          {projectId && (
            <Link
              to={`/p/${projectId}`}
              className="nav-link is-active"
              aria-current="page"
            >
              Project
              <motion.span
                layoutId="nav-underline"
                className="nav-link__underline"
                transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }}
              />
            </Link>
          )}
        </nav>

        <div className="header-right">
          {generating && (
            <Link
              to={`/p/${stream.projectId}`}
              className="header-run-badge"
              aria-label="Open live generation progress"
            >
              <span className="header-run-badge__dot" aria-hidden="true" />
              Generating {stats.completed}/{stats.total || "…"}
            </Link>
          )}
          <span className="header-badge">
            <span className="header-badge__dot" aria-hidden="true" />
            EY Cortex AI
          </span>
        </div>
      </div>
    </header>
  );
}
