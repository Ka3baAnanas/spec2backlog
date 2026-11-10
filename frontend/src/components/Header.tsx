import { motion, useReducedMotion } from "framer-motion";
import { Link, useLocation } from "react-router-dom";

type NavItem = { label: string; to: string; active: boolean };

export function Header() {
  const location = useLocation();
  const reduced = useReducedMotion();
  const segments = location.pathname.split("/").filter(Boolean);
  const projectId = segments[0] === "p" ? segments[1] : undefined;
  const isReview = Boolean(projectId && segments[2] === "review");
  const isLive = Boolean(projectId && segments[2] === "live");

  const navItems: NavItem[] = [{ label: "Projects", to: "/", active: !projectId }];
  if (projectId) {
    navItems.push({
      label: "Workspace",
      to: `/p/${projectId}`,
      active: !isReview && !isLive,
    });
    navItems.push({
      label: "Live",
      to: `/p/${projectId}/live`,
      active: isLive,
    });
    navItems.push({
      label: "Review",
      to: `/p/${projectId}/review`,
      active: isReview,
    });
  }

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
          {navItems.map((item) => (
            <Link
              key={item.label}
              to={item.to}
              className={`nav-link ${item.active ? "is-active" : ""}`.trim()}
              aria-current={item.active ? "page" : undefined}
            >
              {item.label}
              {item.active && (
                <motion.span
                  layoutId="nav-underline"
                  className="nav-link__underline"
                  transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 36 }}
                />
              )}
            </Link>
          ))}
        </nav>

        <div className="header-right">
          <span className="header-badge">
            <span className="header-badge__dot" aria-hidden="true" />
            EY Cortex AI
          </span>
        </div>
      </div>
    </header>
  );
}
