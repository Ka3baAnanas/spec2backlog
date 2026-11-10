import { AnimatePresence, MotionConfig } from "framer-motion";
import { useEffect } from "react";
import { Route, Routes, useLocation } from "react-router-dom";
import { Header } from "./components/Header";
import { PageTransition } from "./components/PageTransition";
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

function AnimatedRoutes() {
  const location = useLocation();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <PageTransition key={location.pathname}>
        <Routes location={location}>
          <Route path="/" element={<Projects />} />
          <Route path="/p/:id" element={<Project />} />
        </Routes>
      </PageTransition>
    </AnimatePresence>
  );
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
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
    </MotionConfig>
  );
}
