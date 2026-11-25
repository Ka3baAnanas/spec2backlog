import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, useState } from "react";
import type { Section, SectionRole } from "../../api/client";
import { easePremium } from "../../lib/motion";
import { roleMeta } from "../../lib/status";
import { Chip } from "../Chip";
import { ChevronRight } from "../Icons";

const ROLES: SectionRole[] = ["requirement", "context", "glossary", "front_matter", "ignored"];

type ItemProps = {
  node: Section;
  depth: number;
  childrenOf: (id: string) => Section[];
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onRoleChange: (section: Section, role: SectionRole) => void;
  updating: string | null;
  onEditManual: (section: Section) => void;
  onDeleteManual: (section: Section) => void;
  deletingId: string | null;
};

function StructureItem({
  node,
  depth,
  childrenOf,
  expanded,
  onToggle,
  onRoleChange,
  updating,
  onEditManual,
  onDeleteManual,
  deletingId,
}: ItemProps) {
  const reduced = useReducedMotion();
  const children = childrenOf(node.id);
  const hasChildren = children.length > 0;
  const isOpen = expanded.has(node.id);
  const meta = roleMeta(node.role);

  return (
    <li className="tree-node">
      <div className="tree-row tree-row--role" style={{ paddingLeft: 8 + depth * 16 }}>
        {hasChildren ? (
          <button
            type="button"
            className="tree-row__chevron"
            aria-label={isOpen ? `Collapse ${node.title}` : `Expand ${node.title}`}
            aria-expanded={isOpen}
            onClick={() => onToggle(node.id)}
          >
            <motion.span
              style={{ display: "inline-flex" }}
              animate={{ rotate: isOpen ? 90 : 0 }}
              transition={{ duration: reduced ? 0 : 0.2, ease: easePremium }}
            >
              <ChevronRight size={13} />
            </motion.span>
          </button>
        ) : (
          <span className="tree-row__spacer" aria-hidden="true" />
        )}

        <span className="tree-row__num">{node.number}</span>
        <span className="tree-row__label" title={node.title}>
          {node.title || "Untitled section"}
        </span>
        {node.is_leaf && <span className="tree-row__leaf-dot" aria-hidden="true" />}
        {node.source === "manual" ? (
          <span className="tree-row__manual">
            <Chip tone="blue">Manual</Chip>
            <button type="button" className="tree-row__action" onClick={() => onEditManual(node)}>
              Edit
            </button>
            <button
              type="button"
              className="tree-row__action is-danger"
              disabled={deletingId === node.id}
              onClick={() => {
                if (window.confirm(`Delete manual context "${node.title}"?`)) onDeleteManual(node);
              }}
            >
              Delete
            </button>
          </span>
        ) : (
          <select
            className={`role-select role-select--${meta.tone}`}
            value={node.role}
            disabled={updating === node.id}
            aria-label={`Role for ${node.title || "untitled section"}`}
            onChange={(event) => onRoleChange(node, event.target.value as SectionRole)}
          >
            {ROLES.map((role) => (
              <option key={role} value={role}>
                {roleMeta(role).label}
              </option>
            ))}
          </select>
        )}
      </div>

      <AnimatePresence initial={false}>
        {hasChildren && isOpen && (
          <motion.ul
            className="tree"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.22, ease: easePremium }}
            style={{ overflow: "hidden" }}
          >
            {children.map((child) => (
              <StructureItem
                key={child.id}
                node={child}
                depth={depth + 1}
                childrenOf={childrenOf}
                expanded={expanded}
                onToggle={onToggle}
                onRoleChange={onRoleChange}
                updating={updating}
                onEditManual={onEditManual}
                onDeleteManual={onDeleteManual}
                deletingId={deletingId}
              />
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

export function StructureTree({
  sections,
  onRoleChange,
  updating,
  onEditManual,
  onDeleteManual,
  deletingId,
}: {
  sections: Section[];
  onRoleChange: (section: Section, role: SectionRole) => void;
  updating: string | null;
  onEditManual: (section: Section) => void;
  onDeleteManual: (section: Section) => void;
  deletingId: string | null;
}) {
  const { roots, childrenOf, defaultExpanded } = useMemo(() => {
    const ids = new Set(sections.map((section) => section.id));
    const parentMap = new Map<string | null, Section[]>();
    for (const section of sections) {
      const key = section.parent_id && ids.has(section.parent_id) ? section.parent_id : null;
      const bucket = parentMap.get(key);
      if (bucket) bucket.push(section);
      else parentMap.set(key, [section]);
    }
    const parents = new Set(sections.filter((section) => section.parent_id).map((section) => section.parent_id));
    return {
      roots: parentMap.get(null) ?? [],
      childrenOf: (id: string) => parentMap.get(id) ?? [],
      defaultExpanded: new Set(
        sections.filter((section) => parents.has(section.id) && section.level < 2).map((section) => section.id),
      ),
    };
  }, [sections]);

  const [expanded, setExpanded] = useState<Set<string>>(defaultExpanded);
  const initialized = useRef(false);

  useEffect(() => {
    if (initialized.current || sections.length === 0) return;
    setExpanded(defaultExpanded);
    initialized.current = true;
  }, [sections.length, defaultExpanded]);

  const toggle = (id: string) => {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <ul className="tree" role="tree" aria-label="Document structure">
      {roots.map((node) => (
        <StructureItem
          key={node.id}
          node={node}
          depth={0}
          childrenOf={childrenOf}
          expanded={expanded}
          onToggle={toggle}
          onRoleChange={onRoleChange}
          updating={updating}
          onEditManual={onEditManual}
          onDeleteManual={onDeleteManual}
          deletingId={deletingId}
        />
      ))}
    </ul>
  );
}
