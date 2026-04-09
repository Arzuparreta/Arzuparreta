"""Registry of allowlisted read-only tools."""

from __future__ import annotations

import logging
from typing import Any

from tools.contracts import ToolFailure, ToolEvidence, ToolRun
from tools.cpu_thermal import CpuThermalTool
from tools.disk_usage import DiskUsageTool
from tools.gpu_status import GpuStatusTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    def __init__(self) -> None:
        self._by_name: dict[str, Any] = {}

    def register(self, tool: Any) -> None:
        self._by_name[tool.name] = tool

    def get(self, name: str) -> Any | None:
        return self._by_name.get(name)

    async def invoke(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout_s: float,
    ) -> ToolRun:
        tool = self._by_name.get(name)
        if tool is None:
            return ToolRun(
                evidence=ToolEvidence(
                    tool_name=name,
                    input_fingerprint="",
                    ok=False,
                    duration_ms=0.0,
                    output_bytes=0,
                    failure=ToolFailure(code="unknown_tool", message=f"Unknown tool {name!r}"),
                ),
                output=None,
            )
        try:
            params = tool.input_model.model_validate(arguments)
        except Exception as exc:
            logger.info("tool %s arg validation failed: %s", name, exc)
            return ToolRun(
                evidence=ToolEvidence(
                    tool_name=name,
                    input_fingerprint="",
                    ok=False,
                    duration_ms=0.0,
                    output_bytes=0,
                    failure=ToolFailure(
                        code="invalid_arguments",
                        message=str(exc),
                        details={"arguments_keys": sorted(arguments.keys())},
                    ),
                ),
                output=None,
            )
        return await tool.run(params, timeout_s=timeout_s)


def default_tool_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(DiskUsageTool())
    reg.register(CpuThermalTool())
    reg.register(GpuStatusTool())
    return reg
