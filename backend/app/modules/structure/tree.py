"""Pivot -> tree. Headings are nodes; text under the last heading belongs to that node."""

import re
from dataclasses import dataclass, field

from app.domain.enums import SectionRole
from app.modules.ingestion.pivot import PivotDocument

FRONT_MATTER_TITLES = (
    "table des matières", "table des matieres", "table of contents",
    "historique des versions", "validation", "sommaire",
)
NUM_RE = re.compile(r"^(\d+(?:\.\d+)*)[.)]?\s+(.*)$")


def is_front_matter_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", (title or "").strip().lower()).strip(" .:-–—")
    return normalized in FRONT_MATTER_TITLES


@dataclass
class SectionNode:
    id: str
    title: str
    number: str
    level: int
    parent: str | None
    text: str = ""
    children: list[str] = field(default_factory=list)
    lineage: list[str] = field(default_factory=list)
    role: str = SectionRole.requirement.value

    @property
    def is_leaf(self) -> bool:
        return not self.children


def build_tree(doc: PivotDocument, new_id) -> dict[str, SectionNode]:
    nodes: dict[str, SectionNode] = {}
    source = doc.source or "document"
    root = SectionNode(new_id(), source, "", 0, None, lineage=[source])
    nodes[root.id] = root
    stack = [root]
    for block in doc.blocks:
        if block.kind == "heading":
            while stack and stack[-1].level >= block.level:
                stack.pop()
            parent = stack[-1] if stack else root
            match = NUM_RE.match(block.text)
            number, title = (match.group(1), match.group(2)) if match else ("", block.text)
            node = SectionNode(
                new_id(),
                title,
                number,
                block.level,
                parent.id,
                lineage=parent.lineage + [f"{number} {title}".strip()],
            )
            nodes[node.id] = node
            parent.children.append(node.id)
            stack.append(node)
        else:
            current = stack[-1]
            current.text += ("\n" if current.text else "") + block.text
    return nodes


def dfs_leaves(nodes: dict[str, SectionNode], root_id: str):
    """Depth-first walk yielding leaves that contain text, with their lineage."""
    def walk(node_id: str):
        node = nodes[node_id]
        if node.is_leaf:
            if node.text.strip():
                yield node
        else:
            for child_id in node.children:
                yield from walk(child_id)

    yield from walk(root_id)


def ordered_nodes(nodes: dict[str, SectionNode]) -> list[SectionNode]:
    if not nodes:
        return []
    root_id = next(iter(nodes))
    out: list[SectionNode] = []

    def walk(node_id: str):
        node = nodes[node_id]
        out.append(node)
        for child_id in node.children:
            walk(child_id)

    walk(root_id)
    return out
