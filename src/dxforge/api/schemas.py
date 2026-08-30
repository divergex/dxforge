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
    command: list[str]
    description: str | None = None


class FunctionOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    project_id: UUID
    version_id: UUID
    command: list[str]
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


class ScheduleCreate(BaseModel):
    function_id: UUID
    version_id: UUID | None = None
    rule: str
    enabled: bool = True
    executor_backend: str = "docker"


class ScheduleOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    function_id: UUID
    version_id: UUID | None
    rule: str
    enabled: bool
    executor_backend: str
    last_fired_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExecutionOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    schedule_id: UUID | None
    function_id: UUID
    version_id: UUID
    status: str
    executor_backend: str
    exit_code: int | None
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None


class ExecutionLogsOut(BaseModel):
    execution_id: UUID
    stdout: str
    stderr: str
