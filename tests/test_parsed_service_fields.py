from __future__ import annotations

from ingestor.parsed_service_fields import docker_service_key_label, journal_service_key_label


def test_journal_prefers_systemd_unit() -> None:
    sk, sl = journal_service_key_label({"_SYSTEMD_UNIT": "nginx.service", "SYSLOG_IDENTIFIER": "foo"})
    assert sk == "unit:nginx.service"
    assert sl == "nginx.service"


def test_journal_syslog_id_when_no_unit() -> None:
    sk, sl = journal_service_key_label({"SYSLOG_IDENTIFIER": "sshd"})
    assert sk == "syslog_id:sshd"
    assert sl == "sshd"


def test_journal_comm_fallback() -> None:
    sk, sl = journal_service_key_label({"_COMM": "ollama"})
    assert sk == "comm:ollama"
    assert sl == "ollama"


def test_journal_omits_when_no_identity() -> None:
    assert journal_service_key_label({}) == (None, None)
    assert journal_service_key_label({"MESSAGE": "x"}) == (None, None)


def test_docker_named() -> None:
    sk, sl = docker_service_key_label("myapp", "deadbeef" * 8)
    assert sk == "docker:myapp"
    assert sl == "myapp"


def test_docker_short_id() -> None:
    full = "a" * 64
    sk, sl = docker_service_key_label(None, full)
    assert sk == "docker:aaaaaaaaaaaa"
    assert sl == "aaaaaaaaaaaa"
