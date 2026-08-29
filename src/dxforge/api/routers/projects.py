from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from dxforge.api.schemas import ProjectCreate, ProjectOut, VersionOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Project, Version

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectOut)
def create_project(
    body: ProjectCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Project:
    project = Project(tenant_id=context.tenant.id, name=body.name)
    context.session.add(project)
    context.session.commit()
    context.session.refresh(project)
    return project


@router.get("", response_model=list[ProjectOut])
def list_projects(
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> list[Project]:
    return list(
        context.session.execute(select(Project).order_by(Project.created_at)).scalars().all()
    )


@router.get("/{project_id}/versions", response_model=list[VersionOut])
def list_project_versions(
    project_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> list[Version]:
    if context.session.get(Project, project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    return list(
        context.session.execute(
            select(Version)
            .where(Version.project_id == project_id)
            .order_by(Version.version_number.desc())
        ).scalars().all()
    )
