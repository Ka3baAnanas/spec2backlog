"""Spec document diffing (v2 impact analysis foundation)."""


def diff_sections(old_sections: list[dict], new_sections: list[dict]) -> dict:
    """Compare two section lists by number; returns added/removed/changed section numbers."""
    old_map = {section.get("number", ""): section for section in old_sections}
    new_map = {section.get("number", ""): section for section in new_sections}
    added = [number for number in new_map if number not in old_map]
    removed = [number for number in old_map if number not in new_map]
    changed = [
        number
        for number, section in new_map.items()
        if number in old_map and old_map[number].get("text", "") != section.get("text", "")
    ]
    return {"added": added, "removed": removed, "changed": changed}
