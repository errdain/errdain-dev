from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SchemaFieldType = Literal[
    "string",
    "integer",
    "number",
    "boolean",
    "date",
    "datetime",
    "uuid",
    "email",
    "phone",
    "address",
    "json",
]


class SchemaRelationship(BaseModel):
    """A directed foreign-key relationship inside one dataset schema."""

    model_config = ConfigDict(extra="forbid")

    field: str
    references_table: str
    references_field: str
    nullable: bool = False


class SchemaField(BaseModel):
    """Canonical field definition shared by the API, CLI, and web UI."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    type: SchemaFieldType
    description: str | None = None
    nullable: bool = False
    unique: bool = False
    semantic_type: str | None = None
    enum: list[str] = Field(default_factory=list)
    minimum: float | None = None
    maximum: float | None = None
    pattern: str | None = None
    distribution: Literal["uniform", "normal", "weighted", "sequential"] | None = None
    relationship: SchemaRelationship | None = None

    @model_validator(mode="after")
    def validate_constraints(self) -> "SchemaField":
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("minimum must not exceed maximum")
        if self.enum and self.type not in {"string", "integer", "number"}:
            raise ValueError("enum is supported only for string and numeric fields")
        if self.pattern and self.type != "string":
            raise ValueError("pattern is supported only for string fields")
        return self


class SchemaTable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    description: str | None = None
    primary_key: str
    fields: list[SchemaField] = Field(min_length=1)
    default_rows: int = Field(default=100, ge=1, le=1_000_000)

    @model_validator(mode="after")
    def validate_fields(self) -> "SchemaTable":
        names = [field.name for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError(f"table {self.name} contains duplicate field names")
        if self.primary_key not in names:
            raise ValueError(f"primary_key {self.primary_key} is not a field in table {self.name}")
        primary = next(field for field in self.fields if field.name == self.primary_key)
        if primary.nullable:
            raise ValueError("primary_key field cannot be nullable")
        return self


class CustomDatasetSchema(BaseModel):
    """Versioned internal schema contract used by every Errdain access channel."""

    model_config = ConfigDict(extra="forbid")

    schema_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{2,79}$")
    name: str = Field(min_length=3, max_length=120)
    version: str = Field(default="1.0.0", pattern=r"^\d+\.\d+\.\d+$")
    description: str | None = None
    source_format: Literal["json_schema", "csv_definition", "sql_ddl", "ui"]
    tables: list[SchemaTable] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_dataset(self) -> "CustomDatasetSchema":
        tables = {table.name: table for table in self.tables}
        if len(tables) != len(self.tables):
            raise ValueError("dataset schema contains duplicate table names")
        for table in self.tables:
            for field in table.fields:
                relationship = field.relationship
                if relationship is None:
                    continue
                if relationship.field != field.name:
                    raise ValueError(
                        f"relationship field {relationship.field} must match containing field {field.name}"
                    )
                target = tables.get(relationship.references_table)
                if target is None:
                    raise ValueError(
                        f"relationship target table does not exist: {relationship.references_table}"
                    )
                target_fields = {item.name for item in target.fields}
                if relationship.references_field not in target_fields:
                    raise ValueError(
                        "relationship target field does not exist: "
                        f"{relationship.references_table}.{relationship.references_field}"
                    )
        return self

    def compatibility_fingerprint(self) -> tuple:
        """Return a stable structural signature suitable for compatibility checks."""

        return tuple(
            (
                table.name,
                table.primary_key,
                tuple(
                    (
                        field.name,
                        field.type,
                        field.nullable,
                        field.unique,
                        tuple(field.enum),
                        field.relationship.references_table if field.relationship else None,
                        field.relationship.references_field if field.relationship else None,
                    )
                    for field in table.fields
                ),
            )
            for table in self.tables
        )
