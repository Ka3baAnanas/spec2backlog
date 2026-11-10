def impacted_items(project_id: str, changed_sections: list[str]) -> list[dict]:
    raise NotImplementedError(
        "Spec v2 impact analysis is not implemented yet (HTTP 501). "
        "Planned: upload v2 -> diff sections -> list impacted backlog items."
    )
