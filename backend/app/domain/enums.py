import enum


class PipelineState(str, enum.Enum):
    uploaded = "uploaded"
    parsed = "parsed"
    structured = "structured"
    linked = "linked"
    awaiting_context_approval = "awaiting_context_approval"
    generating = "generating"
    generated = "generated"
    in_review = "in_review"
    approved = "approved"
    exported = "exported"
    failed = "failed"


class SectionRole(str, enum.Enum):
    requirement = "requirement"
    context = "context"
    glossary = "glossary"
    front_matter = "front_matter"
    ignored = "ignored"


class LinkKind(str, enum.Enum):
    similarity = "similarity"
    reference = "reference"
    lexical = "lexical"
    manual = "manual"


class ItemKind(str, enum.Enum):
    epic = "epic"
    story = "story"
    test = "test"


class ItemStatus(str, enum.Enum):
    proposed = "proposed"
    approved = "approved"
    edited = "edited"
    rejected = "rejected"


class QuestionStatus(str, enum.Enum):
    open = "open"
    answered = "answered"
    ignored = "ignored"
