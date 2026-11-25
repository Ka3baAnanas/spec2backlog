import { useMemo, useState } from "react";
import type { Checklist, DocumentBlock, ProjectDocument } from "../../api/client";
import { Card } from "../Card";
import { Chip } from "../Chip";
import { AlertTriangle, CheckCircle, ListChecks } from "../Icons";

type Filter = "heading" | "paragraph" | "table" | "skipped";

const COUNTERS: { key: Filter; label: string }[] = [
  { key: "heading", label: "Headings" },
  { key: "paragraph", label: "Paragraphs" },
  { key: "table", label: "Tables" },
  { key: "skipped", label: "Skipped" },
];

function truncate(text: string, max = 90): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max - 1)}...` : flat;
}

function headingParts(text: string): { number: string; title: string } {
  const match = /^(\d+(?:\.\d+)*)[.)]?\s+(.*)$/.exec(text.trim());
  if (!match) return { number: "", title: text.trim() };
  return { number: match[1], title: match[2] };
}

function TableBlock({ text }: { text: string }) {
  const rows = text
    .split(/\r?\n/)
    .map((line) => line.split(" | "))
    .filter((row) => row.some((cell) => cell.trim()));
  if (!rows.length) return <p className="doc-view__paragraph">Empty table</p>;
  const [header, ...body] = rows;
  return (
    <div className="doc-view__table-wrap">
      <table className="doc-view__table">
        <thead>
          <tr>
            {header.map((cell, index) => (
              <th key={`h-${index}`}>{cell || " "}</th>
            ))}
          </tr>
        </thead>
        {body.length > 0 && (
          <tbody>
            {body.map((row, rowIndex) => (
              <tr key={`r-${rowIndex}`}>
                {header.map((_, cellIndex) => (
                  <td key={`c-${cellIndex}`}>{row[cellIndex] ?? ""}</td>
                ))}
              </tr>
            ))}
          </tbody>
        )}
      </table>
    </div>
  );
}

function Block({
  block,
  index,
  active,
}: {
  block: DocumentBlock;
  index: number;
  active: boolean;
}) {
  const id = `doc-block-${index}`;
  const className = `doc-view__block doc-view__block--${block.kind} ${active ? "is-active" : ""}`.trim();

  if (block.kind === "heading") {
    const { number, title } = headingParts(block.text);
    return (
      <div
        id={id}
        className={className}
        style={{ marginLeft: Math.max(0, Math.min(block.level, 4) - 1) * 12 }}
      >
        {number && <span className="doc-view__heading-num">{number}</span>}
        <strong>{title || "Untitled heading"}</strong>
      </div>
    );
  }

  if (block.kind === "table") {
    return (
      <div id={id} className={className}>
        <TableBlock text={block.text} />
      </div>
    );
  }

  if (block.kind === "list") {
    return (
      <p id={id} className={className}>
        {block.text.replace(/^[-*]\s*/, "")}
      </p>
    );
  }

  return (
    <p id={id} className={className}>
      {block.text || "Empty paragraph"}
    </p>
  );
}

function checkLines(doc: ProjectDocument | undefined, checklist: Checklist) {
  const lines: { tone: "ok" | "info" | "warn"; text: string }[] = [];
  if (!doc) {
    return [{ tone: "info" as const, text: "Waiting for the parsed document" }];
  }
  const found = checklist?.found ?? [];
  const missing = checklist?.missing ?? [];
  const total = found.length + missing.length;

  if (total > 0) {
    if (missing.length === 0) {
      lines.push({ tone: "ok", text: `All ${total} expected chapters found` });
    } else {
      lines.push({
        tone: "warn",
        text: `${missing.length} expected chapter${missing.length === 1 ? "" : "s"} missing: ${missing.join(", ")}`,
      });
    }
  }

  const skipped = doc?.stats.skipped_toc ?? doc?.skipped?.length ?? 0;
  if (skipped > 0) {
    lines.push({
      tone: "info",
      text: `Table of contents detected and skipped (${skipped} line${skipped === 1 ? "" : "s"})`,
    });
  }

  for (const warning of doc?.warnings ?? []) {
    if (/table[- ]of[- ]contents/i.test(warning)) continue;
    const severe = /no (heading|body text)|no text layer|ocr/i.test(warning);
    lines.push({ tone: severe ? "warn" : "info", text: warning });
  }

  if (!lines.length) {
    lines.push({ tone: "ok", text: "No document issues detected" });
  }
  return lines;
}

function DocumentCheck({ doc, checklist }: { doc?: ProjectDocument; checklist: Checklist }) {
  const lines = checkLines(doc, checklist);
  const hasWarning = lines.some((line) => line.tone === "warn");

  return (
    <Card className={`document-check ${hasWarning ? "has-warning" : ""}`.trim()} pad>
      <div className="document-check__head">
        <div>
          <h3>Document check</h3>
          <p>Plain-language signals from the parser.</p>
        </div>
        <Chip tone={hasWarning ? "amber" : "green"} dot>
          {hasWarning ? "Review" : "OK"}
        </Chip>
      </div>
      <ul className="document-check__list">
        {lines.map((line) => (
          <li key={line.text} className={`is-${line.tone}`}>
            {line.tone === "warn" ? (
              <AlertTriangle size={13} />
            ) : line.tone === "ok" ? (
              <CheckCircle size={13} />
            ) : (
              <ListChecks size={13} />
            )}
            <span>{line.text}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function DocumentView({
  doc,
  checklist,
}: {
  doc?: ProjectDocument;
  checklist: Checklist;
}) {
  const [filter, setFilter] = useState<Filter | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  const blocks = useMemo<DocumentBlock[]>(() => {
    if (doc?.blocks?.length) return doc.blocks;
    return doc?.stats.preview ?? [];
  }, [doc]);

  const skipped = doc?.skipped ?? [];
  const counts: Record<Filter, number> = {
    heading: doc?.stats.headings ?? blocks.filter((block) => block.kind === "heading").length,
    paragraph:
      doc?.stats.paragraphs ?? blocks.filter((block) => block.kind === "paragraph").length,
    table: doc?.stats.tables ?? blocks.filter((block) => block.kind === "table").length,
    skipped: doc?.stats.skipped_toc ?? skipped.length,
  };

  const visible = useMemo(
    () =>
      blocks
        .map((block, index) => ({ block, index }))
        .filter(({ block }) => filter === null || block.kind === filter),
    [blocks, filter],
  );

  const listed = useMemo(() => {
    if (filter === "skipped") {
      return skipped.map((text, index) => ({
        id: `doc-skipped-${index}`,
        label: truncate(text),
      }));
    }
    return visible.map(({ block, index }) => ({
      id: `doc-block-${index}`,
      label:
        block.kind === "table"
          ? `Table: ${truncate(block.text.split("\n")[0] ?? "")}`
          : truncate(block.text),
    }));
  }, [filter, skipped, visible]);

  const scrollTo = (id: string) => {
    const element = window.document.getElementById(id);
    if (!element) return;
    element.scrollIntoView({ behavior: "smooth", block: "center" });
    window.setTimeout(() => {
      setActiveId(id);
      window.setTimeout(() => setActiveId((current) => (current === id ? null : current)), 1500);
    }, 120);
  };

  const selectFilter = (next: Filter) => {
    setFilter((current) => (current === next ? null : next));
    setActiveId(null);
  };

  return (
    <div className="document-layout">
      <Card className="doc-view-card" pad={false}>
        <div className="doc-view__head">
          <div>
            <h3>Document view</h3>
            <p>
              {doc?.filename ?? "Uploaded document"} · {blocks.length} blocks in reading order
            </p>
          </div>
          {filter && (
            <button type="button" className="mini-action" onClick={() => setFilter(null)}>
              Clear filter
            </button>
          )}
        </div>
        <div className="doc-view__scroll">
          {!doc ? (
            <p className="muted-small">Loading the parsed document...</p>
          ) : filter === "skipped" ? (
            skipped.length ? (
              skipped.map((text, index) => {
                const id = `doc-skipped-${index}`;
                return (
                  <p
                    id={id}
                    key={id}
                    className={`doc-view__block doc-view__block--skipped ${activeId === id ? "is-active" : ""}`.trim()}
                  >
                    {text}
                  </p>
                );
              })
            ) : (
              <p className="muted-small">No table-of-contents lines were skipped.</p>
            )
          ) : visible.length ? (
            visible.map(({ block, index }) => (
              <Block
                key={`${index}-${block.kind}`}
                block={block}
                index={index}
                active={activeId === `doc-block-${index}`}
              />
            ))
          ) : (
            <p className="muted-small">No blocks match this filter.</p>
          )}
        </div>
      </Card>

      <div className="doc-side">
        <div className="doc-counters" role="group" aria-label="Document block filters">
          {COUNTERS.map((counter) => {
            const active = filter === counter.key;
            return (
              <button
                key={counter.key}
                type="button"
                className={`doc-counter ${active ? "is-active" : ""}`.trim()}
                aria-pressed={active}
                onClick={() => selectFilter(counter.key)}
              >
                <span>{counter.label}</span>
                <strong>{counts[counter.key]}</strong>
              </button>
            );
          })}
        </div>

        {filter && (
          <Card className="doc-filter-list" pad={false}>
            <div className="doc-filter-list__head">
              <h3>{COUNTERS.find((counter) => counter.key === filter)?.label}</h3>
              <span>{listed.length}</span>
            </div>
            <div className="doc-filter-list__body">
              {listed.length ? (
                listed.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="doc-filter-item"
                    onClick={() => scrollTo(item.id)}
                  >
                    {item.label || "Untitled block"}
                  </button>
                ))
              ) : (
                <p className="muted-small">Nothing to list for this filter.</p>
              )}
            </div>
          </Card>
        )}

        <DocumentCheck doc={doc} checklist={checklist} />
      </div>
    </div>
  );
}
