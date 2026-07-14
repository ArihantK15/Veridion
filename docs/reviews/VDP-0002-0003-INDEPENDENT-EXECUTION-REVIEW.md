---
title: VDP-0002 and VDP-0003 Independent Execution Review
purpose: Record an independent architectural review of the joint Processor execution architecture.
status: Review Artefact
owner: Arihant Kaul
related_documents:
  - ../../constitution/VDP-0002-Core-Processor-Model.md
  - ../../constitution/VDP-0003-Processing-Context-and-Capability-Model.md
  - ../processor/PROCESSOR-LIFECYCLE.md
  - ../processor/PROCESSING-CONTEXT.md
  - ../processor/CAPABILITY-MODEL.md
last_updated: "2026-07-14"
---

# VDP-0002 and VDP-0003 Independent Execution Review

This is an independent architectural review of VDP-0002 and VDP-0003 as a joint execution architecture. It is not an implementation review, style review, proofreading pass, or self-review.

## Executive Summary

VDP-0002 and VDP-0003 establish a strong architectural foundation: Processor authority is bounded, discovery is separated from processing, Processor outputs remain derived, Context and Environment are distinct, capabilities are negotiated before processing, and profiles compose capabilities rather than introducing new behavior.

However, the pair is not yet ready for acceptance audit. One blocking lifecycle contradiction remains between VDP-0002 and VDP-0003: VDP-0002 models Bootstrap and Context Loading as mandatory Processing Session states, while VDP-0003 states that the VDP-0002 Processing Session begins only after Processing Context is frozen. An independent implementation cannot know whether session creation occurs before or after Context construction.

Final recommendation: NOT READY.

## Architecture Assessment

The intended architecture is clear at a high level:

1. VDP-0001 repository discovery produces a Discovered Repository Result.
2. VDP-0003 pre-session negotiation consumes Processor Descriptor and Processing Request.
3. Negotiation Result supports Processing Context construction.
4. Processing Context is frozen.
5. VDP-0002 Processor execution produces a derived Processing Result.

The authority model is sound. The Processor is not a CLI, validator, MCP server, hosted service, IDE, library, or agent, and those concrete surfaces do not become authoritative. Raw Processor output remains derived unless separately incorporated into an authoritative artifact through human or governance process.

The execution architecture needs one boundary correction before independent implementations can safely converge.

## Cross-Document Consistency

VDP-0002 and VDP-0003 agree on these points:

- VDP-0001 owns repository discovery.
- Processor execution consumes a discovered repository representation.
- Processor output is derived.
- Context and Execution Environment are separate.
- Capability and profile semantics are part of VDP-0003 rather than VDP-0002.
- Diagnostics, concrete interfaces, manifest schema, serialization, and extension wire protocol remain deferred.

Primary inconsistency:

- VDP-0002 defines the Processing Session as having one Context and includes Created, Bootstrap, Context Loading, and Context freeze inside the Processor lifecycle.
- VDP-0003 defines Processor Descriptor, Processing Request, Negotiation Result, Context construction, and Context freeze as pre-session work, then states that the VDP-0002 Processing Session begins only after Context is frozen.

## Dependency Analysis

The dependency order is coherent:

- VDP-0002 depends on VDP--001, VDP-0000, and VDP-0001.
- VDP-0003 depends on VDP--001, VDP-0000, VDP-0001, and VDP-0002.
- VDP-0003 does not redefine repository discovery.
- VDP-0003 does not redefine Processor authority.

The dependency edge from VDP-0003 to VDP-0002 is currently strained only by session-boundary language.

## Authority Analysis

Authority boundaries are mostly strong:

- Processor outputs remain derived.
- Processor Descriptors are non-authoritative.
- Capability lifecycle authority must derive from accepted specifications, accepted records, valid extension declarations under an accepted extension model, or another explicitly authorized artifact.
- Implementation-declared lifecycle claims are non-authoritative.
- Policies cannot override the Constitution, accepted VDPs generally, capability semantics, lifecycle rules, or derived-output boundaries.

Remaining risk is not an authority escalation risk; it is a reproducibility and implementation-boundary risk.

## Determinism Analysis

The determinism model is directionally adequate. VDP-0002 scopes equivalent results to equivalent discovered repository result, accepted specification set, Processing Context, operation or profile, capability identifiers and versions, policies, configuration, declared external inputs, and compatible resource-limit outcomes. VDP-0003 adds Processor Descriptor, Processing Request, Negotiation Result, lifecycle authority sources, dependency closure, profile identity, and Context identity.

The unresolved session-boundary contradiction weakens determinism because two implementations could choose different freeze points and both plausibly claim conformance.

## Security Analysis

The specifications identify the important security classes:

- context injection;
- environment injection;
- capability spoofing;
- profile spoofing and escalation;
- namespace collisions;
- malicious extensions;
- policy bypass;
- dependency closure omissions;
- lifecycle spoofing;
- resource exhaustion;
- interruption and partial processing.

The security model is suitable for Draft review. No additional security blocker was found beyond the session-boundary issue, because that boundary affects reproducibility and auditability of security-sensitive conclusions.

## Forward Compatibility

Forward compatibility is well-handled for Draft maturity:

- unknown capabilities and namespaces are preserved and reported;
- unknown future specifications are not silently reinterpreted;
- removed capabilities require accepted compatibility rules for legacy handling;
- profile and capability registries remain deferred;
- concrete serialization and interface protocols remain deferred.

The deferred items are appropriate as long as future VDPs define registries, diagnostics, manifest integration, and extension protocols before implementation conformance claims become stable.

## Implementation Feasibility

Thought experiment:

- A Rust CLI can perform discovery, negotiate capabilities locally, freeze Context, run a Processor, and print derived results.
- A hosted SaaS can perform the same semantic steps behind an API, provided hosted state is not silently treated as Context.
- An MCP server can expose Processor-derived resources without treating MCP responses as authoritative.

All three can become semantically equivalent after the session-boundary contradiction is resolved. Before that correction, one implementation may treat Bootstrap and Context Loading as inside the Processing Session, while another may treat the Processing Session as beginning after Context freeze.

## Findings

### VDP0002-0003-REVIEW-BLOCKING-001 — Processing Session boundary is contradictory

Classification: Blocking

Affected VDP: VDP-0002 and VDP-0003

Affected requirements:

- VDP-0002-REQ-013
- VDP-0002-REQ-021
- VDP-0002-REQ-025
- VDP-0002-REQ-026
- VDP-0002-REQ-033
- VDP-0002-REQ-034
- VDP-0002-REQ-102
- VDP-0003-REQ-001
- VDP-0003-REQ-014
- VDP-0003-REQ-098
- VDP-0003-REQ-106

Architectural impact:

VDP-0002 requires a Processing Session to have exactly one Context and includes Bootstrap and Context Loading as mandatory orderly states. VDP-0003 requires negotiation and Context construction before the VDP-0002 Processing Session begins. The supporting lifecycle document also shows "Processing Session created" before "Context frozen."

An independent implementation cannot determine whether Bootstrap and Context Loading are pre-session orchestration or in-session lifecycle states. This affects lifecycle traces, Context identity, result provenance, interruption handling, determinism, conformance tests, and security auditability.

Recommended correction:

Choose exactly one model and align both VDPs and supporting lifecycle documentation:

- Model A: Processing Session begins before Bootstrap, and Context becomes frozen inside the session.
- Model B: Processing Session begins only after Context freeze, and Bootstrap / Context Loading are pre-session orchestration rather than Processor lifecycle states.

Then update mandatory lifecycle requirements, Context freeze rules, Result Contract language, and lifecycle diagrams accordingly.

### VDP0002-0003-REVIEW-MAJOR-001 — Processor Descriptor identity is not sufficiently reproducible

Classification: Major

Affected VDP: VDP-0003

Affected requirements:

- VDP-0003-REQ-099
- VDP-0003-REQ-102
- VDP-0003-REQ-106

Architectural impact:

The Processor Descriptor may identify "Processor identity or implementation identity," but the minimum stable identity or provenance needed for reproducibility is not stated. Two implementations could emit descriptors with names only, build hashes only, vendor labels only, or transient service identifiers and still claim compliance.

Recommended correction:

Define minimum semantic identity/provenance obligations for Processor Descriptor without requiring a concrete encoding. The descriptor should be sufficient to distinguish implementation family, implementation revision or equivalent provenance, supported specification versions, capability versions, material limitations, environment assumptions, and extension boundary used for the session.

### VDP0002-0003-REVIEW-MAJOR-002 — Lifecycle authority depends on future artifacts without an interim failure rule

Classification: Major

Affected VDP: VDP-0003

Affected requirements:

- VDP-0003-REQ-033 through VDP-0003-REQ-040
- VDP-0003-REQ-103 through VDP-0003-REQ-105

Architectural impact:

VDP-0003 correctly prevents Processors from self-authoring lifecycle maturity. It allows authoritative lifecycle status to come from future accepted registries, records, extension declarations, or other accepted artifacts. Until those artifacts exist, independent implementations may disagree on whether lifecycle status is unknown, implementation-declared, unavailable, or non-authoritative.

Recommended correction:

Add an interim rule: when no authoritative lifecycle source exists, the lifecycle authority state is absent or implementation-declared non-authoritative, and negotiation must report that limitation rather than implying authoritative maturity.

### VDP0002-0003-REVIEW-MAJOR-003 — Policy authority lacks conflict precedence inside the negotiation model

Classification: Major

Affected VDP: VDP-0003

Affected requirements:

- VDP-0003-REQ-006
- VDP-0003-REQ-067
- VDP-0003-REQ-068
- VDP-0003-REQ-090

Architectural impact:

VDP-0003 says policies may affect processing only within explicitly granted authority and cannot override higher authority. It does not define how negotiation reports conflicts between a policy, Processing Request, profile definition, capability definition, extension declaration, and accepted specification when the policy is partially in scope and partially out of scope.

Recommended correction:

Define a minimal conflict precedence rule: accepted specifications and valid governance records govern policy scope; out-of-scope policy effects must be reported and ignored for normative conclusions; in-scope policy effects must be captured in Context and Negotiation Result.

### VDP0002-0003-REVIEW-MINOR-001 — Lifecycle documentation is stale relative to VDP-0003

Classification: Minor

Affected VDP: Supporting documentation for VDP-0002 and VDP-0003

Affected requirements:

- VDP-0002-REQ-033
- VDP-0002-REQ-034
- VDP-0003-REQ-098

Architectural impact:

`docs/processor/PROCESSOR-LIFECYCLE.md` still shows session creation before Context freeze and does not include Processor Descriptor, Processing Request, or Negotiation Result in the lifecycle diagram. Because the document is informative, this is not independently blocking, but it reinforces the blocking contradiction.

Recommended correction:

Update the lifecycle support document after resolving the normative session-boundary model.

### VDP0002-0003-REVIEW-MINOR-002 — Availability status examples are not clearly open or closed

Classification: Minor

Affected VDP: VDP-0003

Affected requirements:

- VDP-0003-REQ-054
- VDP-0003-REQ-102

Architectural impact:

VDP-0003 lists availability states such as available, blocked by policy, unavailable in environment, dependency unsatisfied, version incompatible, and deferred. It also says no serialization is defined. It is not explicit whether these are the complete semantic states for Version 0.1.0 or examples.

Recommended correction:

State whether the availability-status set is closed for the specification revision or illustrative pending a future diagnostics/result-contract VDP.

### VDP0002-0003-REVIEW-OBSERVATION-001 — Deferral boundaries are mostly clean

Classification: Observation

Affected VDP: VDP-0002 and VDP-0003

Affected requirements:

- VDP-0002-REQ-096 through VDP-0002-REQ-100
- VDP-0003-REQ-093 through VDP-0003-REQ-097

Architectural impact:

Diagnostics, manifest schema, CLI, MCP, HTTP, LSP, validator interface, extension wire protocol, serialization, and repository graph serialization are properly deferred. The specifications avoid leaking wire-format design into the abstract architecture.

Recommended correction:

No correction required.

### VDP0002-0003-REVIEW-OBSERVATION-002 — Authority boundary is strong

Classification: Observation

Affected VDP: VDP-0002 and VDP-0003

Affected requirements:

- VDP-0002-REQ-004 through VDP-0002-REQ-008
- VDP-0002-REQ-062
- VDP-0002-REQ-108
- VDP-0003-REQ-032
- VDP-0003-REQ-075
- VDP-0003-REQ-100

Architectural impact:

The documents consistently prevent Processors, Processor Descriptors, Processing Results, profiles, capabilities, and extensions from becoming authoritative merely through execution or declaration.

Recommended correction:

No correction required.

## Recommendations

1. Resolve the Processing Session boundary contradiction before further dependent specifications are authored.
2. Strengthen Processor Descriptor identity and provenance requirements enough to support reproducibility.
3. Add an interim rule for absent authoritative capability or profile lifecycle sources.
4. Add minimal policy conflict precedence for negotiation.
5. Align `docs/processor/PROCESSOR-LIFECYCLE.md` after the normative session-boundary correction.

## Overall Rating

NOT READY.

The architecture is close, but the session-boundary contradiction is foundational. It affects lifecycle conformance, Context identity, Result provenance, deterministic equivalence, and implementation thought experiments across CLI, hosted, and MCP surfaces.

## Readiness Assessment

Blocking findings: 1

Major findings: 3

Minor findings: 2

Observations: 2

Final recommendation: NOT READY.

The specifications should not enter acceptance audit until the blocking Processing Session boundary issue is corrected. After that correction, the remaining Major findings are likely narrow and resolvable without redesigning the architecture.
