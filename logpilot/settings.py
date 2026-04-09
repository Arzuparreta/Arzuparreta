from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(
        default="postgresql+asyncpg://logpilot:changeme@localhost:5432/logpilot",
    )
    ollama_base_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "nomic-embed-text"
    chat_model: str = "llama3"
    docker_log_root: str = "/var/lib/docker/containers"
    docker_socket_path: str = Field(
        default="/var/run/docker.sock",
        description="Unix socket for read-only Docker Engine API (container name enrichment)",
    )
    docker_enrich_container_names: bool = Field(
        default=True,
        description="If socket exists, map container IDs to Names via GET /containers/json",
    )
    docker_query_on_demand: bool = Field(
        default=True,
        description=(
            "When true and intent requests it, `logpilot ask` may call read-only Docker Engine GET APIs "
            "(containers/json, containers/{id}/json) for live RestartCount/state — requires mounted socket"
        ),
    )
    disk_usage_query_on_demand: bool = Field(
        default=True,
        description=(
            "When true and intent requests it, `logpilot ask` may run the allowlisted read-only `disk_usage` tool "
            "(`df -B1 -P`) for disk-space questions"
        ),
    )
    cpu_thermal_query_on_demand: bool = Field(
        default=True,
        description=(
            "When true and intent requests it, `logpilot ask` may run the read-only `cpu_thermal` probe "
            "(`/proc/loadavg`, sysfs thermal zones)"
        ),
    )
    gpu_status_query_on_demand: bool = Field(
        default=True,
        description=(
            "When true and intent requests it, `logpilot ask` may run the read-only `gpu_status` probe "
            "(fixed `nvidia-smi` CSV and/or `rocm-smi` text — requires those binaries in the container/PATH)"
        ),
    )
    host_services_query_on_demand: bool = Field(
        default=True,
        description=(
            "When true, `logpilot ask` may use read-only `systemctl` snapshots for native service-status questions "
            "(e.g. samba/sshd/nginx)."
        ),
    )
    text_log_ingest: bool = True
    text_log_paths: str = Field(
        default="",
        description="Comma-separated paths or globs for host text logs; empty uses built-in defaults",
    )
    text_log_include_journal_duplicate_paths: bool = Field(
        default=False,
        description="When journal ingest is on, still ingest /var/log/syslog and /var/log/messages "
        "(not recommended — duplicates journal on typical rsyslog setups)",
    )
    journal_ingest: bool = Field(
        default=False,
        description="Follow systemd journal via journalctl subprocess (see README for mounts)",
    )
    journal_directory: str = Field(
        default="",
        description="If set, passed as journalctl --directory (e.g. mounted host /var/log/journal)",
    )
    journal_machine_id: str = Field(
        default="",
        description="Override PK for journal_cursors (default: read /etc/machine-id or 'default')",
    )
    journal_flush_batch_size: int = Field(
        default=32,
        ge=1,
        le=500,
        description="Logs per DB transaction when flushing journal lines",
    )
    journal_query_on_demand: bool = Field(
        default=True,
        description="For host-level questions, run journalctl when embedded journal rows are zero but journal files are mounted",
    )
    embed_batch_size: int = 32
    embed_poll_interval_s: float = 2.0
    ingest_poll_interval_s: float = 1.0
    logpilot_api_host: str = "0.0.0.0"
    logpilot_api_port: int = 8080
    logpilot_enable_api: bool = True
    log_level: str = "INFO"
    use_embedding_fallback: bool = False
    st_embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"

    query_agent_max_steps: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max planner steps when POST /query has agent=true",
    )
    query_agent_max_total_rows: int = Field(
        default=200,
        ge=1,
        le=2000,
        description="Max merged log rows across agent retrieval steps",
    )
    query_agent_timeout_s: float = Field(
        default=120.0,
        ge=5.0,
        le=3600.0,
        description="Wall-clock budget for the bounded retrieval planner",
    )
    query_answer_timeout_s: float = Field(
        default=300.0,
        ge=0.0,
        le=3600.0,
        description="Timeout for final answer LLM (0 = use client default)",
    )
    query_context_redact_regex: str = Field(
        default="",
        description="If non-empty, regex applied to log context before the answer LLM (optional PII strip)",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
