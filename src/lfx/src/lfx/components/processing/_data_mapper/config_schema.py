"""Pydantic models for the DataMapperComponent mapping-config JSON."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


SchemaSource = Literal["autodetect", "sample", "jsonschema"]
FieldType = Literal["str", "int", "float", "bool", "list", "dict", "date", "datetime"]
TransformType = Literal["direct", "static", "variable", "template", "expression", "array"]


class FieldDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: FieldType = "str"
    required: bool = False


class InputSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fields: list[FieldDef] = Field(default_factory=list)


class JoinKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    driver_field: str
    lookup_field: str


class JoinDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    on: list[JoinKey] = Field(min_length=1)


class InputDef(BaseModel):
    # `input_schema` is exposed on the wire as `schema` for backwards compatibility;
    # the Python attribute is renamed to avoid shadowing `BaseModel.schema()`.
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    alias: str
    schema_source: SchemaSource = "autodetect"
    input_schema: InputSchema = Field(default_factory=InputSchema, alias="schema")
    sample: dict[str, Any] | list[Any] | None = None
    jsonschema: dict[str, Any] | None = None
    join: JoinDef | None = None


class DestFieldDef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    type: FieldType = "str"
    required: bool = False
    default: Any = None


class SourceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: str
    field: str


class MappingEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    destination: str
    transform: TransformType
    sources: list[SourceRef] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class MapperConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    driver_index: int = 0
    inputs: list[InputDef] = Field(min_length=1)
    destination_schema: list[DestFieldDef] = Field(min_length=1)
    mappings: list[MappingEntry] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_graph(self) -> MapperConfig:
        # driver_index in range
        if not 0 <= self.driver_index < len(self.inputs):
            msg = f"driver_index {self.driver_index} out of range for {len(self.inputs)} inputs"
            raise ValueError(msg)

        # unique aliases
        aliases = [i.alias for i in self.inputs]
        if len(set(aliases)) != len(aliases):
            msg = f"duplicate input aliases: {aliases}"
            raise ValueError(msg)

        # driver has no join; non-driver inputs require join
        for idx, inp in enumerate(self.inputs):
            if idx == self.driver_index:
                if inp.join is not None:
                    msg = f"driver input '{inp.alias}' must not declare a join"
                    raise ValueError(msg)
            elif inp.join is None:
                msg = f"non-driver input '{inp.alias}' must declare a join.on"
                raise ValueError(msg)

        # mappings reference real destinations and real input aliases
        dest_names = {d.name for d in self.destination_schema}
        for m in self.mappings:
            if m.destination not in dest_names:
                msg = f"mapping references unknown destination field '{m.destination}'"
                raise ValueError(msg)
            for src in m.sources:
                if src.input not in aliases:
                    msg = f"mapping source references unknown input '{src.input}'"
                    raise ValueError(msg)

        # every required destination must have a mapping
        mapped = {m.destination for m in self.mappings}
        for d in self.destination_schema:
            if d.required and d.name not in mapped:
                msg = f"required destination field '{d.name}' has no mapping"
                raise ValueError(msg)

        return self
