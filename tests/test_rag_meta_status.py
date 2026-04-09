from __future__ import annotations

from query.rag import _deterministic_meta_answer


def test_deterministic_meta_answer_reports_probe_values() -> None:
    docker_extra = """
## Docker Engine — live read-only inspect (authoritative for container lifecycle)

| Name | Container ID | State | RestartCount | StartedAt | FinishedAt |
| --- | --- | --- | --- | --- | --- |
| app | abcdef123456 | running | 1 | now | never |
| db | fedcba654321 | exited | 0 | then | now |
""".strip()
    disk_extra = """
## Disk usage — read-only `df` (filesystems visible in this environment)

| Source | Mount | Use% | Used (B) | Size (B) | Avail (B) |
| --- | --- | --- | --- | --- | --- |
| `/dev/sda1` | `/` | 47% | 1 | 2 | 3 |
""".strip()
    cpu_extra = """
## CPU load and thermal — read-only (`cpu_thermal`)

- **Load average (1m / 5m / 15m):** 0.35 / 0.40 / 0.45
""".strip()
    answer = _deterministic_meta_answer(
        counts={"journal": 10, "docker": 20, "file": 30, "other": 40},
        docker_extra=docker_extra,
        disk_extra=disk_extra,
        cpu_thermal_extra=cpu_extra,
        gpu_extra="",
    )
    assert "47% used" in answer
    assert "0.35 / 0.40 / 0.45" in answer
    assert "1 running" in answer
    assert "1 exited" in answer

