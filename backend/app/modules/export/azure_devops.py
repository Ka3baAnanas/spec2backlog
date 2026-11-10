def export_azure_devops(rows: list[dict], org_url: str = "", pat: str = ""):
    raise NotImplementedError(
        "Azure DevOps export is not implemented yet (HTTP 501). "
        "Planned: POST {org}/{project}/_apis/wit/workitems/$Epic?api-version=7.1 (JSON Patch)."
    )
