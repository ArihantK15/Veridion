from pathlib import Path

from scan_worker.managed_audit import run_managed_audit


def test_run_managed_audit_returns_report_text(tmp_path, monkeypatch):
    repo_path = tmp_path / "repo"
    (repo_path / ".aletheore").mkdir(parents=True)
    (repo_path / ".aletheore" / "air.toon").write_text("fake toon evidence")

    captured_adapters = []

    def fake_run_reasoning_phase(adapter, repo_path_arg, manual_dir):
        captured_adapters.append(adapter)
        report_path = Path(repo_path_arg) / ".aletheore" / "audit-report.md"
        report_path.write_text("# Real Report\n\nfindings here")
        return str(report_path)

    monkeypatch.setattr("scan_worker.managed_audit.run_reasoning_phase", fake_run_reasoning_phase)

    assert "Real Report" in run_managed_audit(repo_path)

    adapter = captured_adapters[0]
    assert adapter.name == "DeepSeek"
    assert adapter._base_url == "https://api.deepseek.com"
    assert adapter._api_key_env_var == "DEEPSEEK_API_KEY"
    assert adapter._model == "deepseek-v4-pro"
    assert adapter._supports_tool_choice is False
