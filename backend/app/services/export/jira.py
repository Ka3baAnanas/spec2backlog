"""Jira Cloud export. Epics -> Stories (parent=epic) -> Tests (as Sub-task or Xray/Zephyr test).
TODO: POST /rest/api/3/issue/bulk with ADF description; map status/priority; store created keys."""


def export_jira(rows: list[dict], base_url: str, token: str):
    raise NotImplementedError("Jira export: implement after Excel export is validated")
