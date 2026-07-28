from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import AliasChoices, AnyUrl, BaseModel, Field, HttpUrl, field_validator


class OAIPMHAuthenticationConfig(BaseModel):
    username_env: str | None = None
    password_env: str | None = None


class SourceConfig(BaseModel):
    plugin: Literal["oai-pmh"]

    base_url: HttpUrl
    metadata_prefix: str = "oai_dc"
    set_spec: str | None = None

    mode: Literal["identifiers", "records"] = "records"

    deleted_record_policy: Literal["include", "ignore", "tombstone"] = "ignore"

    timeout_seconds: float = Field(default=60, gt=0)

    verify_ssl: bool = True
    user_agent: str = "ORCHESTRATOR-ACP-Harvester/0.1"

    authentication: OAIPMHAuthenticationConfig | None = None


class HarvestingConfig(BaseModel):
    queue_name: str = "orchestrator-provider"

    incremental: bool = True
    overlap_days: int = Field(default=1, ge=0, le=30)

    batch_size: int = Field(default=500, ge=1, le=10_000)

    maximum_records: int | None = Field(default=None, ge=1)

    store_raw_xml: bool = False
    validate_metadata_format: bool = True


class PipelineTransformerConfig(BaseModel):
    name: str
    service_url: HttpUrl


class PipelineConfig(BaseModel):
    metadata_type: str
    transformer: PipelineTransformerConfig


class TransformedMetadata(BaseModel):
    transformer_url: HttpUrl | None = Field(None, alias="transformer-url")
    name: str
    dir: str | None = None
    generate_file: bool | None = Field(None, alias="generate-file")
    restricted: bool | None = None


class ProcessedMetadata(BaseModel):
    hook_name: str = Field(..., alias="hook-name")
    process_function: str = Field(..., alias="process-function")
    service_url: HttpUrl | None = Field(None, alias="service-url")
    name: str
    dir: str | None = None


class Metadata(BaseModel):
    specification: list[str] | None = None
    transformed_metadata: list[TransformedMetadata] | None = Field(None, alias="transformed-metadata")
    processed_metadata: list[ProcessedMetadata] | None = Field(None, alias="processed-metadata")


class Input(BaseModel):
    from_target_name: str | None = Field(default=None, alias="from-target-name")


class StorageType(StrEnum):
    FILE_SYSTEM = "FILE_SYSTEM"
    S3 = "s3"


class Target(BaseModel):
    name: str | None = None
    repo_pid: str | None = Field(default=None, alias="repo-pid")
    repo_name: str | None = Field(default=None, alias="repo-name")
    repo_display_name: str | None = Field(default=None, alias="repo-display-name")
    bridge_plugin_name: str = Field(
        ...,
        alias="bridge-plugin-name",
        validation_alias=AliasChoices("bridge-plugin-name", "bridge_plugin_name"),
    )
    base_url: AnyUrl | None = Field(default=None, alias="base-url")
    target_url: AnyUrl | None = Field(default=None, alias="target-url")
    target_url_params: str | None = Field(default=None, alias="target-url-params")
    payload: dict[str, Any] | None = None
    username: str | None = None
    password: str | None = None
    metadata: Metadata | None = None
    storage_type: StorageType | None = Field(default=StorageType.FILE_SYSTEM, alias="storage-type")
    initial_release_version: str | None = Field(default=None, alias="initial-release-version")
    input: Input | None = None

    @field_validator("target_url", "base_url", mode="before")
    @classmethod
    def validate_urls(cls, value: str | None, info):
        if value:
            parsed_url = urlparse(str(value))
            if info.field_name in ["target_url", "base_url"] and parsed_url.scheme not in [
                "https",
                "http",
                "file",
                "mailto",
                "s3",
            ]:
                raise ValueError(f"Invalid {info.field_name} URL: {value}")
        return value


class NotificationItem(BaseModel):
    type: str
    conf: str


class FileConversion(BaseModel):
    id: str
    origin_type: str = Field(..., alias="origin-type")
    target_type: str = Field(..., alias="target-type")
    conversion_url: HttpUrl = Field(..., alias="conversion-url")
    notification: list[NotificationItem] | None = None


class Enrichment(BaseModel):
    id: str
    name: str
    service_url: HttpUrl = Field(..., alias="service-url")
    result_url: HttpUrl = Field(..., alias="result-url")
    notification: list[NotificationItem] | None = None
    permission: str | None = None


class RepositoryAssistantConfig(BaseModel):
    name: str | None = None
    assistant_config_name: str = Field(
        ...,
        alias="assistant-config-name",
        validation_alias=AliasChoices("assistant-config-name", "name"),
    )
    description: str | None = None
    app_name: str = Field(
        ...,
        alias="app-name",
        validation_alias=AliasChoices("app-name", "app_name"),
    )
    app_config_url: HttpUrl | None = Field(None, alias="app-config-url")
    source: SourceConfig | None = None
    harvesting: HarvestingConfig | None = None
    pipeline: PipelineConfig | None = None
    targets: list[Target]
    file_conversions: list[FileConversion] | None = Field(None, alias="file-conversions")
    enrichments: list[Enrichment] | None = None


# Backward-compatible alias used across ACA code.
RepoAssistantDataModel = RepositoryAssistantConfig
