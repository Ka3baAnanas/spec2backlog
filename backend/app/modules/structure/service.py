from app.modules.ingestion.pivot import PivotDocument
from app.modules.structure.classifier import classify_tree
from app.modules.structure.tree import SectionNode, build_tree, ordered_nodes


def build_structure(pivot: PivotDocument, new_id) -> dict[str, SectionNode]:
    return classify_tree(build_tree(pivot, new_id))


def structure_nodes(pivot: PivotDocument, new_id) -> list[SectionNode]:
    return ordered_nodes(build_structure(pivot, new_id))
