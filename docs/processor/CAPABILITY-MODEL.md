---
title: Capability Model
purpose: Provide informative guidance for VDP-0003 capability and profile semantics.
status: Draft
owner: Arihant Kaul
related_documents:
  - ../../constitution/VDP-0003-Processing-Context-and-Capability-Model.md
  - ../../constitution/VDP-0002-Core-Processor-Model.md
last_updated: "2026-07-14"
---

# Capability Model

This document is informative. VDP-0003 is authoritative.

## Purpose

Capabilities describe what a Processor can do. Negotiation compares a Processor Descriptor, Processing Request, capability definitions, dependencies, policies, environment availability, and versions before Processing Context is constructed. Profiles compose existing capabilities for common processing purposes without introducing new behavior.

## Capability Concepts

A capability is a declared behavior unit. Capabilities may have identifiers, source namespaces, versions, lifecycle status, lifecycle authority sources, dependencies, limitations, implementation support, runtime availability, and negotiation outcomes.

Illustrative capability areas include validation, migration, semantic model, documentation, repository graph, governance, dependency graph, and extension processing.

## Identifier Namespaces

Capability identifiers identify a source namespace or authority class. Semantic categories include core capability, organization-qualified capability, extension-qualified capability, and local experimental capability. Local identifiers are not globally standardized, and namespace ownership is not inferred from repository hosting or popularity.

## Lifecycle

Capability lifecycle states describe maturity, not implementation support:

- Experimental;
- Draft;
- Stable;
- Deprecated;
- Removed.

Capability lifecycle is independent of Processor version. Authoritative lifecycle status derives from Accepted specifications, accepted capability records, valid extension declarations under an accepted extension model, or other explicitly authorized artifacts. When no authoritative lifecycle source exists, authoritative lifecycle is absent or unknown. Processor-declared lifecycle claims are implementation-declared and non-authoritative unless backed by an authoritative source.

## Negotiation

Processors expose a Processor Descriptor. Clients provide a Processing Request. Negotiation produces a Negotiation Result before Context construction.

A Processor Descriptor identifies implementation family or product identity, implementation revision or equivalent provenance, descriptor revision or snapshot identity, supported specifications, supported capabilities, supported profiles, material limitations, environment assumptions, extension boundary, implementation-declared lifecycle claims, and known authoritative lifecycle sources. If the Descriptor changes materially before Context freeze, negotiation restarts or the change is reported.

Negotiation does not collapse status dimensions:

| Dimension | Meaning | Example states |
| --- | --- | --- |
| Support | Whether the implementation claims behavior exists. | supported, partially_supported, unsupported |
| Availability | Whether behavior can execute for this request. | available, blocked_by_policy, unavailable_in_environment, dependency_unsatisfied, version_incompatible, deferred |
| Lifecycle | Maturity of capability or profile. | Experimental, Draft, Stable, Deprecated, Removed |
| Dependency | Required dependency closure state. | satisfied, partially_satisfied, unsatisfied, unknown |

No transport protocol is defined here.

The availability states are a minimum open semantic set, not a closed registry. Future specifications may add more specific categories. Unknown future categories are preserved and reported, and are never silently mapped to available.

## Policy Conflicts

For negotiation scope, policy conflict precedence is: Accepted Constitution, accepted applicable VDPs, valid governance records within granted scope, authoritative capability or profile definitions, valid extension declarations within accepted extension authority, declared repository or organizational policy within granted scope, local request preferences, then implementation defaults.

Out-of-scope policy effects are reported and ignored for normative conclusions. In-scope policy effects are preserved in the Negotiation Result, Context, and Result when they affect execution or interpretation.

## Dependencies

Required dependency closure is resolved before a capability or profile is selected as fully supported. Closure accounts for identifiers, version constraints, transitive dependencies, lifecycle compatibility, support, availability, policy restrictions, and extension requirements. Optional dependencies remain distinct and may reduce functionality without being reported as satisfied required closure.

## Profiles

Profiles compose existing capabilities. Examples include Validation, Migration, Documentation, Governance, Semantic Analysis, and Repository Analysis. A profile does not create behavior outside the capabilities it composes.

A profile has identity, version, source or authority, composed capability identifiers and version constraints, required and optional capabilities, dependency closure, lifecycle status when applicable, limitations, and compatibility expectations. Two profiles with the same display name but different identifiers, versions, sources, or composition are distinct profiles and are not silently merged.

## Non-Implementation Boundary

This document does not define a capability registry, profile registry, manifest schema, diagnostics format, extension wire protocol, CLI, MCP, HTTP, LSP, JSON, hosted API, validator interface, or executable behavior.
