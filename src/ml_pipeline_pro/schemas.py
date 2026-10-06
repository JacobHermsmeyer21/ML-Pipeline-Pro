"""Request and persistence schemas for classification experiment tracking."""

import re
from pathlib import PurePosixPath
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ml_pipeline_pro.repositories import Record

ProjectId = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")]
Name = Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9_-]+$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DatasetDefinition(RequestModel):
    name: Name
    version: Name
    uri: str = Field(min_length=1, max_length=256)
    feature_columns: list[Name] = Field(min_length=1, max_length=128)
    target_column: Name = "target"
    split_column: Name = "split"

    @field_validator("uri")
    @classmethod
    def local_csv_reference(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not re.fullmatch(r"[a-zA-Z0-9_./-]+", value)
            or path.is_absolute()
            or ".." in path.parts
            or path.suffix != ".csv"
        ):
            raise ValueError("uri must be a relative .csv path under the configured dataset root")
        return str(path)

    @model_validator(mode="after")
    def distinct_columns(self):
        columns = [*self.feature_columns, self.target_column, self.split_column]
        if len(set(columns)) != len(columns):
            raise ValueError("Feature, target, and split columns must be distinct")
        return self


class DatasetCreate(DatasetDefinition):
    expected_sha256: Sha256 | None = None


class DatasetRecord(Record, DatasetDefinition):
    sha256: Sha256
    num_classes: int = Field(ge=2, le=64)
    row_counts: dict[Literal["train", "validation", "test"], int]


class ModelCreate(RequestModel):
    name: Name
    framework: Literal["pytorch"] = "pytorch"
    task: Literal["classification"] = "classification"
    architecture: Literal["mlp"] = "mlp"


class ModelRecord(Record, ModelCreate):
    pass


ItemT = TypeVar("ItemT", bound=BaseModel)


class Page(BaseModel, Generic[ItemT]):
    items: list[ItemT]
    limit: int
    offset: int
