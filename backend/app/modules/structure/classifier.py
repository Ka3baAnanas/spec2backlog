"""Section role classification. Heuristic now, LLM later."""

from app.domain.enums import SectionRole
from app.modules.structure.tree import SectionNode, is_front_matter_title

GLOSSARY_HINTS = ("glossaire", "glossary", "définitions", "definitions", "acronymes", "acronyms")
CONTEXT_HINTS = (
    "contexte", "context", "objectifs", "objectives", "périmètre", "perimetre", "scope",
    "introduction", "présentation", "presentation", "enjeux", "background",
)


def classify_section(node: SectionNode) -> str:
    title = (node.title or "").strip()
    lowered = title.lower()
    if is_front_matter_title(title):
        return SectionRole.front_matter.value
    if any(hint in lowered for hint in GLOSSARY_HINTS):
        return SectionRole.glossary.value
    if any(hint in lowered for hint in CONTEXT_HINTS):
        return SectionRole.context.value
    if node.is_leaf and node.text.strip():
        return SectionRole.requirement.value
    return SectionRole.ignored.value


def classify_tree(nodes: dict[str, SectionNode]) -> dict[str, SectionNode]:
    for node in nodes.values():
        node.role = classify_section(node)
    return nodes
