from datetime import datetime
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TenantCreate(BaseModel):
    name: str


class TenantCreated(BaseModel):
    id: UUID
    name: str
    api_key: str


class FunctionCreate(BaseModel):
    name: str
    description: str | None = None


class FunctionOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class VersionOut(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    id: UUID
    version_number: int
    status: str
    created_at: datetime
