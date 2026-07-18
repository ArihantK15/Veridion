from pathlib import Path
from typing import Callable

import aletheore.cli as _aletheore_cli
from aletheore.adapters.openai_compatible import OpenAICompatibleAdapter
from aletheore.report import run_reasoning_phase


def run_managed_audit(
    repo_path: Path,
    manual_dir: str | None = None,
    on_usage: Callable[[int, int], None] | None = None,
) -> str:
    adapter = OpenAICompatibleAdapter(
        name="DeepSeek",
        base_url="https://api.deepseek.com",
        api_key_env_var="DEEPSEEK_API_KEY",
        model="deepseek-v4-pro",
        # deepseek-v4-pro runs in thinking mode by default, which rejects
        # tool_choice="required" (400 invalid_request_error) - fall back to
        # the same unforced tool-choice path used for Ollama.
        supports_tool_choice=False,
        on_usage=on_usage,
    )
    report_path = run_reasoning_phase(
        adapter,
        str(repo_path),
        manual_dir or _aletheore_cli.MANUAL_DIR,
    )
    return Path(report_path).read_text()
