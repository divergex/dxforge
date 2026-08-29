from datetime import datetime
from typing import ClassVar, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantCreate(BaseModel):
    name: str


class TenantCreated(BaseModel):
    id: UUID
    name: str
    api_key: str


class ProjectCreate(BaseModel):
    name: str
    build_tool: Literal["none", "make", "docker"] = "none"


class ProjectOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    build_tool: str
    created_at: datetime


class UploadOut(BaseModel):
    file_id: str


class CredentialCreate(BaseModel):
    name: str
    private_key: str


class CredentialOut(BaseModel):
    id: UUID
    name: str


class BuildRequest(BaseModel):
    file_id: str | None = None
    repo_url: str | None = None
    credential_id: UUID | None = None
    runtime: str | None = None
    build_tool: Literal["none", "make", "docker"] | None = None
    build_command: str | None = None


class FunctionCreate(BaseModel):
    name: str
    project_id: UUID
    version_id: UUID
    handler: str
    description: str | None = None


class FunctionOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    project_id: UUID
    version_id: UUID
    handler: str
    created_at: datetime
    updated_at: datetime


class VersionOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    runtime: str
    build_tool: str
    status: str
    created_at: datetime
