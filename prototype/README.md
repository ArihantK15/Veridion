<p align="center">
  <img src="../assets/logo.png" alt="Veridion" width="360">
</p>

# Veridion Prototype

**Status:** Unratified prototype under VDP-0000-REQ-009 ("Prototypes and experiments MAY
precede specifications, but they MUST NOT become normative without the VDP process").

This directory is deliberately out-of-band from the constitutional apparatus in
`constitution/`, `docs/governance/`, and `docs/reviews/`. It does not modify, supersede, or
depend on any VDP. It is not a proposal and should not be treated as one.

Design spec: `../docs/superpowers/specs/2026-07-14-veridion-v1-design.md`
Implementation plan: `../docs/superpowers/plans/2026-07-14-veridion-v1-scanner.md`

## What this is

A working CLI, `veridion audit [path]`, that produces a grounded audit report of a
repository using deterministic static analysis (tree-sitter + git log) plus a shell-out to
an already-installed coding agent CLI (Claude Code in v1).

## Setup

```bash
cd prototype
pip install -e ".[dev]"
pytest
```
