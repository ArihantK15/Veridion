---
title: Processor Lifecycle
purpose: Provide informative implementation guidance for the VDP-0002 Processor lifecycle.
status: Draft
owner: Arihant Kaul
related_documents:
  - ../../constitution/VDP-0002-Core-Processor-Model.md
  - ../../constitution/VDP-0001-Repository-Discovery-and-Canonical-Layout.md
last_updated: "2026-07-14"
---

# Processor Lifecycle

This document is informative. VDP-0002 is authoritative.

## Purpose

The Processor lifecycle describes the common execution flow that future Veridion CLIs, validators, MCP servers, hosted APIs, IDE extensions, libraries, and automation should follow when they claim Processor conformance.

## Lifecycle Flow

1. Created: initialize one Processing Session.
2. Repository Discovery: discover repository root, identity, copy class, and readiness using VDP-0001.
3. Bootstrap: establish supported features, configuration, manifest-derived context, and processor limits.
4. Context Loading: load declared repository context, records, schemas, extensions, and configuration.
5. Specification Loading: load Accepted VDPs and applicable dependencies.
6. Normalization: produce a derived internal model without modifying authoritative artifacts.
7. Semantic Processing: evaluate relationships among specifications, records, schemas, reviews, extensions, and repository artifacts.
8. Validation: evaluate supported structural, metadata, dependency, lifecycle, and repository checks.
9. Rule Evaluation: evaluate supported normative rules within the Processor capability boundary.
10. Derived Result Generation: assemble one Processing Result.
11. Completed, Cancelled, or Failed: enter exactly one terminal state.

## Session Boundary

A Processing Session has one Context, one lifecycle, one Processor, immutable authoritative inputs, and one Processing Result. Implementations may use workers, services, caches, or helper libraries, but those mechanics do not change the session boundary.

## Determinism

For the same repository, accepted specifications, supported features, configuration, and input snapshot, conforming Processors should produce equivalent Processing Results. Presentation, transport, and rendering may vary.

## Result Contents

A Processing Result may include:

- normalized model;
- dependency graph;
- semantic graph;
- diagnostics references;
- validation state;
- execution metadata.

These outputs are derived artifacts. They do not create authority.

## Error Classes

- Fatal: prevents completion of the claimed processing operation.
- Recoverable: allows processing to continue with diagnostics.
- Unsupported: required version, feature, artifact, capability, or specification is unsupported.
- Deferred: behavior is outside the current capability boundary or future VDP scope.
- Partial: processing continued but did not complete all relevant states, inputs, or checks.
- Interrupted: processing stopped due to cancellation, resource limit, or interruption.

## Security Notes

Processor implementations should treat tampered repositories, hostile extensions, resource exhaustion, malformed artifacts, recursive references, bootstrap poisoning, version confusion, conflicting artifacts, and repository mutation during processing as security-relevant conditions.

## Non-Implementation Boundary

This document does not define diagnostics formats, CLI exit codes, HTTP responses, MCP resources, LSP messages, JSON schemas, validator APIs, extension protocols, or executable behavior.
