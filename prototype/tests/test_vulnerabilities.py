import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from veridion.vulnerabilities import check_vulnerabilities


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("fastapi==0.100.0\nrequests>=2.0\n# comment\n")
    (repo / "package.json").write_text(
        json.dumps({"dependencies": {"left-pad": "^1.3.0"}, "devDependencies": {}})
    )
    return repo


def _mock_response(payload: dict):
    mock = MagicMock()
    mock.read.return_value = json.dumps(payload).encode("utf-8")
    mock.__enter__.return_value = mock
    mock.__exit__.return_value = False
    return mock


def test_check_vulnerabilities_parses_pinned_pip_and_npm_versions(tmp_path):
    repo = make_repo(tmp_path)
    batch_response = _mock_response({"results": [{}, {}]})

    with patch("veridion.vulnerabilities.urllib.request.urlopen", return_value=batch_response) as mock_urlopen:
        result = check_vulnerabilities(repo)

    assert result == {"checked": True, "reason": None, "findings": []}
    sent_request = mock_urlopen.call_args[0][0]
    sent_body = json.loads(sent_request.data)
    queries = sent_body["queries"]
    assert {"package": {"name": "fastapi", "ecosystem": "PyPI"}, "version": "0.100.0"} in queries
    assert {"package": {"name": "left-pad", "ecosystem": "npm"}, "version": "1.3.0"} in queries
    assert not any(q["package"]["name"] == "requests" for q in queries)


def test_check_vulnerabilities_reports_a_real_finding(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("fastapi==0.100.0\n")

    batch_response = _mock_response({"results": [{"vulns": [{"id": "PYSEC-2024-38"}]}]})
    detail_response = _mock_response(
        {
            "id": "PYSEC-2024-38",
            "details": "ReDoS in multipart form parsing.",
            "severity": [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"}],
        }
    )

    with patch(
        "veridion.vulnerabilities.urllib.request.urlopen",
        side_effect=[batch_response, detail_response],
    ):
        result = check_vulnerabilities(repo)

    assert result["checked"] is True
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["package"] == "fastapi"
    assert finding["advisory_id"] == "PYSEC-2024-38"
    assert finding["severity"] == [{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H"}]


def test_check_vulnerabilities_degrades_gracefully_on_network_failure(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "requirements.txt").write_text("fastapi==0.100.0\n")

    with patch(
        "veridion.vulnerabilities.urllib.request.urlopen",
        side_effect=urllib.error.URLError("connection refused"),
    ):
        result = check_vulnerabilities(repo)

    assert result["checked"] is False
    assert "connection refused" in result["reason"]
    assert result["findings"] == []


def test_check_vulnerabilities_no_pins_short_circuits_without_network_call(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    with patch("veridion.vulnerabilities.urllib.request.urlopen") as mock_urlopen:
        result = check_vulnerabilities(repo)

    mock_urlopen.assert_not_called()
    assert result == {"checked": True, "reason": None, "findings": []}
