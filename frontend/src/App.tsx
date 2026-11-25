import { AnimatePresence, MotionConfig } from "framer-motion";
import { useEffect, useState } from "react";
import { Link, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Header } from "./components/Header";
import { PageTransition } from "./components/PageTransition";
import { RunStreamProvider } from "./hooks/useRunStream";
import { ToastProvider } from "./components/Toast";
import Project from "./pages/Project";
import Projects from "./pages/Projects";

function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }, [pathname]);
  return null;
}

function NotFound() {
  const { pathname } = useLocation();
  return (
    <div className="container" style={{ padding: "64px 0", textAlign: "center" }}>
      <h1>Page introuvable</h1>
      <p>
        Aucune page ne correspond à <code>{pathname}</code>.
      </p>
      <Link to="/">Retour aux projets</Link>
    </div>
  );
}

function useTrackedProjectId() {
  const { pathname } = useLocation();
  const match = pathname.match(/^\/p\/([^/]+)/);
  const routeId = match ? decodeURIComponent(match[1]) : undefined;
  const [tracked, setTracked] = useState<string | undefined>(routeId);

  useEffect(() => {
    if (routeId) setTracked(routeId);
  }, [routeId]);

  return tracked;
}

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <PageTransition key={location.pathname}>
        <Routes location={location}>
          <Route path="/" element={<Projects />} />
          <Route path="/p/:id" element={<Project />} />
          <Route path="/admin/*" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </PageTransition>
    </AnimatePresence>
  );
}

export default function App() {
  const projectId = useTrackedProjectId();
  return (
    <MotionConfig reducedMotion="user">
      <RunStreamProvider projectId={projectId}>
        <ToastProvider>
          <ScrollToTop />
          <Header />
          <main className="app-main">
            <AnimatedRoutes />
          </main>
          <footer className="site-footer">
            <div className="container site-footer__inner">
              <div className="site-footer__left">
                <span className="site-footer__beam" aria-hidden="true" />
                <span>Spec2Backlog · EY Cortex AI</span>
              </div>
              <span>Prototype · Human-in-the-loop business analysis · Data stays in your environment</span>
            </div>
          </footer>
        </ToastProvider>
      </RunStreamProvider>
    </MotionConfig>
  );
}
