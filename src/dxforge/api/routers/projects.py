from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from dxforge.api.schemas import BuildRequest, ProjectCreate, ProjectOut, VersionOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.build.pipeline import run_build
from dxforge.build.sources.git_source import GitSource
from dxforge.build.sources.zip_source import ZipSource
from dxforge.db.models import Project, Version

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", status_code=201, response_model=ProjectOut)
def create_project(
    body: ProjectCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Project:
    project = Project(
        tenant_id=context.tenant.id, name=body.name, build_tool=body.build_tool
    )
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


@router.post("/{project_id}/build", status_code=201, response_model=VersionOut)
def build_project(
    project_id: UUID,
    body: BuildRequest,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Version:
    project = context.session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project not found")
    if (body.file_id is None) == (body.repo_url is None):
        raise HTTPException(
            status_code=400, detail="exactly one of file_id or repo_url is required"
        )
    if body.file_id is not None:
        source = ZipSource(body.file_id)
    else:
        source = GitSource(body.repo_url or "", context.tenant.id, body.credential_id)
    try:
        return run_build(
            tenant_id=context.tenant.id,
            project_id=project_id,
            source=source,
            runtime=body.runtime,
            build_tool=body.build_tool or project.build_tool,
            build_command=body.build_command,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
