import { useEffect, useMemo, useState } from "react";
import type {
  ContextPack,
  ProjectDocument,
  ProjectLink,
  Project,
  Section,
  SectionRole,
} from "../../api/client";
import { roleMeta } from "../../lib/status";
import type { RunState } from "../../lib/runState";
import { Button } from "../Button";
import { Card } from "../Card";
import { Chip } from "../Chip";
import { AlertTriangle, CheckCircle, Copy, Link2, ListChecks } from "../Icons";
import { StatTile } from "../StatTile";
import { ContextGraph } from "./ContextGraph";
import { GenerationView } from "./GenerationView";
import { StructureTree } from "./StructureTree";
import { Wizard, type WizardStep } from "./Wizard";

const STEPS: WizardStep[] = [
  { key: "document", label: "Document", hint: "Parse" },
  { key: "structure", label: "Structure", hint: "Roles" },
  { key: "context", label: "Context", hint: "Approve" },
  { key: "generation", label: "Generation", hint: "Draft" },
  { key: "backlog", label: "Backlog", hint: "Review" },
];

const ROLE_ORDER: SectionRole[] = ["requirement", "context", "glossary", "ignored", "front_matter"];

export function PipelineTab({
  project,
  document,
  sections,
  links,
  activeStep,
  maxStep,
  onStepSelect,
  selectedSectionId,
  onSelectSection,
  context,
  contextLoading,
  onRoleChange,
  updatingRole,
  onToggleLink,
  togglingLink,
  onApproveAndGenerate,
  approvingGenerating,
  runState,
  retrying,
  onRetry,
  onOpenBacklog,
}: {
  project: Project;
  document?: ProjectDocument;
  sections: Section[];
  links: ProjectLink[];
  activeStep: number;
  maxStep: number;
  onStepSelect: (index: number) => void;
  selectedSectionId: string | null;
  onSelectSection: (section: Section) => void;
  context?: ContextPack;
  contextLoading: boolean;
  onRoleChange: (section: Section, role: SectionRole) => void;
  updatingRole: string | null;
  onToggleLink: (link: ProjectLink, enabled: boolean) => void;
  togglingLink: number | null;
  onApproveAndGenerate: () => void;
  approvingGenerating: boolean;
  runState: RunState;
  retrying: boolean;
  onRetry: () => void;
  onOpenBacklog: () => void;
}) {
  const [contextTab, setContextTab] = useState<"links" | "prompt">("links");
  const [showAllLinks, setShowAllLinks] = useState(false);
  const roleCounts = useMemo(() => {
    const counts = new Map<SectionRole, number>();
    for (const section of sections) counts.set(section.role, (counts.get(section.role) ?? 0) + 1);
    return counts;
  }, [sections]);

  const selected = selectedSectionId
    ? sections.find((section) => section.id === selectedSectionId) ?? null
    : null;

  const sectionsById = useMemo(() => new Map(sections.map((section) => [section.id, section])), [sections]);

  useEffect(() => {
    setShowAllLinks(false);
  }, [selected?.id]);

  const selectedLinks = useMemo(() => {
    if (!selected) return [];
    const byOther = new Map<string, (typeof links)[number]>();
    for (const link of links) {
      if (link.source_id !== selected.id && link.target_id !== selected.id) continue;
      const otherId = link.source_id === selected.id ? link.target_id : link.source_id;
      const other = sectionsById.get(otherId);
      if (!other || other.role === "ignored" || other.role === "front_matter") continue;
      const current = byOther.get(otherId);
      if (!current || (link.enabled && !current.enabled) || link.score > current.score) {
        byOther.set(otherId, link);
      }
    }
    return Array.from(byOther.values()).sort(
      (left, right) => Number(right.enabled) - Number(left.enabled) || right.score - left.score,
    );
  }, [links, selected, sectionsById]);

  const copyPrompt = async () => {
    if (!context?.prompt) return;
    try {
      await navigator.clipboard.writeText(context.prompt);
    } catch {
      // Clipboard may be unavailable; the prompt stays visible for manual copy.
    }
  };

  return (
    <div className="pipeline">
      <Wizard steps={STEPS} activeIndex={activeStep} maxIndex={maxStep} onSelect={onStepSelect} />

      {activeStep === 0 && (
        <section className="step-panel">
          <div className="step-panel__head">
            <div>
              <div className="eyebrow">
                <span className="eyebrow__dot" aria-hidden="true" />
                Step 1 · Document
              </div>
              <h2>What we extracted</h2>
              <p>Parsed automatically. Check the completeness signals before moving on.</p>
            </div>
            <Chip tone={document?.warnings.length ? "amber" : "green"} dot>
              {document?.warnings.length ? `${document.warnings.length} warning(s)` : "No warnings"}
            </Chip>
          </div>

          <div className="stat-grid stat-grid--step">
            <StatTile label="Headings" value={document?.stats.headings ?? 0} hint="Detected sections" icon={<ListChecks size={13} />} />
            <StatTile label="Paragraphs" value={document?.stats.paragraphs ?? 0} hint="Body blocks" icon={<ListChecks size={13} />} />
            <StatTile label="Tables" value={document?.stats.tables ?? 0} hint="Flattened rows" icon={<ListChecks size={13} />} />
            <StatTile
              label="Warnings"
              value={document?.warnings.length ?? 0}
              hint="Quality signals"
              icon={<AlertTriangle size={13} />}
            />
          </div>

          <div className="step-panel__grid">
            <Card className="checklist-card" pad={false}>
              <div className="card-head">
                <div>
                  <h3>Expected sections</h3>
                  <p>Template checklist from the ingestion quality pass.</p>
                </div>
                <Chip tone={(project.checklist?.missing?.length ?? 0) ? "amber" : "green"}>
                  {(project.checklist?.found?.length ?? 0) + (project.checklist?.missing?.length ?? 0)} expected
                </Chip>
              </div>
              <div className="checklist-grid">
                <div className="checklist-col">
                  <h4>
                    <CheckCircle size={14} style={{ color: "var(--green)" }} /> Found
                  </h4>
                  <div className="chip-wrap">
                    {(project.checklist?.found ?? []).map((item) => (
                      <Chip key={item} tone="green" dot>
                        {item}
                      </Chip>
                    ))}
                    {!project.checklist?.found?.length && <span className="muted-small">None detected</span>}
                  </div>
                </div>
                <div className="checklist-col">
                  <h4>
                    <AlertTriangle size={14} style={{ color: "var(--muted-2)" }} /> Missing
                  </h4>
                  <div className="chip-wrap">
                    {(project.checklist?.missing ?? []).map((item) => (
                      <Chip key={item} tone="outline" dot>
                        {item}
                      </Chip>
                    ))}
                    {!project.checklist?.missing?.length && (
                      <span className="muted-small">Nothing missing — the document looks complete.</span>
                    )}
                  </div>
                </div>
              </div>
            </Card>

            <Card className="step-panel__warnings" pad>
              <h3>Warnings</h3>
              {document?.warnings.length ? (
                <ul className="warning-list">
                  {document.warnings.map((warning) => (
                    <li key={warning}>
                      <AlertTriangle size={14} />
                      <span>{warning}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted-small">No warnings from the parser.</p>
              )}
            </Card>
          </div>

          <details className="doc-preview">
            <summary>
              <span>Preview extracted text</span>
              <span>{document?.stats.preview?.length ?? 0} blocks</span>
            </summary>
            <div className="doc-preview__body">
              {(document?.stats.preview ?? []).map((block, index) => (
                <div key={`${index}-${block.kind}`} className={`doc-block doc-block--${block.kind}`}>
                  <span className="doc-block__kind">{block.kind}</span>
                  <p>{block.text || "—"}</p>
                </div>
              ))}
              {!document?.stats.preview?.length && <p className="muted-small">No preview available.</p>}
            </div>
          </details>

          <div className="step-panel__actions">
            <Button variant="primary" size="lg" onClick={() => onStepSelect(1)}>
              Continue
            </Button>
          </div>
        </section>
      )}

      {activeStep === 1 && (
        <section className="step-panel">
          <div className="step-panel__head">
            <div>
              <div className="eyebrow">
                <span className="eyebrow__dot" aria-hidden="true" />
                Step 2 · Structure
              </div>
              <h2>Set the role of each section</h2>
              <p>Only <strong>requirement</strong> sections are generated. Change a role from the small menu.</p>
            </div>
          </div>

          <div className="role-summary">
            {ROLE_ORDER.map((role) => {
              const meta = roleMeta(role);
              return (
                <div key={role} className="role-summary__item">
                  <Chip tone={meta.tone}>{meta.label}</Chip>
                  <strong>{roleCounts.get(role) ?? 0}</strong>
                  <span>{meta.description}</span>
                </div>
              );
            })}
          </div>

          <Card className="tree-card" pad={false}>
            <div className="tree-card__head">
              <div>
                <h3>Document outline</h3>
                <p>{sections.length} sections · {roleCounts.get("requirement") ?? 0} requirement leaves</p>
              </div>
            </div>
            <div className="tree-card__body">
              <StructureTree sections={sections} onRoleChange={onRoleChange} updating={updatingRole} />
            </div>
          </Card>

          <div className="step-panel__actions">
            <Button variant="primary" size="lg" onClick={() => onStepSelect(2)}>
              Continue
            </Button>
          </div>
        </section>
      )}

      {activeStep === 2 && (
        <section className="step-panel">
          <div className="step-panel__head">
            <div>
              <div className="eyebrow">
                <span className="eyebrow__dot" aria-hidden="true" />
                Step 3 · Context
              </div>
              <h2>Approve what the model will see</h2>
              <p>The graph shows related sections. Disabled links are excluded from the prompt.</p>
            </div>
          </div>

          <div className="context-layout">
            <Card className="context-layout__graph" pad={false}>
              <ContextGraph
                sections={sections}
                links={links}
                selectedId={selected?.id ?? null}
                onSelect={onSelectSection}
              />
            </Card>

            <Card className="context-panel" pad={false}>
              {selected ? (
                <>
                  <div className="context-panel__head">
                    <div>
                      <span className="context-panel__num">Section {selected.number || "—"}</span>
                      <h3>{selected.title || "Untitled section"}</h3>
                    </div>
                    <Chip tone={roleMeta(selected.role).tone}>{roleMeta(selected.role).label}</Chip>
                  </div>

                  <div className="context-panel__tabs" role="tablist" aria-label="Context panel">
                    <button
                      type="button"
                      role="tab"
                      aria-selected={contextTab === "links"}
                      className={`context-tab ${contextTab === "links" ? "is-active" : ""}`.trim()}
                      onClick={() => setContextTab("links")}
                    >
                      Linked sections
                      <span>{selectedLinks.length}</span>
                    </button>
                    <button
                      type="button"
                      role="tab"
                      aria-selected={contextTab === "prompt"}
                      className={`context-tab ${contextTab === "prompt" ? "is-active" : ""}`.trim()}
                      onClick={() => setContextTab("prompt")}
                    >
                      Prompt preview
                    </button>
                  </div>

                  <div className="context-panel__body">
                    {contextTab === "links" ? (
                      selectedLinks.length ? (
                        <>
                        <ul className="context-links">
                          {(showAllLinks ? selectedLinks : selectedLinks.slice(0, 12)).map((link) => {
                            const otherId = link.source_id === selected.id ? link.target_id : link.source_id;
                            const other = sectionsById.get(otherId);
                            return (
                              <li key={link.id} className={`context-link ${link.enabled ? "" : "is-disabled"}`.trim()}>
                                <button
                                  type="button"
                                  className="context-link__main"
                                  onClick={() => other && onSelectSection(other)}
                                >
                                  <span className="context-link__title">
                                    <b>{other?.number || "§"}</b> {other?.title || "Unknown section"}
                                  </span>
                                  <span className="context-link__reason">
                                    <Link2 size={12} />
                                    {link.kind} · {link.reason || "related section"}
                                  </span>
                                </button>
                                <div className="context-link__side">
                                  <span className="context-link__score" title="Link score">
                                    {Math.round(link.score * 100)}%
                                  </span>
                                  <button
                                    type="button"
                                    className={`switch ${link.enabled ? "is-on" : ""}`.trim()}
                                    aria-label={link.enabled ? "Disable link" : "Enable link"}
                                    aria-pressed={link.enabled}
                                    disabled={togglingLink === link.id}
                                    onClick={() => onToggleLink(link, !link.enabled)}
                                  >
                                    <span />
                                  </button>
                                </div>
                              </li>
                            );
                          })}
                        </ul>
                        {selectedLinks.length > 12 && (
                          <button
                            type="button"
                            className="show-all-links"
                            onClick={() => setShowAllLinks((value) => !value)}
                          >
                            {showAllLinks
                              ? "Show fewer links"
                              : `Show all ${selectedLinks.length} links`}
                          </button>
                        )}
                        </>
                      ) : (
                        <p className="muted-small">No linked sections for this section.</p>
                      )
                    ) : contextLoading ? (
                      <p className="muted-small">Rendering the exact prompt…</p>
                    ) : context ? (
                      <>
                        <div className="prompt-actions">
                          <span className="muted-small">Exact prompt sent to the generator</span>
                          <button type="button" className="mini-action" onClick={() => void copyPrompt()}>
                            <Copy size={13} /> Copy
                          </button>
                        </div>
                        <pre className="prompt-preview">{context.prompt}</pre>
                      </>
                    ) : (
                      <p className="muted-small">Could not render the prompt for this section.</p>
                    )}
                  </div>
                </>
              ) : (
                <div className="context-panel__empty">
                  <Link2 size={20} />
                  <strong>Select a section</strong>
                  <p>Click a node in the graph to inspect its links and prompt.</p>
                </div>
              )}
            </Card>
          </div>

          <div className="step-panel__sticky">
            <div>
              <strong>Human checkpoint 1</strong>
              <span>Generation only starts after this approval.</span>
            </div>
            <Button
              variant="primary"
              size="lg"
              loading={approvingGenerating}
              onClick={onApproveAndGenerate}
            >
              Confirm and generate backlog
            </Button>
          </div>
        </section>
      )}

      {activeStep === 3 && (
        <section className="step-panel">
          <div className="step-panel__head">
            <div>
              <div className="eyebrow">
                <span className="eyebrow__dot" aria-hidden="true" />
                Step 4 · Generation
              </div>
              <h2>Drafting the backlog</h2>
              <p>Live progress from backend run events. The full log lives in History.</p>
            </div>
          </div>
          <GenerationView sections={sections} state={runState} retrying={retrying} onRetry={onRetry} />
        </section>
      )}

      {activeStep === 4 && (
        <section className="step-panel step-panel--center">
          <Card className="step-done" pad>
            <span className="step-done__icon" aria-hidden="true">
              <CheckCircle size={24} />
            </span>
            <h2>Backlog ready for review</h2>
            <p>Every story keeps its source section, criteria and tests. Open the Backlog tab to validate it.</p>
            <Button variant="primary" size="lg" onClick={onOpenBacklog}>
              Open Backlog
            </Button>
          </Card>
        </section>
      )}
    </div>
  );
}
