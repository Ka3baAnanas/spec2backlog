from pydantic import BaseModel


class ProjectOut(BaseModel):
    id: str
    name: str
    status: str
    checklist: dict = {}
    model_config = {"from_attributes": True}


class NodeOut(BaseModel):
    id: str
    parent_id: str | None
    number: str
    title: str
    level: int
    is_leaf: bool
    is_global: bool
    is_front_matter: bool = False
    lineage: list[str]
    text: str = ""
    model_config = {"from_attributes": True}


class ItemOut(BaseModel):
    id: str
    kind: str
    title: str
    parent_item_id: str | None
    source_node_id: str
    status: str
    body: dict
    questions: list
    model_config = {"from_attributes": True}


class ItemPatch(BaseModel):
    title: str | None = None
    body: dict | None = None
    status: str | None = None
    by: str = "ba"
