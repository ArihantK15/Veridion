import subprocess
from unittest.mock import MagicMock, patch

import pytest

from aletheore.adapters.base import AgentAdapter
from aletheore.adapters.claude_code import AdapterInvocationError, ClaudeCodeAdapter


def test_agent_adapter_is_abstract():
    with pytest.raises(TypeError):
        AgentAdapter()


def test_claude_code_adapter_name():
    assert ClaudeCodeAdapter().name == "claude"


@patch("aletheore.adapters.claude_code.shutil.which")
def test_is_available_true_when_binary_found(mock_which):
    mock_which.return_value = "/usr/local/bin/claude"
    assert ClaudeCodeAdapter().is_available() is True
    mock_which.assert_called_once_with("claude")


@patch("aletheore.adapters.claude_code.shutil.which")
def test_is_available_false_when_binary_missing(mock_which):
    mock_which.return_value = None
    assert ClaudeCodeAdapter().is_available() is False


@patch("aletheore.adapters.claude_code.subprocess.run")
def test_invoke_returns_stdout_on_success(mock_run):
    mock_run.return_value = MagicMock(returncode=0, stdout="report text", stderr="")
    result = ClaudeCodeAdapter().invoke("do the audit", cwd="/some/repo")
    assert result == "report text"
    args, kwargs = mock_run.call_args
    assert args[0][0] == "claude"
    assert kwargs["cwd"] == "/some/repo"


@patch("aletheore.adapters.claude_code.subprocess.run")
def test_invoke_raises_on_nonzero_exit(mock_run):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
    with pytest.raises(AdapterInvocationError, match="boom"):
        ClaudeCodeAdapter().invoke("do the audit", cwd="/some/repo")


@patch("aletheore.adapters.claude_code.subprocess.run")
def test_invoke_raises_on_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=600)
    with pytest.raises(AdapterInvocationError, match="timed out"):
        ClaudeCodeAdapter().invoke("do the audit", cwd="/some/repo")
