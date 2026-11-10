import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import type { Node } from "../api/client";
import { easePremium, softSpring } from "../lib/motion";
import { ChevronRight } from "./Icons";

type TreeViewProps = {
  nodes: Node[];
  selectedId: string | null;
  onSelect: (node: Node) => void;
};

type TreeItemProps = {
  node: Node;
  depth: number;
  childrenOf: (id: string) => Node[];
  expanded: Set<string>;
  selectedId: string | null;
  onSelect: (node: Node) => void;
  onToggle: (id: string) => void;
  reduced: boolean;
};

function TreeItem({
  node,
  depth,
  childrenOf,
  expanded,
  selectedId,
  onSelect,
  onToggle,
  reduced,
}: TreeItemProps) {
  const children = childrenOf(node.id);
  const hasChildren = children.length > 0;
  const isOpen = expanded.has(node.id);
  const isSelected = selectedId === node.id;

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect(node);
    }
    if (event.key === "ArrowRight" && hasChildren && !isOpen) {
      event.preventDefault();
      onToggle(node.id);
    }
    if (event.key === "ArrowLeft" && hasChildren && isOpen) {
      event.preventDefault();
      onToggle(node.id);
    }
  };

  return (
    <li className="tree-node" role="treeitem" aria-expanded={hasChildren ? isOpen : undefined} aria-selected={isSelected}>
      <div
        className={[
          "tree-row",
          isSelected ? "is-selected" : "",
          node.is_leaf ? "is-leaf" : "",
        ]
          .filter(Boolean)
          .join(" ")}
        style={{ paddingLeft: 8 + depth * 14 }}
        tabIndex={0}
        onClick={() => onSelect(node)}
        onKeyDown={handleKeyDown}
      >
        {isSelected && (
          <motion.span
            layoutId="tree-selected"
            className="tree-selected-bg"
            transition={reduced ? { duration: 0 } : softSpring}
            aria-hidden="true"
          />
        )}

        {hasChildren ? (
          <button
            type="button"
            className="tree-row__chevron"
            aria-label={isOpen ? `Collapse ${node.title}` : `Expand ${node.title}`}
            aria-expanded={isOpen}
            onClick={(event) => {
              event.stopPropagation();
              onToggle(node.id);
            }}
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
      </div>

      <AnimatePresence initial={false}>
        {hasChildren && isOpen && (
          <motion.ul
            key="children"
            className="tree"
            role="group"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: reduced ? 0 : 0.22, ease: easePremium }}
            style={{ overflow: "hidden" }}
          >
            {children.map((child) => (
              <TreeItem
                key={child.id}
                node={child}
                depth={depth + 1}
                childrenOf={childrenOf}
                expanded={expanded}
                selectedId={selectedId}
                onSelect={onSelect}
                onToggle={onToggle}
                reduced={reduced}
              />
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </li>
  );
}

export function TreeView({ nodes, selectedId, onSelect }: TreeViewProps) {
  const reduced = useReducedMotion() ?? false;
  const initialized = useRef(false);
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set());

  const { roots, childrenOf, byId } = useMemo(() => {
    const ids = new Set(nodes.map((node) => node.id));
    const parentMap = new Map<string | null, Node[]>();
    const byIdMap = new Map<string, Node>();

    for (const node of nodes) {
      byIdMap.set(node.id, node);
      const key = node.parent_id && ids.has(node.parent_id) ? node.parent_id : null;
      const bucket = parentMap.get(key);
      if (bucket) bucket.push(node);
      else parentMap.set(key, [node]);
    }

    return {
      roots: parentMap.get(null) ?? [],
      byId: byIdMap,
      childrenOf: (id: string) => parentMap.get(id) ?? [],
    };
  }, [nodes]);

  useEffect(() => {
    if (initialized.current || nodes.length === 0) return;
    const withChildren = new Set<string>();
    for (const node of nodes) {
      if (node.parent_id) withChildren.add(node.parent_id);
    }
    setExpanded(
      new Set(
        nodes
          .filter((node) => withChildren.has(node.id) && node.level < 2)
          .map((node) => node.id),
      ),
    );
    initialized.current = true;
  }, [nodes]);

  useEffect(() => {
    if (!selectedId) return;
    const ancestors: string[] = [];
    let current = byId.get(selectedId);
    while (current?.parent_id) {
      ancestors.push(current.parent_id);
      current = byId.get(current.parent_id);
    }
    if (!ancestors.length) return;
    setExpanded((previous) => {
      const next = new Set(previous);
      let changed = false;
      for (const id of ancestors) {
        if (!next.has(id)) {
          next.add(id);
          changed = true;
        }
      }
      return changed ? next : previous;
    });
  }, [selectedId, byId]);

  const toggle = useCallback((id: string) => {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return (
    <ul className="tree" role="tree" aria-label="Document outline">
      {roots.map((node) => (
        <TreeItem
          key={node.id}
          node={node}
          depth={0}
          childrenOf={childrenOf}
          expanded={expanded}
          selectedId={selectedId}
          onSelect={onSelect}
          onToggle={toggle}
          reduced={reduced}
        />
      ))}
    </ul>
  );
}
