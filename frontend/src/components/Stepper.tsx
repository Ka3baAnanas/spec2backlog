import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { springPop } from "../lib/motion";
import { Check } from "./Icons";

export type Step = { label: string; sub?: string };

type StepperProps = {
  steps: Step[];
  doneCount: number;
  title?: string;
};

export function Stepper({ steps, doneCount, title = "Pipeline" }: StepperProps) {
  const reduced = useReducedMotion();
  const safeDone = Math.max(0, Math.min(doneCount, steps.length));
  const activeIndex = safeDone < steps.length ? safeDone : -1;
  const total = Math.max(1, steps.length - 1);
  const percent = steps.length <= 1 ? 0 : (Math.max(0, safeDone - 1) / total) * 100;

  return (
    <div className="card stepper-card">
      <div className="stepper__top">
        <h2>{title}</h2>
        <span className="stepper__progress-label">
          {safeDone} of {steps.length} stages complete
        </span>
      </div>

      <div className="stepper">
        <div className="stepper__track" aria-hidden="true">
          <motion.div
            className="stepper__fill"
            initial={false}
            animate={{ width: `${percent}%` }}
            transition={{ duration: reduced ? 0 : 0.45, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>

        <div className="stepper__track stepper__track--vertical" aria-hidden="true">
          <motion.div
            className="stepper__fill stepper__fill--vertical"
            initial={false}
            animate={{ height: `${percent}%` }}
            transition={{ duration: reduced ? 0 : 0.45, ease: [0.22, 1, 0.36, 1] }}
          />
        </div>

        <ol className="stepper__steps">
          {steps.map((step, index) => {
            const done = index < safeDone;
            const active = index === activeIndex;
            return (
              <li
                key={step.label}
                className={`step ${done ? "is-done" : ""} ${active ? "is-active" : ""}`.trim()}
                aria-current={active ? "step" : undefined}
              >
                <div className="step__marker">
                  <AnimatePresence mode="wait" initial={false}>
                    {done ? (
                      <motion.span
                        key="done"
                        initial={{ scale: 0, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0, opacity: 0 }}
                        transition={springPop}
                        style={{ display: "inline-flex" }}
                      >
                        <Check size={15} />
                      </motion.span>
                    ) : (
                      <motion.span
                        key="number"
                        initial={{ scale: 0.7, opacity: 0 }}
                        animate={{ scale: 1, opacity: 1 }}
                        exit={{ scale: 0.7, opacity: 0 }}
                        transition={{ duration: 0.2 }}
                      >
                        {index + 1}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  {active && !reduced && <span className="step__pulse" aria-hidden="true" />}
                </div>
                <div className="step__label">
                  {step.label}
                  {step.sub && <span className="step__sub">{step.sub}</span>}
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
