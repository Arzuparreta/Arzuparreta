from query.journalctl_on_demand import (
    REBOOT_JOURNAL_GREP,
    journalctl_since_argument,
    list_boots_row_count,
)


def test_journalctl_since_argument_relative() -> None:
    assert journalctl_since_argument("10d") == "-10d"
    assert journalctl_since_argument("1h") == "-1h"
    assert journalctl_since_argument("30m") == "-30m"


def test_reboot_journal_grep_pattern_non_empty() -> None:
    assert "reboot" in REBOOT_JOURNAL_GREP
    assert "kernel:" in REBOOT_JOURNAL_GREP


def test_list_boots_row_count_parses_table() -> None:
    sample = """IDX BOOT ID                          FIRST ENTRY                  LAST ENTRY
  0 287444931bcf4cf98610dd1ea575223f Sat 2026-04-04 11:06:27 CEST Sun 2026-04-05 01:19:41 CEST
"""
    assert list_boots_row_count(sample) == 1

    two = sample + (
        " -1 a87444931bcf4cf98610dd1ea575223e "
        "Fri 2026-04-01 08:00:00 UTC Sat 2026-04-04 10:00:00 UTC\n"
    )
    assert list_boots_row_count(two) == 2
