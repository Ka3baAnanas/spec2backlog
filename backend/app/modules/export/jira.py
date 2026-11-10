def export_jira(rows: list[dict], base_url: str = "", token: str = ""):
    raise NotImplementedError(
        "Jira export is not implemented yet (HTTP 501). "
        "Planned: POST /rest/api/3/issue/bulk, epics -> stories -> tests, store created keys."
    )
