import { motion, useReducedMotion, type HTMLMotionProps } from "framer-motion";

type CardProps = HTMLMotionProps<"div"> & {
  pad?: boolean;
  interactive?: boolean;
  flat?: boolean;
};

export function Card({ pad = false, interactive = false, flat = false, className = "", children, ...rest }: CardProps) {
  const reduced = useReducedMotion();
  return (
    <motion.div
      {...rest}
      className={["card", pad ? "card--pad" : "", interactive ? "card--interactive" : "", flat ? "card--flat" : "", className]
        .filter(Boolean)
        .join(" ")}
      whileHover={interactive && !reduced ? { y: -2 } : undefined}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </motion.div>
  );
}
