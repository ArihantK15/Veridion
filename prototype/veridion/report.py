from pathlib import Path

from veridion.adapters.base import AgentAdapter


class NoAdapterAvailableError(Exception):
    pass


class AmbiguousAdapterError(Exception):
    pass


def select_adapter(
    adapters: list[AgentAdapter], forced_name: str | None, interactive: bool
) -> AgentAdapter:
    available = [a for a in adapters if a.is_available()]

    if forced_name is not None:
        for adapter in available:
            if adapter.name == forced_name:
                return adapter
        raise NoAdapterAvailableError(
            f"requested adapter '{forced_name}' is not available on PATH"
        )

    if not available:
        names = ", ".join(a.name for a in adapters)
        raise NoAdapterAvailableError(
            f"no supported agent CLI found on PATH (checked: {names})"
        )

    if len(available) == 1:
        return available[0]

    if interactive:
        names = [a.name for a in available]
        print("Multiple agent CLIs found:")
        for i, name in enumerate(names, start=1):
            print(f"  {i}. {name}")
        choice = input(f"Which one? [1-{len(names)}]: ").strip()
        index = int(choice) - 1
        return available[index]

    names = ", ".join(a.name for a in available)
    raise AmbiguousAdapterError(
        f"multiple agent CLIs available ({names}) and not running interactively; "
        "pass --agent NAME to choose one"
    )


def build_instruction(manual_dir: str) -> str:
    return (
        f"Read every markdown file in the '{manual_dir}' directory and "
        f"'.veridion/evidence.json' in the current directory. Follow the manual's "
        f"Part I operating instructions exactly, including its output contract, and "
        f"write the resulting audit report to '.veridion/audit-report.md'."
    )


def run_reasoning_phase(adapter: AgentAdapter, repo_path: str, manual_dir: str) -> str:
    instruction = build_instruction(manual_dir)
    output = adapter.invoke(instruction, cwd=repo_path)

    report_path = Path(repo_path) / ".veridion" / "audit-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(output)
    return str(report_path)
