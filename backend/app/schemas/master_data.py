"""Import response contracts shared by the three rule-only datasets."""
from typing import Literal
from pydantic import BaseModel, Field


class ImportRowError(BaseModel):
    row: int | None = None
    reason: str


class MasterImportResponse(BaseModel):
    import_id: int
    dataset: str
    status: Literal['completed', 'partial', 'rejected', 'empty']
    inserted: int
    updated: int
    skipped: int
    rejected: int
    errors: list[ImportRowError] = Field(default_factory=list)
    checks: dict | None = None


class DatasetImportStatus(BaseModel):
    dataset: str
    rows_loaded: int
    last_imported_at: str | None
    last_import_status: str | None
    last_successful_imported_at: str | None
