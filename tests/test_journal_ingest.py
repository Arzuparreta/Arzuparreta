from __future__ import annotations

from pathlib import Path

import pytest

from ingestor.journal import (
    journal_plaintext_omit_paths,
    log_from_journal_line,
    machine_id_for_journal,
    source_name_from_journal_entry,
)
from ingestor.plain_text import _expand_log_paths
from logpilot.settings import Settings


def test_source_name_prefers_systemd_unit() -> None:
    assert (
        source_name_from_journal_entry({"_SYSTEMD_UNIT": "nginx.service"})
        == "journal:nginx.service"
    )


def test_log_from_journal_line_roundtrip() -> None:
    line = (
        '{"MESSAGE":"hello","__CURSOR__":"abc","_SYSTEMD_UNIT":"sshd.service",'
        '"PRIORITY":"3","__REALTIME_TIMESTAMP":"1700000000000000"}'
    )
    out = log_from_journal_line(line)
    assert out is not None
    log, cur = out
    assert cur == "abc"
    assert log.raw == "hello"
    assert log.source == "journal:sshd.service"
    assert log.level == "err"
    assert log.parsed.get("systemd_unit") == "sshd.service"
    assert log.parsed.get("service_key") == "unit:sshd.service"
    assert log.parsed.get("service_label") == "sshd.service"


def test_log_from_journal_line_no_service_key_without_identity() -> None:
    line = '{"MESSAGE":"only message","__CURSOR__":"c1","__REALTIME_TIMESTAMP":"1700000000000000"}'
    out = log_from_journal_line(line)
    assert out is not None
    log, _ = out
    assert "service_key" not in log.parsed
    assert "service_label" not in log.parsed


def test_journal_plaintext_omit_paths() -> None:
    assert journal_plaintext_omit_paths(Settings(journal_ingest=False)) is None
    assert journal_plaintext_omit_paths(
        Settings(journal_ingest=True, text_log_include_journal_duplicate_paths=True)
    ) is None
    o = journal_plaintext_omit_paths(Settings(journal_ingest=True))
    assert o is not None
    assert "/var/log/syslog" in o


def test_machine_id_override() -> None:
    assert machine_id_for_journal(Settings(journal_machine_id="  myhost  ")) == "myhost"


def test_expand_log_paths_respects_omit(tmp_path: Path) -> None:
    a = tmp_path / "a.log"
    b = tmp_path / "b.log"
    a.write_text("1", encoding="utf-8")
    b.write_text("2", encoding="utf-8")
    cfg = f"{a},{b}"
    out = _expand_log_paths(cfg, omit_paths=frozenset({str(a.resolve())}))
    assert [p.resolve() for p in out] == [b.resolve()]


@pytest.mark.parametrize("bad", ["", "{not json}", '{"MESSAGE":"x"}'])  # missing __CURSOR__
def test_log_from_journal_line_rejects(bad: str) -> None:
    assert log_from_journal_line(bad) is None
