import { motion, useReducedMotion } from "framer-motion";
import type { ReactNode } from "react";
import { easePremium } from "../lib/motion";

export function PageTransition({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      initial={{ opacity: 0, y: reduced ? 0 : 12 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: reduced ? 0 : -8 }}
      transition={{ duration: reduced ? 0 : 0.25, ease: easePremium }}
    >
      {children}
    </motion.div>
  );
}
