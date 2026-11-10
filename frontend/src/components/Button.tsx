import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ComponentPropsWithoutRef, ReactNode } from "react";
import { Check } from "./Icons";

type NativeButtonProps = Omit<
  ComponentPropsWithoutRef<"button">,
  "onAnimationStart" | "onAnimationEnd" | "onDrag" | "onDragStart" | "onDragEnd"
>;

export type ButtonProps = NativeButtonProps & {
  variant?: "primary" | "accent" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  success?: boolean;
  icon?: ReactNode;
  block?: boolean;
};

export function Button({
  variant = "secondary",
  size = "md",
  loading = false,
  success = false,
  icon,
  block = false,
  className = "",
  children,
  disabled,
  ...rest
}: ButtonProps) {
  const reduced = useReducedMotion();
  const isDisabled = Boolean(disabled) || loading;

  return (
    <motion.button
      {...rest}
      type={rest.type ?? "button"}
      className={[
        "btn",
        `btn--${variant}`,
        size === "sm" ? "btn--sm" : size === "lg" ? "btn--lg" : "",
        block ? "btn--block" : "",
        success ? "btn--success" : "",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
      disabled={isDisabled}
      whileHover={!reduced && !isDisabled ? { y: -1 } : undefined}
      whileTap={!reduced && !isDisabled ? { scale: 0.98 } : undefined}
      transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
      aria-busy={loading || undefined}
    >
      <AnimatePresence mode="wait" initial={false}>
        {loading ? (
          <motion.span
            key="spinner"
            className="btn__spinner"
            initial={{ opacity: 0, scale: 0.7 }}
            animate={{ opacity: 1, scale: 1, rotate: 360 }}
            exit={{ opacity: 0, scale: 0.7 }}
            transition={{
              rotate: { repeat: Infinity, duration: 0.75, ease: "linear" },
              opacity: { duration: 0.15 },
              scale: { duration: 0.15 },
            }}
            aria-hidden="true"
          />
        ) : success ? (
          <motion.span
            key="success"
            className="btn__icon"
            initial={{ opacity: 0, scale: 0.4 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.4 }}
            transition={{ type: "spring", stiffness: 520, damping: 28 }}
            aria-hidden="true"
          >
            <Check size={15} />
          </motion.span>
        ) : icon ? (
          <motion.span
            key="icon"
            className="btn__icon"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            aria-hidden="true"
          >
            {icon}
          </motion.span>
        ) : null}
      </AnimatePresence>
      {children != null && <span>{children}</span>}
    </motion.button>
  );
}
