import { motion, useReducedMotion } from "framer-motion";
import { Check } from "../Icons";

export type WizardStep = { key: string; label: string; hint?: string };

export function Wizard({
  steps,
  activeIndex,
  onSelect,
}: {
  steps: WizardStep[];
  activeIndex: number;
  onSelect: (index: number) => void;
}) {
  const reduced = useReducedMotion();

  return (
    <nav className="wizard" aria-label="Pipeline steps">
      <ol className="wizard__list">
        {steps.map((step, index) => {
          const done = index < activeIndex;
          const active = index === activeIndex;
          return (
            <li key={step.key} className="wizard__item">
              <button
                type="button"
                className={[
                  "wizard__step",
                  done ? "is-done" : "",
                  active ? "is-active" : "",
                  "is-clickable",
                ]
                  .filter(Boolean)
                  .join(" ")}
                aria-current={active ? "step" : undefined}
                aria-label={`Step ${index + 1}: ${step.label}`}
                onClick={() => onSelect(index)}
              >
                {active && (
                  <motion.span
                    layoutId="wizard-active"
                    className="wizard__active-bg"
                    transition={reduced ? { duration: 0 } : { type: "spring", stiffness: 420, damping: 38 }}
                    aria-hidden="true"
                  />
                )}
                <span className="wizard__marker" aria-hidden="true">
                  {done ? <Check size={13} /> : index + 1}
                </span>
                <span className="wizard__text">
                  <span className="wizard__label">{step.label}</span>
                  {step.hint && <span className="wizard__hint">{step.hint}</span>}
                </span>
                
              </button>
              {index < steps.length - 1 && <span className="wizard__connector" aria-hidden="true" />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
