import type { ReactNode } from "react";

export type ChipTone = "default" | "yellow" | "green" | "amber" | "red" | "blue" | "dark" | "outline";

type ChipProps = {
  tone?: ChipTone;
  dot?: boolean;
  className?: string;
  children: ReactNode;
  title?: string;
};

export function Chip({ tone = "default", dot = false, className = "", children, title }: ChipProps) {
  return (
    <span className={`chip chip--${tone} ${className}`.trim()} title={title}>
      {dot && <span className="chip__dot" />}
      {children}
    </span>
  );
}
