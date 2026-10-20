"""Review and provenance contracts for immutable dataset column selection."""

from pydantic import BaseModel, Field, field_validator

from ml_pipeline_pro.preparation_schemas import Column
from ml_pipeline_pro.schemas import Name, RequestModel, Sha256


class ColumnEdit(RequestModel):
    version: Name
    drop_columns: list[Column] = Field(min_length=1, max_length=128)
    source_sha256: Sha256

    @field_validator("drop_columns")
    @classmethod
    def distinct_columns(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Choose each omitted column only once")
        if any(len(name.encode()) > 128 for name in value):
            raise ValueError("Column names exceed the byte limit")
        return sorted(value)


class ColumnSave(ColumnEdit):
    reviewed_sha256: Sha256


class EditableColumn(BaseModel):
    name: Column
    output_columns: list[Name]


class DatasetColumns(BaseModel):
    dataset_id: str
    name: Name
    version: Name
    source_sha256: Sha256
    columns: list[EditableColumn]
    target_column: str
    split_column: str
    row_counts: dict[str, int]
    encoded_width: int


class ColumnPreview(BaseModel):
    source: DatasetColumns
    version: Name
    drop_columns: list[Column]
    kept_columns: list[EditableColumn]
    feature_columns: list[Name]
    encoded_width: int
    row_counts: dict[str, int]
    preview_sha256: Sha256
