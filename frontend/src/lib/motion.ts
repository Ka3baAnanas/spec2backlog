import type { Transition, Variants } from "framer-motion";

export const easePremium: [number, number, number, number] = [0.22, 1, 0.36, 1];

export const pageTransition: Transition = { duration: 0.25, ease: easePremium };

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: pageTransition },
  exit: { opacity: 0, y: -8, transition: { duration: 0.18, ease: easePremium } },
};

export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.04, delayChildren: 0.02 } },
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.28, ease: easePremium } },
};

export const springPop: Transition = { type: "spring", stiffness: 520, damping: 30 };

export const softSpring: Transition = { type: "spring", stiffness: 380, damping: 38 };
