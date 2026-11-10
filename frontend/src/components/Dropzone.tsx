import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useRef, useState, type DragEvent, type KeyboardEvent } from "react";
import { UploadCloud } from "./Icons";

type DropzoneProps = {
  onFile: (file: File) => void;
  accept?: string;
  busy?: boolean;
  disabled?: boolean;
  busyLabel?: string;
  title?: string;
  hint?: string;
};

export function Dropzone({
  onFile,
  accept = ".docx,.pdf",
  busy = false,
  disabled = false,
  busyLabel = "Reading document…",
  title = "Drop your specification here",
  hint = "Word (.docx) or PDF · up to 25 MB",
}: DropzoneProps) {
  const reduced = useReducedMotion();
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const locked = busy || disabled;

  const openPicker = () => {
    if (!locked) inputRef.current?.click();
  };

  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onFile(file);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (locked) return;
    handleFiles(event.dataTransfer.files);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openPicker();
    }
  };

  return (
    <div
      className={[
        "dropzone",
        dragging ? "is-dragging" : "",
        locked ? "is-busy" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      role="button"
      tabIndex={locked ? -1 : 0}
      aria-label={title}
      aria-disabled={locked || undefined}
      onClick={openPicker}
      onKeyDown={onKeyDown}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!locked) setDragging(true);
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!locked) setDragging(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();
        if (event.currentTarget.contains(event.relatedTarget as Node | null)) return;
        setDragging(false);
      }}
      onDrop={onDrop}
    >
      <motion.div
        className="dropzone__icon"
        animate={
          dragging && !reduced
            ? { y: [0, -6, 0], scale: [1, 1.06, 1] }
            : { y: 0, scale: 1 }
        }
        transition={
          dragging && !reduced
            ? { duration: 0.7, repeat: Infinity, ease: "easeInOut" }
            : { duration: 0.2 }
        }
        aria-hidden="true"
      >
        <UploadCloud size={24} />
      </motion.div>

      <div>
        <div className="dropzone__title">
          {dragging ? "Release to upload" : title}
        </div>
        <div className="dropzone__hint">
          {busy ? busyLabel : (
            <>
              or <span className="dropzone__browse">browse files</span> · {hint}
            </>
          )}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {busy && (
          <motion.div
            key="shimmer"
            className="dropzone__shimmer"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            style={{ position: "absolute", left: 0, right: 0, bottom: 0 }}
          />
        )}
      </AnimatePresence>

      <input
        ref={inputRef}
        type="file"
        accept={accept}
        onChange={(event) => {
          handleFiles(event.target.files);
          event.target.value = "";
        }}
      />
    </div>
  );
}
