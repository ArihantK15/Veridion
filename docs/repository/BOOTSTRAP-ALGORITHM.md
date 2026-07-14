---
title: Repository Bootstrap Algorithm
purpose: Provide informative implementation guidance for VDP-0001 repository discovery.
status: Draft
owner: Arihant Kaul
related_documents:
  - ../../constitution/VDP-0001-Repository-Discovery-and-Canonical-Layout.md
  - ../../constitution/VDP--001-Specification-Specification.md
  - ../../constitution/VDP-0000-Veridion-Constitution.md
last_updated: "2026-07-14"
---

# Repository Bootstrap Algorithm

This document is informative. VDP-0001 is authoritative.

## Purpose

The repository bootstrap flow gives implementers a common mental model for discovering a Veridion repository before any CLI, MCP server, IDE extension, hosted validator, automation, or AI agent interprets repository content.

## Bootstrap Flow

1. Receive a start path, archive root, working copy, hosted repository location, or caller-selected repository location.
2. Search for candidate `VERIDION.yaml` files from the start location toward the applicable boundary.
3. Select the nearest valid candidate manifest.
4. Validate manifest syntax and supported manifest version.
5. Establish the repository root as the directory containing the selected manifest.
6. Read identity metadata and classify the copy as canonical, official mirror, archive, working copy, fork, temporary clone, offline copy, partial copy, or untrusted copy.
7. Validate canonical layout expectations.
8. Locate VDP-0000 and verify constitutional metadata.
9. Locate Accepted VDPs by metadata and lifecycle state.
10. Locate schemas, reviews, governance records, repository records, diagnostics, and extensions.
11. Build a non-authoritative repository graph for navigation.
12. Return readiness, diagnostics, discovered relationships, and unsupported capability information.

## Readiness States

- Ready: Required manifest, layout, constitutional, specification, and record evidence are present for the claimed operation.
- Partial: Some repository evidence is present, but required artifacts or records are missing for full readiness.
- Unsupported: The repository uses a manifest version, mandatory capability, or artifact form the processor does not support.
- Untrusted: Provenance, identity, canonicality, or integrity cannot be established.

## Determinism Rules

Discovery should produce the same root, copy class, readiness state, and diagnostics for the same input and processor capability set. Implementers should avoid fallback guesses such as treating a Git remote URL, repository folder name, or README title as repository identity.

## Partial and Offline Repositories

Offline inspection should work without network access. A processor may classify local readiness from local artifacts, but it should not claim public canonicality without governance, migration, recovery, or provenance records.

Partial repositories should preserve useful diagnostics. Missing manifests, missing Constitution files, missing records, future manifest versions, and unsupported capabilities should be visible to callers.

## Security Notes

Repository bootstrap should treat manifest tampering, path traversal, symbolic links, filesystem normalization conflicts, hostile mirrors, malicious archives, stale caches, spoofed forks, and bootstrap poisoning as security-relevant conditions.

## Non-Implementation Boundary

This document does not define command-line flags, MCP resources, API payloads, parser libraries, filesystem walkers, or validation code.
