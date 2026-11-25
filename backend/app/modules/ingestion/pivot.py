"""Pivot format: the single standard representation every input (Word/PDF/scan) is converted to."""

from dataclasses import dataclass, field


@dataclass
class Block:
    kind: str  # heading | paragraph | list | table
    text: str
    level: int = 0  # heading level (1..n); 0 otherwise


@dataclass
class PivotDocument:
    blocks: list[Block] = field(default_factory=list)
    source: str = ""
    warnings: list[str] = field(default_factory=list)
    skipped_toc: int = 0
    skipped: list[str] = field(default_factory=list)
