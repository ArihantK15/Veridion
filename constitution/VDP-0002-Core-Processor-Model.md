---
identifier: VDP-0002
title: Core Processor Model
status: Draft
version: 0.1.0
format_version: "1.0"
authors:
  - Arihant Kaul
reviewers: []
created: "2026-07-14"
updated: "2026-07-14"
dependencies:
  - VDP--001
  - VDP-0000
  - VDP-0001
supersedes: []
superseded_by: null
category: processor
tags:
  - processor
  - execution-model
  - derived-artifacts
  - conformance
---

# Core Processor Model

## Abstract

VDP-0002 defines the abstract Veridion Processor model implemented by CLIs, validators, IDE integrations, MCP servers, hosted APIs, libraries, automation, and future implementations. A Processor consumes authoritative repository artifacts and produces derived processing results. It does not create authority, accept proposals, modify constitutional authority, change governance, or become a governance actor.

This specification defines processor terminology, session boundaries, lifecycle states, input and output authority, determinism, error classification, forward compatibility, and security constraints. It does not define diagnostics formats, CLI commands, HTTP APIs, MCP resources, LSP behavior, JSON payloads, manifest schemas, extension protocols, validator interfaces, or capability negotiation.

## Motivation

Veridion implementations need a shared execution model before concrete interfaces diverge. Without an abstract Processor model, a CLI, MCP server, hosted platform, and validator could disagree about what counts as input, when repository state is loaded, whether generated output is authoritative, how cancellation behaves, or how unsupported future specifications are handled.

The Processor model gives every implementation a common semantic contract while leaving concrete protocols to future VDPs.

## Goals

- Define the canonical abstract Processor.
- Define Processing, Processing State, Processing Session, Processing Lifecycle, Processing Result, capability boundaries, responsibilities, and non-responsibilities.
- Establish that Processors consume authoritative artifacts and produce derived artifacts.
- Define deterministic lifecycle states and transitions.
- Define immutable authoritative inputs for a Processing Session.
- Define accepted input categories and derived output categories.
- Define equivalence expectations for conforming processors.
- Define fatal, recoverable, unsupported, deferred, partial, and interrupted processing conditions.
- Define forward-compatible handling of unknown future specifications and capabilities.
- Address core security risks without tying the model to an operating system.

## Non Goals

- Define diagnostics formats.
- Define CLI commands, exit codes, flags, or terminal behavior.
- Define HTTP, MCP, LSP, JSON, hosted API, or library interfaces.
- Define the `VERIDION.yaml` manifest schema.
- Define a concrete capability model or extension protocol.
- Define a validator interface.
- Implement any processor.
- Create repository scanning code, schema parsers, or test fixtures.
- Accept proposals, change governance, or modify VDP--001, VDP-0000, or VDP-0001.

## Terminology

- Processor: The abstract execution model that reads Veridion repository context and produces a derived Processing Result.
- Processing: The act of executing the Processor lifecycle for one Processing Session.
- Processing State: A named lifecycle state with deterministic entry and exit rules.
- Processing Session: One bounded execution with one Context, one Processor, one lifecycle, immutable authoritative inputs, and one Result.
- Processing Lifecycle: The ordered state machine through which a Processing Session proceeds.
- Processing Result: The derived output of a Processing Session.
- Context: The discovered repository state, accepted specifications, records, configuration, supported features, and declared inputs available to a Processing Session.
- Processor Capability Boundary: The declared feature boundary within which a Processor claims conformance.
- Processor Responsibility: A duty every conforming Processor has within its claimed capability boundary.
- Processor Non-responsibility: A duty explicitly excluded from the abstract Processor model.
- Authoritative input: A repository artifact or record whose authority derives from accepted specifications or valid governance records.
- Derived artifact: Any output created by Processing, including normalized models, graphs, diagnostics references, validation states, and execution metadata.
- Equivalent Processing Result: A result with the same normative meaning, readiness classification, validation conclusions, and material diagnostics, even if presentation differs.

## Background

VDP--001 defines the proposal system and the authority boundary between Markdown specifications, metadata, and derived artifacts. VDP-0000 defines governance authority and prohibits automated systems from exercising constitutional authority. VDP-0001 defines repository discovery, canonical layout, repository identity, and the `VERIDION.yaml` bootstrap manifest concept.

VDP-0002 builds on those specifications by defining what an implementation does after repository discovery begins and before any concrete interface presents results to a user, API, editor, workflow, or agent.

## Problem Statement

Every Veridion implementation needs to process repository artifacts consistently. The project needs one abstract execution model that defines what a Processor may read, how it moves through lifecycle states, how it freezes authoritative inputs, how it handles unknown or unsupported content, and what it may output without creating new authority.

Without this model, concrete implementations could silently rely on undefined external state, treat generated summaries as authoritative, mutate repository authority, skip required lifecycle stages, or produce incompatible results from the same repository.

## Proposed Design

The Processor is a deterministic state machine scoped to one Processing Session. A session begins with declared inputs and supported features, discovers repository context according to VDP-0001, loads authoritative artifacts, normalizes them into an internal derived model, performs semantic processing, validates applicable requirements, evaluates supported rules, generates a derived Processing Result, and completes, cancels, or fails.

The Processor has no authority of its own. It can read, normalize, validate, evaluate, report, cache, index, summarize, or generate derived artifacts within its capability boundary. It cannot accept proposals, modify governance, ratify constitutional text, create canonical repository authority, or turn generated artifacts into authoritative artifacts.

## Normative Requirements

### Processor Identity and Authority

### VDP-0002-REQ-001 — Abstract processor definition

A Processor MUST be the abstract execution model implemented by concrete Veridion implementations.

### VDP-0002-REQ-002 — Interface independence

A Processor MUST NOT be defined as a CLI, validator, IDE extension, MCP server, hosted API, library, or any other concrete interface.

### VDP-0002-REQ-003 — Authority consumption

A Processor MUST consume authoritative artifacts according to accepted specifications and valid records.

### VDP-0002-REQ-004 — Derived production

A Processor MUST produce only derived artifacts and derived conclusions unless an accepted specification explicitly grants a scoped authority to a processor output.

### VDP-0002-REQ-005 — No authority creation

A Processor MUST NOT create constitutional, governance, proposal, repository, or specification authority by processing.

### VDP-0002-REQ-006 — No proposal acceptance

A Processor MUST NOT accept, reject, ratify, withdraw, supersede, or transition VDP lifecycle status.

### VDP-0002-REQ-007 — No governance mutation

A Processor MUST NOT appoint roles, remove roles, vote, authorize emergencies, transfer repository authority, or change governance state.

### VDP-0002-REQ-008 — No constitutional modification

A Processor MUST NOT modify constitutional authority or treat generated constitutional text as accepted authority.

### VDP-0002-REQ-009 — Capability boundary

A Processor MUST declare or expose the capability boundary under which it claims conformance.

### VDP-0002-REQ-010 — Responsibility boundary

A Processor MUST distinguish responsibilities inside its capability boundary from non-responsibilities outside that boundary.

### Core Concepts

### VDP-0002-REQ-011 — Processing definition

Processing MUST mean executing the Processor lifecycle for one Processing Session.

### VDP-0002-REQ-012 — Processing state definition

A Processing State MUST have a defined meaning, deterministic transition rules, and observable result impact when relevant.

### VDP-0002-REQ-013 — Processing session definition

A Processing Session MUST bind one Processor, one Context, one lifecycle, immutable authoritative inputs, and one Processing Result.

### VDP-0002-REQ-014 — Processing lifecycle definition

The Processing Lifecycle MUST define the ordered state progression for a Processing Session.

### VDP-0002-REQ-015 — Processing result definition

A Processing Result MUST be the derived output of one Processing Session.

### VDP-0002-REQ-016 — Context definition

Context MUST include the repository state, accepted specifications, relevant records, configuration, supported features, and declared inputs used by the session.

### VDP-0002-REQ-017 — Processor capability boundary definition

Processor Capability Boundary MUST describe the supported features, specification versions, input forms, output forms, and optional behaviors claimed by the Processor.

### VDP-0002-REQ-018 — Processor responsibility definition

Processor Responsibility MUST describe duties required for claimed conformance within the capability boundary.

### VDP-0002-REQ-019 — Processor non-responsibility definition

Processor Non-responsibility MUST describe duties explicitly excluded from the abstract Processor model or deferred to future VDPs.

### VDP-0002-REQ-020 — Derived artifact labeling

Processor outputs SHOULD be labeled or exposed as derived artifacts when presented to humans or other systems.

### Processing Session

### VDP-0002-REQ-021 — Single context

A Processing Session MUST have exactly one Context.

### VDP-0002-REQ-022 — Single lifecycle

A Processing Session MUST have exactly one lifecycle instance.

### VDP-0002-REQ-023 — Single processor

A Processing Session MUST be executed by exactly one Processor instance or one logically equivalent Processor execution.

### VDP-0002-REQ-024 — Single result

A Processing Session MUST produce exactly one terminal Processing Result when it completes, fails, or is cancelled.

### VDP-0002-REQ-025 — Immutable authoritative inputs

Authoritative inputs for a Processing Session MUST be immutable for the duration of that session.

### VDP-0002-REQ-026 — Input snapshot

A Processor MUST define the repository and artifact snapshot used for a Processing Session before semantic processing begins.

### VDP-0002-REQ-027 — Session isolation

State from one Processing Session MUST NOT silently alter the authoritative inputs or conclusions of another session.

### VDP-0002-REQ-028 — External state declaration

Any external state used by a Processing Session MUST be declared in Context or reported as unavailable, unsupported, or non-authoritative.

### VDP-0002-REQ-029 — Undefined state prohibition

A Processor MUST NOT rely on undefined external state when producing conformance, validation, readiness, or authority-related conclusions.

### VDP-0002-REQ-030 — Session metadata

A Processing Result SHOULD include execution metadata sufficient to identify supported features, configuration, input snapshot, lifecycle terminal state, and material limitations.

### Lifecycle States

### VDP-0002-REQ-031 — Created state

The Created state MUST initialize the session without reading authoritative repository artifacts.

### VDP-0002-REQ-032 — Repository Discovery state

The Repository Discovery state MUST discover repository identity, root, copy class, readiness, and discovery diagnostics according to VDP-0001.

### VDP-0002-REQ-033 — Bootstrap state

The Bootstrap state MUST establish the minimum processing environment, supported feature set, configuration, and manifest-derived context needed for later states.

### VDP-0002-REQ-034 — Context Loading state

The Context Loading state MUST load declared authoritative inputs, relevant records, extensions, schemas, configuration, and supported repository context.

### VDP-0002-REQ-035 — Specification Loading state

The Specification Loading state MUST load accepted specifications and applicable dependencies before semantic processing depends on them.

### VDP-0002-REQ-036 — Normalization state

The Normalization state MUST convert loaded inputs into a derived internal model without changing authoritative artifacts.

### VDP-0002-REQ-037 — Semantic Processing state

The Semantic Processing state MUST evaluate semantic relationships among loaded artifacts within the Processor capability boundary.

### VDP-0002-REQ-038 — Validation state

The Validation state MUST evaluate applicable structural, metadata, dependency, lifecycle, and repository constraints supported by the Processor.

### VDP-0002-REQ-039 — Rule Evaluation state

The Rule Evaluation state MUST evaluate supported normative rules, policies, or conformance checks only within the declared capability boundary.

### VDP-0002-REQ-040 — Derived Result Generation state

The Derived Result Generation state MUST assemble the Processing Result from derived models, graph data, validation state, diagnostics references, and execution metadata.

### VDP-0002-REQ-041 — Completed state

The Completed state MUST indicate that processing reached a terminal successful result for the claimed capability boundary.

### VDP-0002-REQ-042 — Cancelled state

The Cancelled state MUST indicate that processing stopped due to caller request, policy, resource limit, or interruption before normal completion.

### VDP-0002-REQ-043 — Failed state

The Failed state MUST indicate that processing reached a terminal failure and MUST preserve available diagnostic context.

### VDP-0002-REQ-044 — Terminal state exclusivity

A Processing Session MUST end in exactly one terminal state: Completed, Cancelled, or Failed.

### VDP-0002-REQ-045 — Deterministic transitions

Every lifecycle transition MUST be deterministic for the same Context, supported features, configuration, and input snapshot.

### Inputs

### VDP-0002-REQ-046 — Repository input

A Processor MUST read repository input through the repository discovery model defined by VDP-0001.

### VDP-0002-REQ-047 — Accepted specification input

A Processor MUST treat only validated Accepted specifications as accepted specification input.

### VDP-0002-REQ-048 — Schema input

A Processor MAY read schemas as validation aids but MUST NOT allow schemas to override authoritative Markdown specifications unless accepted specifications grant scoped schema authority.

### VDP-0002-REQ-049 — Governance record input

A Processor MAY read governance records but MUST NOT change governance meaning by processing them.

### VDP-0002-REQ-050 — Review record input

A Processor MAY read review records as evidence or context but MUST NOT treat review presence alone as proposal acceptance.

### VDP-0002-REQ-051 — Extension input

A Processor MAY read extensions only within its capability boundary and only after core repository discovery and bootstrap constraints are evaluated.

### VDP-0002-REQ-052 — Configuration input

Configuration used for Processing MUST be included in Context or represented in execution metadata.

### VDP-0002-REQ-053 — No undefined external input

A Processor MUST NOT use network state, local cache state, private memory, environment-specific defaults, or hosted metadata as authoritative input unless the Context declares it and accepted specifications permit it.

### VDP-0002-REQ-054 — Input conflict reporting

Conflicting authoritative inputs MUST produce diagnostics or failure rather than silent reconciliation.

### Outputs

### VDP-0002-REQ-055 — Processing result output

A Processor MUST produce a Processing Result as its session output.

### VDP-0002-REQ-056 — Normalized model output

A Processing Result MAY contain a normalized model, and that model MUST be treated as derived.

### VDP-0002-REQ-057 — Dependency graph output

A Processing Result MAY contain a dependency graph, and that graph MUST be treated as derived.

### VDP-0002-REQ-058 — Semantic graph output

A Processing Result MAY contain a semantic graph, and that graph MUST be treated as derived.

### VDP-0002-REQ-059 — Diagnostics reference output

A Processing Result MAY contain diagnostics references without defining a diagnostics format.

### VDP-0002-REQ-060 — Validation state output

A Processing Result MAY contain validation state for supported checks.

### VDP-0002-REQ-061 — Execution metadata output

A Processing Result SHOULD contain execution metadata describing lifecycle terminal state, supported features, configuration, and material limitations.

### VDP-0002-REQ-062 — Output non-authority

Processing Result content MUST NOT become authoritative merely because it is generated by a conforming Processor.

### Determinism and Equivalence

### VDP-0002-REQ-063 — Equivalent result requirement

Two conforming Processors with the same repository, accepted specifications, supported features, configuration, and input snapshot MUST produce equivalent Processing Results unless an accepted specification explicitly permits variation.

### VDP-0002-REQ-064 — Presentation independence

Equivalent Processing Results MAY differ in presentation, ordering of non-semantic fields, rendering, or transport encoding.

### VDP-0002-REQ-065 — Material conclusion stability

Validation conclusions, readiness classifications, dependency relationships, and material diagnostics MUST remain equivalent under equivalent inputs.

### VDP-0002-REQ-066 — Variation disclosure

Permitted variation MUST be disclosed in execution metadata or diagnostics when it affects interpretation.

### VDP-0002-REQ-067 — Non-determinism prohibition

A Processor MUST NOT use randomness, wall-clock time, network availability, private memory, or cache state to change normative conclusions unless an accepted specification explicitly permits that input.

### Error Model

### VDP-0002-REQ-068 — Fatal condition

A fatal condition MUST prevent completion of the claimed processing operation.

### VDP-0002-REQ-069 — Recoverable condition

A recoverable condition MAY allow processing to continue while preserving diagnostics about the condition.

### VDP-0002-REQ-070 — Unsupported condition

An unsupported condition MUST indicate that the Processor lacks support for a required version, feature, artifact, capability, or specification.

### VDP-0002-REQ-071 — Deferred condition

A deferred condition MUST indicate that the requested behavior is intentionally outside the current Processor capability boundary or deferred to future specifications.

### VDP-0002-REQ-072 — Partial processing

Partial processing MUST report which lifecycle states, inputs, capabilities, or checks were not completed.

### VDP-0002-REQ-073 — Interrupted processing

Interrupted processing MUST produce a Cancelled or Failed terminal result with available diagnostics when feasible.

### VDP-0002-REQ-074 — No CLI exit code requirement

The Processor error model MUST NOT define CLI exit codes or interface-specific error transport.

### Forward Compatibility

### VDP-0002-REQ-075 — Unknown future specification preservation

A Processor encountering unknown future specifications MUST preserve references and report unsupported status when relevant.

### VDP-0002-REQ-076 — Safe continuation

A Processor SHOULD continue processing supported artifacts when unknown future specifications do not affect the claimed operation.

### VDP-0002-REQ-077 — No silent reinterpretation

A Processor MUST NOT silently reinterpret unsupported future specifications, fields, capabilities, or lifecycle states as older supported meanings.

### VDP-0002-REQ-078 — Unknown capability reporting

Unknown required capabilities MUST be reported as unsupported or partial.

### VDP-0002-REQ-079 — Unknown optional capability handling

Unknown optional capabilities SHOULD be preserved and ignored safely when they do not affect the claimed operation.

### VDP-0002-REQ-080 — Version confusion prevention

A Processor MUST distinguish proposal version, proposal format version, manifest version, capability version, schema version, and processor version when those values are available.

### Security

### VDP-0002-REQ-081 — Tampered repository handling

A Processor MUST treat tampered repositories or inconsistent repository evidence as security-relevant conditions.

### VDP-0002-REQ-082 — Hostile extension handling

A Processor MUST treat extensions as untrusted until they are validated within the Processor capability boundary.

### VDP-0002-REQ-083 — Resource exhaustion handling

A Processor SHOULD bound recursion, graph traversal, artifact loading, and derived result generation to reduce resource exhaustion risk.

### VDP-0002-REQ-084 — Malformed artifact handling

Malformed artifacts MUST produce diagnostics or failure rather than undefined behavior.

### VDP-0002-REQ-085 — Recursive reference handling

Recursive references MUST be detected or bounded when they affect processing.

### VDP-0002-REQ-086 — Bootstrap poisoning handling

Bootstrap poisoning attempts MUST be reported when manifest, repository discovery, configuration, or extension data conflicts with authoritative records.

### VDP-0002-REQ-087 — Security portability

Processor security requirements MUST NOT depend on a specific operating system, filesystem, forge, runtime, or hosting platform.

### Failure Scenarios

### VDP-0002-REQ-088 — Repository mutation during processing

If repository state changes during Processing, the Processor MUST preserve the session input snapshot or fail with diagnostics.

### VDP-0002-REQ-089 — Specification superseded during processing

If a specification is superseded during Processing, the current session MUST continue with its immutable input snapshot or fail with diagnostics.

### VDP-0002-REQ-090 — Invalid context

Invalid Context MUST prevent successful completion for operations that depend on that Context.

### VDP-0002-REQ-091 — Processing cancellation

Cancellation MUST lead to the Cancelled state unless the Processor has already reached Completed or Failed.

### VDP-0002-REQ-092 — Missing dependency

A missing required dependency MUST produce a fatal, unsupported, or partial result according to the claimed operation.

### VDP-0002-REQ-093 — Future specification

A future specification required by the repository MUST produce unsupported or partial status when the Processor cannot interpret it.

### VDP-0002-REQ-094 — Unknown capability

An unknown required capability MUST prevent a full-ready conclusion for operations that depend on that capability.

### VDP-0002-REQ-095 — Conflicting artifacts

Conflicting artifacts MUST be reported and MUST NOT be silently resolved by processor preference.

### Deferred Interface Boundaries

### VDP-0002-REQ-096 — Diagnostics format deferral

This specification MUST NOT define a diagnostics format.

### VDP-0002-REQ-097 — Concrete interface deferral

This specification MUST NOT define CLI, HTTP, MCP, LSP, JSON, hosted API, library, or validator interfaces.

### VDP-0002-REQ-098 — Manifest schema deferral

This specification MUST NOT define the concrete manifest schema.

### VDP-0002-REQ-099 — Extension protocol deferral

This specification MUST NOT define the extension protocol.

### VDP-0002-REQ-100 — Capability model deferral

This specification MUST NOT define the full capability model beyond the abstract Processor capability boundary.

## Informative Notes

The Processor is the shared semantic center beneath future Veridion implementations. A concrete CLI may invoke a Processor and print results. An MCP server may expose Processor-derived resources. A hosted platform may render Processing Results. None of those interfaces changes the abstract authority boundary.

## Architecture

The model has four layers:

1. Repository discovery and bootstrap from VDP-0001.
2. Processing Session with immutable authoritative inputs.
3. Processor lifecycle state machine.
4. Derived Processing Result consumed by concrete interfaces.

Concrete implementations may split these layers across processes, services, libraries, or workers, but claimed conformance is measured against the abstract model.

## Interfaces

This draft defines no concrete interface. It defines semantic expectations for any future interface that invokes a Processor:

- the caller provides or selects repository input;
- the Processor establishes Context;
- the Processor executes one lifecycle;
- the Processor returns one Processing Result;
- the interface renders, transports, stores, or summarizes the derived result without making it authoritative.

## Algorithms

Processor lifecycle pseudocode:

```text
create session
enter Created
enter Repository Discovery
enter Bootstrap
enter Context Loading
freeze authoritative input snapshot
enter Specification Loading
enter Normalization
enter Semantic Processing
enter Validation
enter Rule Evaluation
enter Derived Result Generation
if successful:
  enter Completed
else if cancelled:
  enter Cancelled
else:
  enter Failed
return Processing Result
```

Transitions are deterministic for the same Context, supported features, configuration, and input snapshot.

## Evidence Requirements

Evidence for Processor conformance includes lifecycle traces, input snapshots, supported feature declarations, configuration records, Processing Results, diagnostics references, validation outcomes, and examples showing handling of unsupported, partial, cancelled, and failed processing.

## Reasoning Requirements

Processors should distinguish authoritative inputs, derived models, diagnostics, assumptions, and interface presentation. A result may explain a conclusion, but the explanation remains derived unless a future accepted specification grants scoped authority.

## Validation Strategy

Validation can check canonical metadata, canonical sections, contiguous requirement identifiers, dependency references, lifecycle-state coverage, deferred-interface boundaries, absence of unresolved placeholders, and consistency between VDP-0002 and the informative lifecycle document.

Future validation may include fixture-driven equivalence tests across implementations.

## Scoring Considerations

Not applicable. The Core Processor Model does not define scoring.

## Security Considerations

Processor execution is security-sensitive because it consumes repository content, manifests, configuration, extensions, schemas, and records that may be malformed, hostile, recursive, stale, or contradictory. The Processor must keep authority boundaries explicit and avoid allowing derived output, caches, extensions, or interface state to become authoritative.

## Performance Considerations

Processors should bound artifact loading, graph construction, recursion, derived result size, extension handling, and validation work. Performance optimizations such as caches and indexes are allowed only as derived aids and must not replace authoritative input validation.

## Compatibility

This draft supports future concrete interfaces by defining the abstract model only. Older Processors should preserve and report unsupported future specifications or capabilities while continuing supported processing where possible.

## Migration

No current implementation is migrated by this draft. Future CLI, MCP, hosted, IDE, library, and validator implementations should align their execution model with VDP-0002 before claiming processor conformance.

## Extensibility

Future VDPs may define diagnostics, concrete interfaces, JSON result formats, manifest schema, capability negotiation, extension protocol, validator interface, fixture format, and conformance profiles. Those extensions must preserve the Processor authority boundary unless explicitly amended by accepted specification.

## Alternatives Considered

- Define Processor as a CLI: rejected because Veridion needs one model across interfaces.
- Define Processor as a validator: rejected because validation is one lifecycle state, not the whole model.
- Let each interface define its own lifecycle: rejected because it would fragment conformance and determinism.
- Make Processing Results authoritative: rejected because VDP--001 and VDP-0000 preserve human and artifact authority boundaries.
- Define diagnostics and JSON now: deferred to keep this VDP focused on the abstract execution model.

## Open Questions

- What diagnostics format should future VDPs define?
- What concrete capability model should processors advertise?
- How should Processor conformance fixtures be represented?
- Which concrete interface should be specified first: CLI, MCP, hosted API, or validator?
- How should extension isolation be specified?

## Future Work

- Define diagnostics model and identifiers.
- Define concrete Processor Result serialization.
- Define CLI invocation semantics.
- Define MCP resource and tool semantics.
- Define extension protocol and isolation rules.
- Define validator interface and conformance fixtures.
- Define capability advertisement and negotiation.

## References

- VDP--001: Specification Specification.
- VDP-0000: Veridion Constitution.
- VDP-0001: Repository Discovery and Canonical Layout.
- `docs/processor/PROCESSOR-LIFECYCLE.md`.

## Appendices

### Appendix A: Lifecycle State Summary

| State | Purpose | Terminal |
| --- | --- | --- |
| Created | Initialize session. | No |
| Repository Discovery | Discover repository root, identity, and readiness. | No |
| Bootstrap | Establish processing environment and supported features. | No |
| Context Loading | Load declared context and authoritative inputs. | No |
| Specification Loading | Load accepted specifications and dependencies. | No |
| Normalization | Build derived internal model. | No |
| Semantic Processing | Evaluate semantic relationships. | No |
| Validation | Evaluate supported validation constraints. | No |
| Rule Evaluation | Evaluate supported rules within capability boundary. | No |
| Derived Result Generation | Assemble derived Processing Result. | No |
| Completed | Successful terminal state. | Yes |
| Cancelled | Cancelled terminal state. | Yes |
| Failed | Failed terminal state. | Yes |
