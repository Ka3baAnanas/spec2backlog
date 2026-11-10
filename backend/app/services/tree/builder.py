"""Pivot -> tree. Headings are nodes; text under the last heading is that node's content.
A node with no sub-heading is a LEAF."""
import re
from dataclasses import dataclass, field

from app.services.ingestion.pivot import PivotDocument

GLOBAL_HINTS = ("glossaire", "contexte", "définitions", "acronymes")
FRONT_MATTER_TITLES = (
    "table des matières", "table des matieres", "table of contents",
    "historique des versions", "validation", "sommaire",
)
NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(.*)$")


def is_front_matter_title(title: str) -> bool:
    """True for template boilerplate that must never be sent to the graph/LLM."""
    t = re.sub(r"\s+", " ", (title or "").strip().lower()).strip(" .:-–—")
    return t in FRONT_MATTER_TITLES


@dataclass
class TNode:
    id: str
    title: str
    number: str
    level: int
    parent: str | None
    text: str = ""
    children: list[str] = field(default_factory=list)
    lineage: list[str] = field(default_factory=list)
    is_global: bool = False
    is_front_matter: bool = False

    @property
    def is_leaf(self) -> bool:
        return not self.children


def build_tree(doc: PivotDocument, new_id) -> dict[str, TNode]:
    nodes: dict[str, TNode] = {}
    root = TNode(new_id(), doc.source or "document", "", 0, None, lineage=[doc.source or "document"])
    nodes[root.id] = root
    stack = [root]
    for b in doc.blocks:
        if b.kind == "heading":
            while stack and stack[-1].level >= b.level:
                stack.pop()
            parent = stack[-1] if stack else root
            m = NUM_RE.match(b.text)
            number, title = (m.group(1), m.group(2)) if m else ("", b.text)
            n = TNode(new_id(), title, number, b.level, parent.id,
                      lineage=parent.lineage + [f"{number} {title}".strip()],
                      is_global=any(h in title.lower() for h in GLOBAL_HINTS),
                      is_front_matter=parent.is_front_matter or is_front_matter_title(title))
            nodes[n.id] = n
            parent.children.append(n.id)
            stack.append(n)
        else:
            cur = stack[-1]
            cur.text += (("\n" if cur.text else "") + b.text)
    return nodes


def dfs_leaves(nodes: dict[str, TNode], root_id: str):
    """Depth-first walk, yielding leaves WITH their lineage (the friend's DFS)."""
    def walk(nid: str):
        n = nodes[nid]
        if n.is_leaf:
            if n.text.strip():
                yield n
        else:
            for c in n.children:
                yield from walk(c)
    yield from walk(root_id)
