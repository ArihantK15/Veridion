from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from veridion.cli import main
from veridion.report import (
    AmbiguousAdapterError,
    NoAdapterAvailableError,
    build_instruction,
    run_reasoning_phase,
    select_adapter,
)


def make_adapter(name: str, available: bool):
    adapter = MagicMock()
    adapter.name = name
    adapter.is_available.return_value = available
    return adapter


def test_select_adapter_returns_only_available_one():
    a = make_adapter("claude", True)
    b = make_adapter("cursor", False)
    result = select_adapter([a, b], forced_name=None, interactive=False)
    assert result is a


def test_select_adapter_raises_when_none_available():
    a = make_adapter("claude", False)
    with pytest.raises(NoAdapterAvailableError):
        select_adapter([a], forced_name=None, interactive=False)


def test_select_adapter_raises_when_multiple_and_not_interactive_and_no_flag():
    a = make_adapter("claude", True)
    b = make_adapter("cursor", True)
    with pytest.raises(AmbiguousAdapterError):
        select_adapter([a, b], forced_name=None, interactive=False)


def test_select_adapter_honors_forced_name():
    a = make_adapter("claude", True)
    b = make_adapter("cursor", True)
    result = select_adapter([a, b], forced_name="cursor", interactive=False)
    assert result is b


def test_build_instruction_references_manual_and_evidence():
    instruction = build_instruction(manual_dir="manual")
    assert "manual" in instruction
    assert ".veridion/evidence.json" in instruction


def test_run_reasoning_phase_writes_report(tmp_path):
    repo = tmp_path
    (repo / ".veridion").mkdir()
    (repo / ".veridion" / "evidence.json").write_text("{}")

    adapter = MagicMock()
    adapter.invoke.return_value = "# Audit Report\n\nfindings here\n"

    report_path = run_reasoning_phase(adapter, repo_path=str(repo), manual_dir="manual")

    written = Path(report_path)
    assert written == repo / ".veridion" / "audit-report.md"
    assert written.read_text() == "# Audit Report\n\nfindings here\n"
    adapter.invoke.assert_called_once()


def test_main_requires_a_command(capsys):
    with patch("sys.argv", ["veridion"]):
        with pytest.raises(SystemExit):
            main()


def test_main_audit_invokes_audit_flow(tmp_path):
    with patch("sys.argv", ["veridion", "audit", str(tmp_path), "--agent", "claude"]):
        with patch("veridion.cli._audit", return_value=0) as mock_audit:
            exit_code = main()
    assert exit_code == 0
    mock_audit.assert_called_once_with(str(tmp_path), "claude")
