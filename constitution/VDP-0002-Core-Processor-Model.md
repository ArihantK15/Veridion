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

This specification defines processor terminology, session boundaries, lifecycle states, input and output authority, determinism, error classification, forward compatibility, and security constraints. Repository discovery remains owned by VDP-0001 and occurs before Processor lifecycle execution. This specification does not define diagnostics formats, CLI commands, HTTP APIs, MCP resources, LSP behavior, JSON payloads, manifest schemas, extension protocols, validator interfaces, or capability negotiation.

## Motivation

Veridion implementations need a shared execution model before concrete interfaces diverge. Without an abstract Processor model, a CLI, MCP server, hosted platform, and validator could disagree about what counts as input, when repository state is loaded, whether generated output is authoritative, how cancellation behaves, or how unsupported future specifications are handled.

The Processor model gives every implementation a common semantic contract while leaving concrete protocols to future VDPs.

## Goals

- Define the canonical abstract Processor.
- Define Processing, Processing State, Processing Session, Processing Lifecycle, Processing Result, capability boundaries, responsibilities, and non-responsibilities.
- Establish that Processors consume authoritative artifacts and produce derived artifacts.
- Define deterministic lifecycle states and transitions while allowing conditional states to be skipped under explicit rules.
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
- Processing Session: One bounded execution that begins after Context freeze and binds one frozen Context, one Processor execution, one lifecycle, immutable authoritative inputs, and at most one emitted terminal Result.
- Processing Lifecycle: The ordered state machine through which a Processing Session proceeds.
- Processing Result: The derived output of a Processing Session.
- Discovered Repository Result: The derived result produced by applying VDP-0001 repository discovery rules to a candidate location.
- Processing Context: The immutable semantic input to a Processing Session, including the discovered repository result or equivalent discovered repository representation, accepted specification set, declared configuration, policy inputs, supported version declarations, requested operation or profile reference, declared external inputs, and capability boundary.
- Execution Environment: The mutable runtime conditions under which a Processor executes, including filesystem access, network availability, memory, CPU, operating system, sandbox, clock, interactive state, and process limits.
- Context: A shorthand for Processing Context.
- Processor Capability Boundary: The declared feature boundary within which a Processor claims conformance.
- Processor Responsibility: A duty every conforming Processor has within its claimed capability boundary.
- Processor Non-responsibility: A duty explicitly excluded from the abstract Processor model.
- Authoritative input: A repository artifact or record whose authority derives from accepted specifications or valid governance records.
- Derived artifact: Any output created by Processing, including normalized models, graphs, diagnostics references, validation states, and execution metadata.
- Equivalent Processing Result: A result with the same normative meaning, readiness classification, validation conclusions, and material diagnostics, even if presentation differs.

## Background

VDP--001 defines the proposal system and the authority boundary between Markdown specifications, metadata, and derived artifacts. VDP-0000 defines governance authority and prohibits automated systems from exercising constitutional authority. VDP-0001 defines repository discovery, canonical layout, repository identity, and the `VERIDION.yaml` bootstrap manifest concept.

VDP-0002 builds on those specifications by defining what a Processor does after VDP-0001 repository discovery, VDP-0003 pre-session negotiation, Processing Context construction, and Context freeze have produced a valid frozen Processing Context.

## Problem Statement

Every Veridion implementation needs to process repository artifacts consistently. The project needs one abstract execution model that defines what a Processor may read, how it moves through lifecycle states, how it freezes authoritative inputs, how it handles unknown or unsupported content, and what it may output without creating new authority.

Without this model, concrete implementations could silently rely on undefined external state, treat generated summaries as authoritative, mutate repository authority, skip required lifecycle stages, or produce incompatible results from the same repository.

## Proposed Design

The Processor is a deterministic state machine scoped to one Processing Session. The binding conceptual pipeline is: VDP-0001 discovery, Discovered Repository Result, Processor Descriptor, Processing Request, Capability Negotiation, Negotiation Result, Processing Context construction, Context freeze, VDP-0002 Processing Session creation, Processor lifecycle, then Processing Result. A concrete application may expose pre-session orchestration and processing through one command or service, but the conformance boundaries remain distinct.

A session begins only after a valid frozen Processing Context exists. It executes against that frozen Context, conditionally loads or verifies applicable artifacts, normalizes when required, performs applicable semantic processing, validation, and rule evaluation, generates a derived Processing Result when possible, and reaches an orderly terminal classification or is catastrophically interrupted.

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

A Processor MUST produce only derived artifacts and derived conclusions. No raw Processor output becomes authoritative merely because a Processor emitted it.

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

A Processing Session MUST begin only after Processing Context is frozen and MUST bind exactly one frozen Processing Context, one Processor execution, one lifecycle instance, immutable authoritative inputs, and at most one emitted terminal Processing Result.

### VDP-0002-REQ-014 — Processing lifecycle definition

The Processing Lifecycle MUST define the ordered state progression for a Processing Session.

### VDP-0002-REQ-015 — Processing result definition

A Processing Result MUST be the derived output of one Processing Session.

### VDP-0002-REQ-016 — Context definition

Context MUST mean immutable Processing Context and MUST NOT be conflated with mutable Execution Environment conditions.

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

A Processing Session MUST have exactly one frozen Context.

### VDP-0002-REQ-022 — Single lifecycle

A Processing Session MUST have exactly one lifecycle instance.

### VDP-0002-REQ-023 — Single processor

A Processing Session MUST be executed by exactly one Processor instance or one logically equivalent Processor execution.

### VDP-0002-REQ-024 — Single result

A Processing Session that reaches an orderly terminal condition MUST attempt to emit exactly one terminal Processing Result.

### VDP-0002-REQ-025 — Immutable authoritative inputs

Authoritative inputs for a Processing Session MUST already be frozen before session creation and MUST remain immutable for the duration of that session.

### VDP-0002-REQ-026 — Input snapshot

A Processor MUST verify or record at session start the frozen repository and artifact snapshot used for the Processing Session and MUST NOT mutate or replace that snapshot.

### VDP-0002-REQ-027 — Session isolation

State from one Processing Session MUST NOT silently alter the authoritative inputs or conclusions of another session.

### VDP-0002-REQ-028 — External state declaration

Environment-dependent facts that affect Processing Results MUST be captured into Context or reported as limitations, unavailable, unsupported, or non-authoritative.

### VDP-0002-REQ-029 — Undefined state prohibition

A Processor MUST NOT rely on undefined external state when producing conformance, validation, readiness, or authority-related conclusions.

### VDP-0002-REQ-030 — Session metadata

A Processing Result SHOULD include execution metadata sufficient to identify supported features, configuration, input snapshot, lifecycle terminal state, and material limitations.

### Lifecycle States

### VDP-0002-REQ-031 — Created state

The Created state MUST indicate that the Processing Session has been instantiated with one frozen Context and that no conditional Processor state has yet executed.

### VDP-0002-REQ-032 — Discovered repository input

The Processor lifecycle MUST begin only after VDP-0001 discovery has produced a Discovered Repository Result sufficient for the requested operation.

### VDP-0002-REQ-033 — Bootstrap exclusion

Bootstrap MUST be treated as pre-session orchestration and MUST NOT be reported as a Processor lifecycle state.

### VDP-0002-REQ-034 — Context Loading exclusion

Context Loading for Processing Context construction MUST be treated as pre-session orchestration and MUST NOT be reported as a Processor lifecycle state.

### VDP-0002-REQ-035 — Specification Loading state

The Specification Loading state MUST load accepted specifications and applicable dependencies before semantic processing depends on them when that state is required by the requested operation, requested profile, declared capability set, or applicable accepted specifications.

### VDP-0002-REQ-036 — Normalization state

The Normalization state MUST convert loaded inputs into a derived internal model without changing authoritative artifacts when normalization is applicable.

### VDP-0002-REQ-037 — Semantic Processing state

The Semantic Processing state MUST evaluate semantic relationships among loaded artifacts within the Processor capability boundary when semantic processing is applicable.

### VDP-0002-REQ-038 — Validation state

The Validation state MUST evaluate applicable structural, metadata, dependency, lifecycle, and repository constraints supported by the Processor when validation is applicable.

### VDP-0002-REQ-039 — Rule Evaluation state

The Rule Evaluation state MUST evaluate supported normative rules, policies, or conformance checks only within the declared capability boundary when rule evaluation is applicable.

### VDP-0002-REQ-040 — Derived Result Generation state

The Derived Result Generation state MUST assemble the Processing Result from derived models, graph data, validation state, diagnostics references, and execution metadata.

### VDP-0002-REQ-041 — Completed state

The Completed state MUST indicate that processing reached a terminal successful result for the claimed capability boundary.

### VDP-0002-REQ-042 — Cancelled state

The Cancelled state MUST indicate that processing stopped due to caller request, policy, resource limit, or interruption before normal completion.

### VDP-0002-REQ-043 — Failed state

The Failed state MUST indicate that processing reached an orderly terminal failure and MUST preserve available diagnostic context when result emission is possible.

### VDP-0002-REQ-044 — Terminal state exclusivity

A Processing Session that reaches an orderly terminal condition MUST be classified as exactly one logical terminal state: Completed, Cancelled, or Failed.

### VDP-0002-REQ-045 — Deterministic transitions

Every lifecycle transition MUST be deterministic for the same discovered repository result or equivalent repository snapshot, Processing Context, requested operation or profile, capability identifiers and versions, declared policies, configuration, declared external inputs, and compatible resource-limit outcomes.

### Inputs

### VDP-0002-REQ-046 — Repository input

A Processor MUST consume a VDP-0001-conformant Discovered Repository Result or logically equivalent discovered repository representation and MUST NOT invent repository identity, root, copy class, or readiness independently.

### VDP-0002-REQ-047 — Accepted specification input

A Processor MUST treat only validated Accepted specifications as accepted specification input.

### VDP-0002-REQ-048 — Schema input

A Processor MAY read schemas as validation aids but MUST NOT allow schemas to override authoritative Markdown specifications unless accepted specifications grant scoped schema authority.

### VDP-0002-REQ-049 — Governance record input

A Processor MAY read governance records but MUST NOT change governance meaning by processing them.

### VDP-0002-REQ-050 — Review record input

A Processor MAY read review records as evidence or context but MUST NOT treat review presence alone as proposal acceptance.

### VDP-0002-REQ-051 — Extension input

A Processor MAY read extensions only within its capability boundary and only after the Discovered Repository Result and pre-session sufficiency constraints are evaluated.

### VDP-0002-REQ-052 — Configuration input

Configuration used for Processing MUST be included in Context or represented in execution metadata.

### VDP-0002-REQ-053 — No undefined external input

A Processor MUST NOT use network state, local cache state, private memory, environment-specific defaults, hosted metadata, or mutable Execution Environment details as authoritative input unless the Context declares them and accepted specifications permit them.

### VDP-0002-REQ-054 — Input conflict reporting

Conflicting authoritative inputs MUST produce diagnostics or failure rather than silent reconciliation.

### Outputs

### VDP-0002-REQ-055 — Processing result output

A Processor MUST attempt to produce a Processing Result for an orderly terminal condition.

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

Two conforming Processors with the same discovered repository result or equivalent repository snapshot, accepted specification set and versions, Processing Context, requested operation or profile, capability identifiers and versions, declared policies, configuration, declared external inputs, compatible resource-limit outcomes, and no accepted specification permitting variation MUST produce equivalent Processing Results.

### VDP-0002-REQ-064 — Presentation independence

Equivalent Processing Results MAY differ in presentation, ordering of non-semantic fields, rendering, transport encoding, and interface-specific packaging.

### VDP-0002-REQ-065 — Material conclusion stability

Validation conclusions, readiness classifications, dependency relationships, and material diagnostics MUST remain equivalent within the shared capability subset under equivalent inputs.

### VDP-0002-REQ-066 — Variation disclosure

Permitted variation, including capability-set variation, MUST be disclosed in execution metadata or diagnostics when it affects interpretation.

### VDP-0002-REQ-067 — Non-determinism prohibition

A Processor MUST NOT use randomness, wall-clock time, network availability, machine identity, locale, private memory, cache state, or mutable Execution Environment details to change normative conclusions unless they are explicitly captured as declared input, an accepted specification allows them, and the Processing Result discloses their effect.

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

Interrupted processing MUST produce a Cancelled or Failed terminal result with available diagnostics when feasible, but catastrophic interruption MAY prevent result emission.

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

Bootstrap poisoning attempts MUST be reported when the Discovered Repository Result, configuration, environment-derived inputs, or extension data conflicts with authoritative records.

### VDP-0002-REQ-087 — Security portability

Processor security requirements MUST NOT depend on a specific operating system, filesystem, forge, runtime, or hosting platform.

### Failure Scenarios

### VDP-0002-REQ-088 — Repository mutation during processing

If repository state changes during Processing after the input snapshot is frozen, the Processor MUST continue against the frozen snapshot or terminate with diagnostics and MUST NOT silently switch snapshots.

### VDP-0002-REQ-089 — Specification superseded during processing

If a specification is superseded during Processing, the current session MUST continue with its immutable input snapshot or fail with diagnostics.

### VDP-0002-REQ-090 — Invalid context

Invalid Context MUST prevent successful completion for operations that depend on that Context.

### VDP-0002-REQ-091 — Processing cancellation

Cancellation MUST lead to the Cancelled state unless the Processor has already reached Completed or Failed or catastrophic interruption prevents terminal classification.

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

### Boundary Corrections

### VDP-0002-REQ-101 — Discovery boundary

Repository discovery MUST occur under VDP-0001 before Processor lifecycle execution, and discovery failures MUST remain discovery-phase outcomes unless the requested operation explicitly permits processing a partial discovered repository result.

### VDP-0002-REQ-102 — Mandatory lifecycle states

Every orderly Processing Session MUST include Created, Derived Result Generation when result emission is possible, and exactly one orderly terminal classification.

### VDP-0002-REQ-103 — Conditional lifecycle states

Specification Loading, Normalization, Semantic Processing, Validation, and Rule Evaluation MUST be treated as conditional states executed only when required by the requested operation, requested profile, declared capability set, or applicable accepted specifications.

### VDP-0002-REQ-104 — Skipped state recording

A Processing Result MUST record which states executed, which conditional states were skipped, why each state was skipped, and which states were not reached.

### VDP-0002-REQ-105 — Valid transition reporting

State transitions MUST be valid under the lifecycle model; implementations MAY combine internal execution steps, but externally reported state semantics MUST remain equivalent and skipped conditional states MUST NOT be falsely reported as successfully completed.

### VDP-0002-REQ-106 — Catastrophic interruption

Catastrophic interruption MAY prevent terminal Processing Result emission, and absence of a result MUST NOT be interpreted as success, cancellation, failure evidence, or conformance evidence.

### VDP-0002-REQ-107 — External interruption records

A caller or orchestrator MAY record an external interruption record after catastrophic interruption, but later recovery MUST NOT fabricate a Processor Result that was never emitted.

### VDP-0002-REQ-108 — Authority incorporation boundary

Processor output MAY be used as evidence or as proposed source changes, migration candidates, normalized representations, reports, evidence packages, generated documentation, suggested governance records, candidate manifests, or validation conclusions, but it becomes part of an authoritative artifact only after authorized human or governance process, explicit reviewable incorporation, provenance preservation, and satisfaction of applicable lifecycle or repository rules.

### VDP-0002-REQ-109 — Pre-session orchestration boundary

Repository discovery, Processor Descriptor construction or retrieval, Processing Request construction, capability negotiation, Negotiation Result creation, Processing Context construction, Context identity assignment, Context freeze, and the decision whether a request is sufficient to create a session MUST be treated as pre-session orchestration.

### VDP-0002-REQ-110 — No session on pre-session failure

Failures during discovery, negotiation, Context construction, or Context freeze MUST NOT produce a VDP-0002 Processing Result because no Processing Session exists.

### VDP-0002-REQ-111 — Combined-interface separation

A CLI, hosted service, MCP server, IDE, library, or other concrete implementation MAY expose pre-session orchestration and Processing Session execution through one operation, but it MUST preserve separate semantic records, separate failure ownership, separate conformance claims, and clear identification of whether a session was created.

## Informative Notes

The Processor is the shared semantic center beneath future Veridion implementations. A concrete CLI may invoke VDP-0001 discovery and then invoke a Processor. An MCP server may expose Processor-derived resources. A hosted platform may render Processing Results. None of those interfaces changes the abstract authority boundary.

## Architecture

The model has four layers:

1. VDP-0001 repository discovery outside the Processor lifecycle.
2. VDP-0003 pre-session negotiation and Context construction.
3. Frozen Processing Context consumed by Processing Session creation.
4. Processor lifecycle state machine with mandatory and conditional states.
5. Derived Processing Result consumed by concrete interfaces.

Concrete implementations may split these layers across processes, services, libraries, or workers, but claimed conformance is measured against the abstract model.

## Interfaces

This draft defines no concrete interface. It defines semantic expectations for any future interface that invokes a Processor:

- the caller provides or selects a candidate location;
- VDP-0001 repository discovery produces a Discovered Repository Result;
- VDP-0003 pre-session orchestration freezes Processing Context;
- the Processor consumes the frozen Context;
- the Processor executes one lifecycle;
- the Processor attempts to return one Processing Result for orderly terminal conditions;
- the interface renders, transports, stores, or summarizes the derived result without making it authoritative.

## Algorithms

Processor lifecycle pseudocode:

```text
create session
enter Created
if required: enter Specification Loading
if required: enter Normalization
if required: enter Semantic Processing
if required: enter Validation
if required: enter Rule Evaluation
enter Derived Result Generation
if successful:
  enter Completed
else if cancelled:
  enter Cancelled
else:
  enter Failed
return Processing Result
```

Catastrophic interruption, such as host termination, power loss, process crash, fatal runtime failure, unrecoverable memory exhaustion, or loss of execution environment, may prevent the final `return Processing Result` step.

Transitions are deterministic for the same frozen Processing Context and compatible in-session resource-limit outcomes.

## Evidence Requirements

Evidence for Processor conformance includes lifecycle traces, input snapshots, supported feature declarations, configuration records, Processing Results, diagnostics references, validation outcomes, and examples showing handling of unsupported, partial, cancelled, and failed processing.

## Reasoning Requirements

Processors should distinguish authoritative inputs, derived models, diagnostics, assumptions, Execution Environment limitations, and interface presentation. A result may explain a conclusion, but the explanation remains derived and does not become authority automatically.

## Validation Strategy

Validation can check canonical metadata, canonical sections, contiguous requirement identifiers, dependency references, lifecycle-state coverage, skipped-state semantics, terminal result boundaries, deferred-interface boundaries, absence of unresolved placeholders, and consistency between VDP-0002 and the informative lifecycle document.

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

Future VDPs may define diagnostics, concrete interfaces, JSON result formats, manifest schema, capability negotiation, extension protocol, validator interface, fixture format, Processing Context schema, Execution Environment schema, and conformance profiles. Those extensions must preserve the Processor authority boundary.

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
| Created | Session instantiated with frozen Context. | No |
| Specification Loading | Load accepted specifications and dependencies when required. | No |
| Normalization | Build derived internal model when required. | No |
| Semantic Processing | Evaluate semantic relationships when required. | No |
| Validation | Evaluate supported validation constraints when required. | No |
| Rule Evaluation | Evaluate supported rules within capability boundary when required. | No |
| Derived Result Generation | Assemble derived Processing Result. | No |
| Completed | Successful terminal state. | Yes |
| Cancelled | Cancelled terminal state. | Yes |
| Failed | Failed terminal state. | Yes |
