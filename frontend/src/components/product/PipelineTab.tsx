import { useMemo, useState } from "react";
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
import { CheckCircle, Plus, X } from "../Icons";
import { ContextGraph } from "./ContextGraph";
import { ContextPanel } from "./ContextPanel";
import { DocumentView } from "./DocumentView";
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

function StepNav({
  index,
  onStepSelect,
  onOpenBacklog,
  openBacklog = false,
}: {
  index: number;
  onStepSelect: (index: number) => void;
  onOpenBacklog: () => void;
  openBacklog?: boolean;
}) {
  const last = index === STEPS.length - 1;
  return (
    <div className="step-nav">
      <Button variant="secondary" size="lg" disabled={index === 0} onClick={() => onStepSelect(index - 1)}>
        Back
      </Button>
      <Button
        variant="primary"
        size="lg"
        onClick={() => (openBacklog || last ? onOpenBacklog() : onStepSelect(index + 1))}
      >
        Next
      </Button>
    </div>
  );
}

export function PipelineTab({
  project,
  document,
  sections,
  links,
  activeStep,
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
  onSaveManualContext,
  onDeleteManualContext,
  manualSaving,
  manualDeletingId,
  onClearSelection,
  onSaveExtraInstructions,
  savingInstructions,
}: {
  project: Project;
  document?: ProjectDocument;
  sections: Section[];
  links: ProjectLink[];
  activeStep: number;
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
  onSaveManualContext: (sectionId: string | null, title: string, text: string) => void;
  onDeleteManualContext: (section: Section) => void;
  manualSaving: boolean;
  manualDeletingId: string | null;
  onClearSelection: () => void;
  onSaveExtraInstructions: (sectionId: string, text: string) => void;
  savingInstructions: boolean;
}) {
  const [manualOpen, setManualOpen] = useState(false);
  const [manualEditing, setManualEditing] = useState<Section | null>(null);
  const [manualTitle, setManualTitle] = useState("");
  const [manualText, setManualText] = useState("");

  const openManualContext = (section?: Section) => {
    setManualEditing(section ?? null);
    setManualTitle(section?.title ?? "");
    setManualText(section?.text ?? "");
    setManualOpen(true);
  };

  const closeManualContext = () => {
    if (manualSaving) return;
    setManualOpen(false);
    setManualEditing(null);
  };

  const saveManualContext = () => {
    if (!manualTitle.trim() || !manualText.trim()) return;
    onSaveManualContext(manualEditing?.id ?? null, manualTitle.trim(), manualText.trim());
    setManualOpen(false);
    setManualEditing(null);
  };
  const roleCounts = useMemo(() => {
    const counts = new Map<SectionRole, number>();
    for (const section of sections) counts.set(section.role, (counts.get(section.role) ?? 0) + 1);
    return counts;
  }, [sections]);

  const selected = selectedSectionId
    ? sections.find((section) => section.id === selectedSectionId) ?? null
    : null;
  const sectionsById = useMemo(
    () => new Map(sections.map((section) => [section.id, section])),
    [sections],
  );

  const requirementLeaves = roleCounts.get("requirement") ?? 0;
  const generationActive =
    runState.stages.generation.status === "active" || project.status === "generating";
  const generateDisabledReason = approvingGenerating
    ? "Generation is starting."
    : generationActive
      ? "Generation is already running."
      : requirementLeaves === 0
        ? "Set at least one section as requirement before generating."
        : undefined;

  return (
    <div className="pipeline">
      <Wizard steps={STEPS} activeIndex={activeStep} onSelect={onStepSelect} />

      {activeStep === 0 && (
        <section className="step-panel">
          <div className="step-panel__head">
            <div>
              <div className="eyebrow">
                <span className="eyebrow__dot" aria-hidden="true" />
                Step 1 · Document
              </div>
              <h2>What we extracted</h2>
              <p>Read the parsed document, then check the signals before moving on.</p>
            </div>
          </div>

          <DocumentView doc={document} checklist={project.checklist} />

          <StepNav index={0} onStepSelect={onStepSelect} onOpenBacklog={onOpenBacklog} />
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
                  <div className="role-summary__top">
                    <Chip tone={meta.tone}>{meta.label}</Chip>
                    <strong>{roleCounts.get(role) ?? 0}</strong>
                  </div>
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
              <Button
                variant="secondary"
                size="sm"
                icon={<Plus size={14} />}
                onClick={() => openManualContext()}
              >
                Add context
              </Button>
            </div>
            <div className="tree-card__body">
              <StructureTree
                sections={sections}
                onRoleChange={onRoleChange}
                updating={updatingRole}
                onEditManual={openManualContext}
                onDeleteManual={onDeleteManualContext}
                deletingId={manualDeletingId}
              />
            </div>
          </Card>

          <StepNav index={1} onStepSelect={onStepSelect} onOpenBacklog={onOpenBacklog} />
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
                onClear={onClearSelection}
              />
            </Card>

            <ContextPanel
              selected={selected}
              sectionsById={sectionsById}
              links={links}
              context={context}
              contextLoading={contextLoading}
              onToggleLink={onToggleLink}
              togglingLink={togglingLink}
              onSaveExtraInstructions={onSaveExtraInstructions}
              savingInstructions={savingInstructions}
            />
          </div>

          <div className="step-panel__sticky">
            <div>
              <strong>Human checkpoint 1</strong>
              <span>Generation only starts after this approval.</span>
            </div>
            <Button
              variant="accent"
              size="lg"
              loading={approvingGenerating}
              disabled={Boolean(generateDisabledReason)}
              title={generateDisabledReason}
              onClick={onApproveAndGenerate}
            >
              Confirm and generate backlog
            </Button>
          </div>

          <StepNav index={2} onStepSelect={onStepSelect} onOpenBacklog={onOpenBacklog} />
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
              <p>Live progress from backend run events. The full log lives in Activity.</p>
            </div>
          </div>
          <GenerationView sections={sections} state={runState} retrying={retrying} onRetry={onRetry} />
          <StepNav index={3} onStepSelect={onStepSelect} onOpenBacklog={onOpenBacklog} openBacklog />
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
          </Card>
          <StepNav index={4} onStepSelect={onStepSelect} onOpenBacklog={onOpenBacklog} />
        </section>
      )}

      {manualOpen && (
        <div className="modal-backdrop" onClick={closeManualContext}>
          <div
            className="modal manual-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="manual-context-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="modal__head">
              <div>
                <div className="drawer__eyebrow">Analyst note</div>
                <h2 id="manual-context-title">
                  {manualEditing ? "Edit manual context" : "Add context"}
                </h2>
              </div>
              <button
                type="button"
                className="drawer__close"
                onClick={closeManualContext}
                aria-label="Close"
              >
                <X size={15} />
              </button>
            </div>
            <div className="modal__body">
              <label className="field">
                <span>Title</span>
                <input
                  className="input"
                  value={manualTitle}
                  onChange={(event) => setManualTitle(event.target.value)}
                  placeholder="e.g. Client constraints"
                  maxLength={200}
                  autoFocus
                />
              </label>
              <label className="field">
                <span>Context</span>
                <textarea
                  className="input input--area manual-modal__text"
                  value={manualText}
                  onChange={(event) => setManualText(event.target.value)}
                  placeholder="Business rules, acronyms, client constraints..."
                />
              </label>
            </div>
            <div className="modal__foot">
              <Button variant="secondary" onClick={closeManualContext}>
                Cancel
              </Button>
              <Button
                variant="primary"
                loading={manualSaving}
                disabled={!manualTitle.trim() || !manualText.trim()}
                onClick={saveManualContext}
              >
                {manualEditing ? "Save changes" : "Add context"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
