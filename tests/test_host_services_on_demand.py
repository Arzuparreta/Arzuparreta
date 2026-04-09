from __future__ import annotations

from query.host_services_on_demand import (
    _candidate_units,
    _normalize_unit_name,
    _parse_busctl_object_line,
    _parse_busctl_string_value,
)


def test_parse_busctl_object_line() -> None:
    assert (
        _parse_busctl_object_line('o "/org/freedesktop/systemd1/unit/dbus_2dbroker_2eservice"\n')
        == "/org/freedesktop/systemd1/unit/dbus_2dbroker_2eservice"
    )
    assert _parse_busctl_object_line("") is None
    assert _parse_busctl_object_line('no object here\n') is None


def test_parse_busctl_string_value() -> None:
    assert _parse_busctl_string_value('s "active"\n') == "active"
    assert _parse_busctl_string_value("") is None


def test_normalize_unit_name() -> None:
    assert _normalize_unit_name("nginx") == "nginx.service"
    assert _normalize_unit_name("nginx.service") == "nginx.service"
    assert _normalize_unit_name("foo.mount") == "foo.mount"


def test_candidate_units_samba_no_bare_duplicate() -> None:
    assert _candidate_units("samba", "Is my samba service working?") == [
        "samba.service",
        "smbd.service",
        "nmbd.service",
    ]
