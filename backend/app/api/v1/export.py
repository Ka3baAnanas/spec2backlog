from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.v1.projects import get_project
from app.core.db import get_db
from app.core.events import emit
from app.modules.export.azure_devops import export_azure_devops
from app.modules.export.csv import to_csv
from app.modules.export.excel import to_xlsx
from app.modules.export.jira import export_jira
from app.modules.export.traceability import backlog_rows, matrix

router = APIRouter(prefix="/api/v1", tags=["export"])


@router.get("/projects/{project_id}/coverage")
def get_coverage(project_id: str, db: Session = Depends(get_db)):
    project = get_project(db, project_id)
    return matrix(db, project)


@router.get("/projects/{project_id}/export")
def export_backlog(
    project_id: str,
    export_format: str = Query("xlsx", alias="format"),
    db: Session = Depends(get_db),
):
    project = get_project(db, project_id)
    fmt = export_format.lower()
    rows = backlog_rows(db, project)
    emit(project_id, "export", "stage_start", f"Preparing {fmt} export", {"rows": len(rows)})

    if fmt == "xlsx":
        content = to_xlsx(rows)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "backlog.xlsx"
    elif fmt == "csv":
        content = to_csv(rows)
        media_type = "text/csv; charset=utf-8"
        filename = "backlog.csv"
    elif fmt == "jira":
        try:
            export_jira(rows)
        except NotImplementedError as exc:
            raise HTTPException(501, str(exc)) from exc
        raise HTTPException(501, "Jira export is not implemented yet")
    elif fmt == "azure":
        try:
            export_azure_devops(rows)
        except NotImplementedError as exc:
            raise HTTPException(501, str(exc)) from exc
        raise HTTPException(501, "Azure DevOps export is not implemented yet")
    else:
        raise HTTPException(400, "invalid format; expected xlsx, csv, jira or azure")

    project.status = "exported"
    db.commit()
    emit(project_id, "export", "stage_end", f"Exported {len(rows)} item(s)",
         {"rows": len(rows), "format": fmt})
    return Response(
        content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
