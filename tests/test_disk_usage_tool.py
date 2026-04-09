"""Golden `df` parsing and disk_usage tool contracts."""

from __future__ import annotations

import pytest

from tools.disk_usage import DiskUsageTool, _parse_df_stdout
from tools.registry import ToolRegistry, default_tool_registry


_GOLDEN_DF = """Filesystem                         1B-blocks          Used     Available Use% Mounted on
udev                             1007187968             0    1007187968   0% /dev
/dev/sda1                       500000000000  250000000000  250000000000  50% /
/dev/sdb1                      1000000000000             0  1000000000000   0% /mnt/data
"""


def test_parse_df_stdout_golden() -> None:
    mounts = _parse_df_stdout(_GOLDEN_DF, mount_filter=None)
    assert len(mounts) == 3
    root = next(m for m in mounts if m.mountpoint == "/")
    assert root.source == "/dev/sda1"
    assert root.size_b == 500_000_000_000
    assert root.used_b == 250_000_000_000
    assert root.avail_b == 250_000_000_000
    assert root.use_pct == 50.0


def test_parse_df_mount_filter() -> None:
    mounts = _parse_df_stdout(_GOLDEN_DF, mount_filter={"/"})
    assert len(mounts) == 1
    assert mounts[0].mountpoint == "/"


@pytest.mark.asyncio
async def test_registry_unknown_tool() -> None:
    reg = default_tool_registry()
    run = await reg.invoke("no_such_tool", {}, timeout_s=1.0)
    assert not run.evidence.ok
    assert run.evidence.failure is not None
    assert run.evidence.failure.code == "unknown_tool"


@pytest.mark.asyncio
async def test_registry_disk_usage_validation() -> None:
    reg = ToolRegistry()
    reg.register(DiskUsageTool())
    run = await reg.invoke("disk_usage", {"mount_points": "not-a-list"}, timeout_s=1.0)
    assert not run.evidence.ok
    assert run.evidence.failure is not None
    assert run.evidence.failure.code == "invalid_arguments"
