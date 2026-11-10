"""Azure DevOps export. Epic -> User Story -> Test Case via
POST {org}/{project}/_apis/wit/workitems/$Epic?api-version=7.1 (JSON Patch)."""


def export_azdo(rows: list[dict], org_url: str, pat: str):
    raise NotImplementedError("Azure DevOps export: implement after Excel export is validated")
