import { useMemo, useState, type ReactNode } from "react";
import type { ContextPack, LinkKind, ProjectLink, Section } from "../../api/client";
import { roleMeta } from "../../lib/status";
import { Button } from "../Button";
import { Card } from "../Card";
import { Chip } from "../Chip";
import { Copy, Link2 } from "../Icons";

type Tab = "section" | "links" | "prompt";

function estimateTokens(text: string): number {
  return Math.max(1, Math.ceil((text || "").length / 4));
}

function linkOtherId(link: ProjectLink, sectionId: string): string {
  return link.source_id === sectionId ? link.target_id : link.source_id;
}

function reasonFor(link: ProjectLink, other: Section | undefined): string {
  if (link.kind === "similarity") return "Similar meaning";
  if (link.kind === "reference") {
    return `Explicitly referenced: see §${other?.number || link.reason.match(/\d+(?:\.\d+)*/)?.[0] || "?"}`;
  }
  if (link.kind === "lexical") {
    const words = link.reason.includes(":")
      ? link.reason.split(":").slice(1).join(":").trim()
      : "";
    return words ? `Shares words: ${words}` : "Shares words with this section";
  }
  if (link.kind === "manual") return "Manually linked";
  return link.reason || "Related section";
}

function strengthFor(score: number): { label: string; key: string } {
  if (score >= 0.75) return { label: "Strong", key: "strong" };
  if (score >= 0.55) return { label: "Medium", key: "medium" };
  return { label: "Weak", key: "weak" };
}

function kindTone(kind: LinkKind): "blue" | "yellow" | "outline" {
  if (kind === "similarity") return "blue";
  if (kind === "reference") return "yellow";
  return "outline";
}

function PromptBlock({
  label,
  tokens,
  defaultOpen = false,
  children,
}: {
  label: string;
  tokens: number;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <details
      className="prompt-block"
      open={open}
      onToggle={(event) => setOpen(event.currentTarget.open)}
    >
      <summary>
        <span>{label}</span>
        <span className="prompt-block__tokens">~{tokens.toLocaleString()} tokens</span>
      </summary>
      <div className="prompt-block__body">{children}</div>
    </details>
  );
}

export function ContextPanel({
  selected,
  sectionsById,
  links,
  context,
  contextLoading,
  onToggleLink,
  togglingLink,
  onSaveExtraInstructions,
  savingInstructions,
}: {
  selected: Section | null;
  sectionsById: Map<string, Section>;
  links: ProjectLink[];
  context?: ContextPack;
  contextLoading: boolean;
  onToggleLink: (link: ProjectLink, enabled: boolean) => void;
  togglingLink: number | null;
  onSaveExtraInstructions: (sectionId: string, text: string) => void;
  savingInstructions: boolean;
}) {
  const [tab, setTab] = useState<Tab>("section");
  const [showAllLinks, setShowAllLinks] = useState(false);
  const [expandedLinkId, setExpandedLinkId] = useState<number | null>(null);
  const [extraInstructions, setExtraInstructions] = useState(
    selected?.extra_instructions ?? "",
  );

  const selectedKey = selected?.id ?? null;
  const [lastSelected, setLastSelected] = useState<string | null>(selectedKey);
  if (selectedKey !== lastSelected) {
    setLastSelected(selectedKey);
    setTab("section");
    setShowAllLinks(false);
    setExpandedLinkId(null);
    setExtraInstructions(selected?.extra_instructions ?? "");
  }

  const selectedLinks = useMemo(() => {
    if (!selected) return [];
    const byOther = new Map<string, ProjectLink>();
    for (const link of links) {
      if (link.source_id !== selected.id && link.target_id !== selected.id) continue;
      const otherId = linkOtherId(link, selected.id);
      const other = sectionsById.get(otherId);
      if (!other || other.role === "ignored" || other.role === "front_matter") continue;
      const current = byOther.get(otherId);
      if (!current || (link.enabled && !current.enabled) || link.score > current.score) {
        byOther.set(otherId, link);
      }
    }
    return Array.from(byOther.values()).sort((left, right) => right.score - left.score);
  }, [links, selected, sectionsById]);

  const contextData = context?.context;
  const globalSections = contextData?.global_context ?? [];
  const glossary = contextData?.glossary ?? [];
  const linkedSections = contextData?.linked_sections ?? [];

  const globalText = [
    ...globalSections.map((item) => `[${item.number} ${item.title}]\n${item.text}`),
    ...glossary.map((item) => `- ${item.term}: ${item.definition}`),
  ].join("\n\n");
  const linkedText = linkedSections
    .map((item) => `[${item.number} ${item.title}]\n${item.text}`)
    .join("\n\n");
  const instructions = context?.instructions ?? "";
  const totalTokens =
    context?.tokens ||
    estimateTokens(instructions) +
      estimateTokens(globalText) +
      estimateTokens(contextData?.text ?? selected?.text ?? "") +
      estimateTokens(linkedText);

  const copyPrompt = async () => {
    if (!context) return;
    const full = [instructions, context.prompt].filter(Boolean).join("\n\n");
    try {
      await navigator.clipboard.writeText(full);
    } catch {
      // Clipboard may be unavailable; the prompt stays available in the cards.
    }
  };

  const visibleLinks = showAllLinks ? selectedLinks : selectedLinks.slice(0, 8);
  const dirty =
    selected !== null && extraInstructions.trim() !== (selected.extra_instructions ?? "").trim();

  return (
    <Card className="context-panel" pad={false}>
      {selected ? (
        <>
          <div className="context-panel__head">
            <div>
              <span className="context-panel__num">
                {selected.source === "manual" ? "Manual context" : `Section ${selected.number || "n/a"}`}
              </span>
              <h3>{selected.title || "Untitled section"}</h3>
            </div>
            <div className="context-panel__tags">
              {selected.source === "manual" && <Chip tone="blue">Manual</Chip>}
              <Chip tone={roleMeta(selected.role).tone}>{roleMeta(selected.role).label}</Chip>
            </div>
          </div>

          <div className="context-panel__tabs" role="tablist" aria-label="Context panel">
            <button
              type="button"
              role="tab"
              aria-selected={tab === "section"}
              className={`context-tab ${tab === "section" ? "is-active" : ""}`.trim()}
              onClick={() => setTab("section")}
            >
              Section
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "links"}
              className={`context-tab ${tab === "links" ? "is-active" : ""}`.trim()}
              onClick={() => setTab("links")}
            >
              Linked sections <span>{selectedLinks.length}</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={tab === "prompt"}
              className={`context-tab ${tab === "prompt" ? "is-active" : ""}`.trim()}
              onClick={() => setTab("prompt")}
            >
              Prompt
            </button>
          </div>

          <div className="context-panel__body">
            {tab === "section" && (
              <div className="context-section">
                {selected.lineage.length > 0 && (
                  <p className="context-section__path">{selected.lineage.join(" > ")}</p>
                )}
                <p className="context-section__text">{selected.text || "This section has no text."}</p>
              </div>
            )}

            {tab === "links" && (
              <>
                {selectedLinks.length ? (
                  <>
                    <ul className="context-links">
                      {visibleLinks.map((link) => {
                        const other = sectionsById.get(linkOtherId(link, selected.id));
                        const strength = strengthFor(link.score);
                        const expanded = expandedLinkId === link.id;
                        return (
                          <li
                            key={link.id}
                            className={`context-link ${link.enabled ? "" : "is-disabled"}`.trim()}
                          >
                            <div className="context-link__row">
                              <button
                                type="button"
                                className="context-link__main"
                                aria-expanded={expanded}
                                onClick={() => setExpandedLinkId(expanded ? null : link.id)}
                              >
                                <span className="context-link__title">
                                  <b>{other?.source === "manual" ? "Manual" : `§${other?.number || "?"}`}</b>{" "}
                                  {other?.title || "Unknown section"}
                                </span>
                                <span className={`context-link__reason is-${link.kind}`}>
                                  <Link2 size={12} />
                                  {reasonFor(link, other)}
                                </span>
                                <span className={`strength strength--${strength.key}`}>
                                  <span className="strength__track">
                                    <i style={{ width: `${Math.round(link.score * 100)}%` }} />
                                  </span>
                                  {strength.label}
                                </span>
                              </button>
                              <div className="context-link__side">
                                <Chip tone={kindTone(link.kind)}>{link.kind}</Chip>
                                <button
                                  type="button"
                                  className={`switch ${link.enabled ? "is-on" : ""}`.trim()}
                                  aria-label={link.enabled ? "Exclude link" : "Include link"}
                                  aria-pressed={link.enabled}
                                  disabled={togglingLink === link.id}
                                  onClick={() => onToggleLink(link, !link.enabled)}
                                >
                                  <span />
                                </button>
                              </div>
                            </div>
                            {expanded && (
                              <p className="context-link__text">
                                {other?.text || "This section has no text."}
                              </p>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                    {selectedLinks.length > 8 && (
                      <button
                        type="button"
                        className="show-all-links"
                        onClick={() => setShowAllLinks((value) => !value)}
                      >
                        {showAllLinks ? "Show fewer" : `Show all ${selectedLinks.length} links`}
                      </button>
                    )}
                  </>
                ) : (
                  <p className="muted-small">No linked sections for this section.</p>
                )}
              </>
            )}

            {tab === "prompt" && (
              <div className="prompt-panel">
                {contextLoading ? (
                  <p className="muted-small">Rendering the exact prompt...</p>
                ) : context ? (
                  <>
                    <div className="prompt-toolbar">
                      <span className="prompt-tokens">~{totalTokens.toLocaleString()} tokens</span>
                      <Button
                        size="sm"
                        variant="secondary"
                        icon={<Copy size={13} />}
                        onClick={() => void copyPrompt()}
                      >
                        Copy
                      </Button>
                    </div>

                    <PromptBlock label="Instructions" tokens={estimateTokens(instructions)}>
                      <pre className="prompt-block__text">{instructions || "No system instructions."}</pre>
                    </PromptBlock>

                    <PromptBlock
                      label="Global context"
                      tokens={estimateTokens(globalText)}
                      defaultOpen
                    >
                      <p className="muted-small">
                        Always sent: context sections, glossary and manual context.
                      </p>
                      {globalSections.length ? (
                        <div className="prompt-context-list">
                          {globalSections.map((item) => (
                            <div key={item.section_id} className="prompt-context-item">
                              <div className="prompt-context-item__head">
                                <span>
                                  {item.number ? `§${item.number}` : "Context"}{" "}
                                  {item.title || "Untitled"}
                                </span>
                                {item.source === "manual" && <Chip tone="blue">Manual</Chip>}
                              </div>
                              <p>{item.text}</p>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="muted-small">No context sections.</p>
                      )}
                      {glossary.length > 0 && (
                        <div className="prompt-glossary">
                          <h4>Glossary</h4>
                          <ul>
                            {glossary.map((item) => (
                              <li key={`${item.kind}-${item.term}`}>
                                <b>{item.term}</b>: {item.definition}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </PromptBlock>

                    <PromptBlock
                      label="This section"
                      tokens={estimateTokens(contextData?.text ?? selected.text)}
                    >
                      <pre className="prompt-block__text">
                        {contextData?.text || selected.text || "No section text."}
                      </pre>
                    </PromptBlock>

                    <PromptBlock
                      label="Linked sections"
                      tokens={estimateTokens(linkedText)}
                    >
                      {linkedText ? (
                        <pre className="prompt-block__text">{linkedText}</pre>
                      ) : (
                        <p className="muted-small">No linked sections in this prompt.</p>
                      )}
                    </PromptBlock>
                  </>
                ) : (
                  <p className="muted-small">Could not render the prompt for this section.</p>
                )}

                <div className="extra-instructions">
                  <div className="extra-instructions__head">
                    <h4>Extra instructions for this section</h4>
                    <span>~{estimateTokens(extraInstructions).toLocaleString()} tokens</span>
                  </div>
                  <textarea
                    className="input input--area"
                    value={extraInstructions}
                    onChange={(event) => setExtraInstructions(event.target.value)}
                    placeholder="Add constraints, edge cases, wording preferences..."
                  />
                  <div className="extra-instructions__foot">
                    <span className="muted-small">
                      Saved with this section and appended to its prompt at generation.
                    </span>
                    <Button
                      size="sm"
                      variant="primary"
                      loading={savingInstructions}
                      disabled={!dirty || savingInstructions}
                      onClick={() => {
                        const text = extraInstructions.trim();
                        setExtraInstructions(text);
                        onSaveExtraInstructions(selected.id, text);
                      }}
                    >
                      Save instructions
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
      ) : (
        <div className="context-panel__empty">
          <Link2 size={20} />
          <strong>Select a section</strong>
          <p>Click a node in the graph to read it, inspect links and shape its prompt.</p>
        </div>
      )}
    </Card>
  );
}
