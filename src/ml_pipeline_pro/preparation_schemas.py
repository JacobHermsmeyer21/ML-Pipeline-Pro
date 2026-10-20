"""Explicit, reviewable settings for bounded raw classification CSV preparation."""

from typing import Annotated, Literal

from pydantic import Field, field_validator, model_validator

from ml_pipeline_pro.schemas import Name, RequestModel, Sha256

Column = Annotated[str, Field(min_length=1, max_length=128)]
BoundedValue = Annotated[float, Field(ge=-1e12, le=1e12, allow_inf_nan=False)]


class ColumnEncoding(RequestModel):
    treatment: Literal["auto", "numeric", "one_hot", "mapping", "exclude"] = "auto"
    mapping: dict[Column, BoundedValue] = Field(default_factory=dict, max_length=128)
    unknown_value: BoundedValue = 0

    @model_validator(mode="after")
    def mapping_is_explicit(self):
        if self.treatment != "mapping" and self.mapping:
            raise ValueError("Numeric category mappings require mapping treatment")
        return self


class PreparationSettings(RequestModel):
    name: Name
    version: Name
    target_column: Column
    columns: dict[Column, ColumnEncoding] = Field(default_factory=dict, max_length=128)
    label_mapping: dict[Column, Annotated[int, Field(ge=0, le=63)]] = Field(
        default_factory=dict, max_length=64
    )
    train_percent: int = Field(default=70, ge=1, le=98)
    validation_percent: int = Field(default=15, ge=1, le=98)
    test_percent: int = Field(default=15, ge=1, le=98)
    seed: int = Field(default=42, ge=0, le=2**32 - 1)
    split_column: Column | None = None
    impute_missing: bool = False
    reviewed_sha256: Sha256 | None = None

    @field_validator("columns", "label_mapping")
    @classmethod
    def bounded_keys(cls, value):
        if any(len(key.encode("utf-8")) > 128 for key in value):
            raise ValueError("Column and category names exceed the byte limit")
        return value

    @model_validator(mode="after")
    def consistent(self):
        if self.train_percent + self.validation_percent + self.test_percent != 100:
            raise ValueError("Training, validation and test percentages must sum to 100")
        if self.split_column == self.target_column:
            raise ValueError("Target and split columns must differ")
        return self
