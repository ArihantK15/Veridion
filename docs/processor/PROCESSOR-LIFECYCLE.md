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

Repository discovery is outside the Processor lifecycle. VDP-0001 discovery consumes a candidate location and produces a Discovered Repository Result. The Processor consumes that result, or a logically equivalent discovered repository representation, during Bootstrap.

```text
Candidate location
  -> VDP-0001 repository discovery
  -> Discovered Repository Result
  -> Bootstrap / Context construction
  -> Processor lifecycle
  -> Processing Result
```

## Lifecycle Flow

Mandatory orderly states:

1. Created: initialize one Processing Session.
2. Bootstrap: accept the Discovered Repository Result, check sufficiency for the requested operation, establish supported versions and capability boundary, inspect Execution Environment constraints, and prepare Context construction.
3. Context Loading: load declared repository context, records, schemas, extensions, configuration, policy inputs, and declared external inputs.
4. Derived Result Generation: assemble one Processing Result when result emission is possible.
5. Completed, Cancelled, or Failed: enter exactly one logical terminal classification for orderly termination.

Conditional states:

- Specification Loading: load Accepted VDPs and applicable dependencies when required.
- Normalization: produce a derived internal model when required.
- Semantic Processing: evaluate relationships among artifacts when required.
- Validation: evaluate supported structural, metadata, dependency, lifecycle, and repository checks when required.
- Rule Evaluation: evaluate supported normative rules within the Processor capability boundary when required.

Conditional states are executed only when required by the requested operation, requested profile, declared capability set, or applicable accepted specifications.

## Skipped States

A conditional state may be skipped only when it is not required by the requested operation, is outside the declared capability boundary, is blocked by a prior fatal condition, is explicitly disabled by policy, or may be omitted under an accepted specification.

The Processing Result records which states executed, which states were skipped, why each state was skipped, and which states were not reached. A skipped state is not a successful state.

## Session Boundary

A Processing Session has one Context, one lifecycle, one Processor, immutable authoritative inputs, and at most one emitted terminal Processing Result. Implementations may use workers, services, caches, or helper libraries, but those mechanics do not change the session boundary.

The sequence is:

```text
Discovered Repository Result available
  -> Processing Session created
  -> Bootstrap
  -> Context Loading
  -> Context frozen
  -> conditional processing states
  -> Derived Result Generation
  -> orderly terminal classification
```

The authoritative input snapshot is frozen before any state produces normative or conformance conclusions. If repository state changes after that snapshot, the current session continues against the frozen snapshot or terminates with diagnostics; it does not silently switch snapshots.

## Context and Environment

Processing Context is immutable semantic input to the session. It may include the discovered repository result, accepted specification set, declared configuration, policy inputs, supported version declarations, requested operation or profile reference, declared external inputs, and capability boundary.

Execution Environment is mutable runtime condition. It may include filesystem access, network availability, memory, CPU, operating system, sandbox, clock, interactive state, and process limits.

Environment-dependent facts that affect Processing Results are captured into Context or reported as limitations. Environment availability is not authority.

## Determinism

For the same discovered repository result or equivalent repository snapshot, accepted specification set and versions, Processing Context, requested operation or profile, capability identifiers and versions, declared policies, configuration, declared external inputs, compatible resource-limit outcomes, and no accepted specification permitting variation, conforming Processors should produce equivalent Processing Results.

Processors with different capability sets are not required to produce equivalent complete results. They report the capability difference and preserve equivalent conclusions for the shared capability subset where applicable.

## Result Contents

A Processing Result may include:

- normalized model;
- dependency graph;
- semantic graph;
- diagnostics references;
- validation state;
- execution metadata.

These outputs are derived artifacts. They do not create authority. Processor output may become part of an authoritative artifact only after authorized human or governance process, explicit reviewable incorporation, provenance preservation, and satisfaction of applicable lifecycle or repository rules.

## Terminal Results and Catastrophic Interruption

An orderly terminal condition is classified as Completed, Cancelled, or Failed. A conforming Processor attempts to emit exactly one terminal Processing Result for an orderly terminal condition.

Catastrophic interruption may prevent result emission. Examples include host termination, power loss, process crash, fatal runtime failure, unrecoverable memory exhaustion, or loss of execution environment. When no result is emitted, absence of a result is not success, cancellation, failure evidence, or conformance evidence. A caller or orchestrator may record an external interruption record, but later recovery does not fabricate a Processor Result.

## Error Classes

- Fatal: prevents completion of the claimed processing operation.
- Recoverable: allows processing to continue with diagnostics.
- Unsupported: required version, feature, artifact, capability, or specification is unsupported.
- Deferred: behavior is outside the current capability boundary or future VDP scope.
- Partial: processing continued but did not complete all relevant states, inputs, or checks.
- Interrupted: processing stopped due to cancellation, resource limit, or interruption; catastrophic interruption may prevent result emission.

## Security Notes

Processor implementations should treat tampered repositories, hostile extensions, resource exhaustion, malformed artifacts, recursive references, bootstrap poisoning, version confusion, conflicting artifacts, and repository mutation during processing as security-relevant conditions.

## Non-Implementation Boundary

This document does not define diagnostics formats, CLI exit codes, HTTP responses, MCP resources, LSP messages, JSON schemas, validator APIs, extension protocols, or executable behavior.
