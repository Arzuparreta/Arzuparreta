from logpilot.settings import Settings

from query.inventory import _answer_rules_block


def test_answer_rules_reboot_without_journal() -> None:
    s = Settings()
    block = _answer_rules_block(
        "How many times has my computer rebooted?",
        {"journal": 0, "docker": 100, "file": 0, "other": 0},
        s,
        reboot_journal_focus=True,
    )
    assert "unknown" in block.lower() or "cannot" in block.lower()
    assert "journal:" in block


def test_answer_rules_reboot_with_live_journalctl() -> None:
    s = Settings()
    block = _answer_rules_block(
        "How many times has my computer rebooted?",
        {"journal": 0, "docker": 100, "file": 0, "other": 0},
        s,
        journalctl_excerpt_len=8000,
        reboot_journal_focus=True,
    )
    assert "journalctl" in block.lower()
    assert "raw" in block.lower()


def test_answer_rules_reboot_with_list_boots() -> None:
    s = Settings()
    block = _answer_rules_block(
        "How many times has my computer rebooted?",
        {"journal": 0, "docker": 100, "file": 0, "other": 0},
        s,
        journalctl_excerpt_len=1200,
        journalctl_list_boots=True,
        reboot_journal_focus=True,
    )
    assert "list-boots" in block.lower()
    assert "max(0" in block


def test_answer_rules_meta_coverage_flag() -> None:
    s = Settings()
    block = _answer_rules_block(
        "coverage",
        {"journal": 0, "docker": 0, "file": 0, "other": 0},
        s,
        is_meta_coverage_question=True,
    )
    assert "coverage" in block.lower()
    assert "sample" in block.lower()
    assert "non-log" in block.lower() or "disk usage" in block.lower()


def test_answer_rules_docker_engine_table() -> None:
    s = Settings()
    block = _answer_rules_block(
        "restart count",
        {"journal": 0, "docker": 10, "file": 0, "other": 0},
        s,
        docker_engine_excerpt_len=5000,
    )
    assert "restartcount" in block.lower()
    assert "docker engine" in block.lower()
    assert "cumulative" in block.lower()


def test_answer_rules_disk_usage_probe() -> None:
    s = Settings()
    block = _answer_rules_block(
        "disk space",
        {"journal": 0, "docker": 0, "file": 0, "other": 0},
        s,
        disk_usage_excerpt_len=400,
    )
    assert "disk usage" in block.lower()
    assert "df" in block.lower()
    assert "i/o" in block.lower() or "io load" in block.lower()
    assert "checkpoint" in block.lower()


def test_answer_rules_cpu_thermal_probe() -> None:
    s = Settings()
    block = _answer_rules_block(
        "cpu temp",
        {"journal": 0, "docker": 0, "file": 0, "other": 0},
        s,
        cpu_thermal_excerpt_len=200,
    )
    assert "cpu load" in block.lower() or "thermal" in block.lower()
    assert "cpu_thermal" in block.lower()


def test_answer_rules_gpu_status_probe() -> None:
    s = Settings()
    block = _answer_rules_block(
        "gpu vram",
        {"journal": 0, "docker": 0, "file": 0, "other": 0},
        s,
        gpu_status_excerpt_len=300,
    )
    assert "gpu" in block.lower()
    assert "gpu_status" in block.lower()
