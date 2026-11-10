import { animate, motion, useReducedMotion } from "framer-motion";
import { useEffect, useState, type ReactNode } from "react";
import { easePremium, staggerItem } from "../lib/motion";

type StatTileProps = {
  label: string;
  value: number;
  suffix?: string;
  hint?: string;
  icon?: ReactNode;
};

export function StatTile({ label, value, suffix, hint, icon }: StatTileProps) {
  const reduced = useReducedMotion();
  const [display, setDisplay] = useState(reduced ? value : 0);

  useEffect(() => {
    if (reduced) {
      setDisplay(value);
      return;
    }
    const controls = animate(0, value, {
      duration: 0.85,
      ease: easePremium,
      onUpdate: (latest) => setDisplay(Math.round(latest)),
    });
    return () => controls.stop();
  }, [value, reduced]);

  return (
    <motion.div className="card stat" variants={staggerItem}>
      <div className="stat__label">
        {icon}
        {label}
      </div>
      <div className="stat__value">
        {display}
        {suffix && <small>{suffix}</small>}
      </div>
      {hint && <div className="stat__hint">{hint}</div>}
    </motion.div>
  );
}
