import { AnimatePresence, motion } from "framer-motion";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { CheckCircle, Sparkles, X, XCircle } from "./Icons";

export type ToastTone = "success" | "error" | "info";

type ToastInput = {
  title: string;
  message?: string;
  tone?: ToastTone;
  duration?: number;
};

type ToastItem = ToastInput & { id: string; tone: ToastTone };

type ToastFn = (toast: ToastInput) => void;

const ToastContext = createContext<ToastFn | null>(null);

let toastSeed = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const remove = useCallback((id: string) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const push = useCallback<ToastFn>(
    (input) => {
      const id = `${Date.now()}-${++toastSeed}`;
      const toast: ToastItem = { ...input, id, tone: input.tone ?? "info" };
      setToasts((current) => [...current.slice(-3), toast]);
      window.setTimeout(() => remove(id), input.duration ?? 4400);
    },
    [remove],
  );

  const value = useMemo(() => push, [push]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toast-viewport" role="region" aria-label="Notifications">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => (
            <motion.div
              key={toast.id}
              layout
              className={`toast toast--${toast.tone}`}
              initial={{ opacity: 0, x: 48, scale: 0.97 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 48, scale: 0.97 }}
              transition={{ duration: 0.26, ease: [0.22, 1, 0.36, 1] }}
              role="status"
              aria-live="polite"
            >
              <span className="toast__icon">
                {toast.tone === "success" ? (
                  <CheckCircle size={16} />
                ) : toast.tone === "error" ? (
                  <XCircle size={16} />
                ) : (
                  <Sparkles size={16} />
                )}
              </span>
              <div className="toast__content">
                <div className="toast__title">{toast.title}</div>
                {toast.message && <div className="toast__message">{toast.message}</div>}
              </div>
              <button
                type="button"
                className="toast__close"
                onClick={() => remove(toast.id)}
                aria-label="Dismiss notification"
              >
                <X size={14} />
              </button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastFn {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
