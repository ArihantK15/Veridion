---
identifier: VDP-0001
title: Repository Discovery and Canonical Layout
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
supersedes: []
superseded_by: null
category: repository
tags:
  - repository-discovery
  - canonical-layout
  - bootstrap
  - manifest
---

# Repository Discovery and Canonical Layout

## Abstract

VDP-0001 defines how Veridion repositories are discovered, identified, validated, and navigated. It establishes repository identity as independent from hosting location, defines repository copy classes, introduces the `VERIDION.yaml` bootstrap manifest, assigns constitutional meaning to canonical directories, and specifies a deterministic bootstrap algorithm for humans, CLIs, MCP servers, IDE extensions, hosted platforms, validators, automation, AI agents, and third-party implementations.

This specification does not implement repository scanning, does not define a Git protocol, does not create a CLI or MCP interface, and does not make generated artifacts authoritative.

## Motivation

Veridion is intended to support many implementations and deployment environments. Without common repository semantics, each processor could discover different roots, trust different files, misidentify forks or mirrors, confuse generated indexes with authoritative artifacts, or apply different rules to partial and offline copies.

A stable repository discovery specification gives every implementation the same starting point. It lets a local CLI, an MCP server, a hosted validator, an IDE extension, and an independent implementation agree on what repository they are inspecting before they interpret specifications, governance records, schemas, diagnostics, extensions, or derived artifacts.

## Goals

- Define repository identity independently from URLs, forges, filesystem paths, and ownership names.
- Define copy classes including canonical repositories, official mirrors, archives, forks, working copies, temporary clones, offline copies, and untrusted copies.
- Introduce `VERIDION.yaml` as the minimum machine bootstrap point without over-designing every future manifest field.
- Define a deterministic discovery and validation algorithm that never guesses.
- Assign semantic responsibility to canonical directories.
- Define repository graph relationships beyond folder names.
- Define repository conformance classes and capability advertisement.
- Handle nested repositories, monorepos, submodules, worktrees, vendor copies, archives, and read-only snapshots.
- Define migration, mirror promotion, ownership transfer, and recovery semantics.
- Protect authoritative artifacts from generated indexes, embeddings, caches, AI summaries, and stale derived data.
- Address repository security concerns that are not limited to Git.
- Preserve forward compatibility for future fields, capabilities, directories, and specifications.

## Non Goals

- Implement `VERIDION.yaml`.
- Define every future manifest field.
- Implement repository scanning, validation, CLI behavior, MCP behavior, IDE behavior, or hosted behavior.
- Define a Git specification or filesystem tutorial.
- Create repository UUID generation, cryptographic signatures, diagnostics registries, or certification programs.
- Change VDP--001 or VDP-0000.
- Define product scoring, prompt behavior, review behavior, or framework analysis behavior.
- Begin VDP-0002.

## Terminology

- Repository identity: The stable identity of a Veridion repository independent from current location.
- Repository location: A mutable path, URL, forge location, storage location, archive location, or transport location where repository content is found.
- Canonical Repository: The repository location designated by valid governance records as the current authoritative source location.
- Official Mirror: A repository copy designated by valid governance records for availability or preservation without independent canonical authority.
- Archive: A preserved repository state intended for historical inspection or recovery.
- Working Copy: A local checkout or copy used for ordinary reading, editing, validation, or development.
- Fork: A divergent repository lineage that may share history but does not automatically inherit canonical status.
- Temporary Clone: A short-lived copy used for validation, build, review, automation, or inspection.
- Offline Copy: A copy inspected without network access.
- Untrusted Copy: A copy whose provenance, integrity, or authority has not been established.
- Repository root: The directory that contains the active `VERIDION.yaml` manifest for the discovered repository.
- Bootstrap manifest: The `VERIDION.yaml` file used as the machine bootstrap point.
- Repository graph: The semantic relationships among specifications, reviews, records, decisions, implementations, derived artifacts, schemas, diagnostics, and extensions.
- Authoritative artifact: A repository artifact that an accepted specification or governance record makes authoritative for a defined purpose.
- Derived artifact: An artifact generated from authoritative artifacts or repository state without independent authority.
- Processor: Any tool, implementation, hosted service, agent, automation, validator, or extension that reads or evaluates a Veridion repository.

## Background

VDP--001 defines the proposal system and is Accepted. VDP-0000 exists as the Draft Constitution and defines governance concepts including canonical repository, official mirror, archive, authority transfer, governance records, repository portability, and recovery. VDP-0001 depends on those foundations and applies them to repository discovery and layout.

## Problem Statement

Given any Veridion repository anywhere in the world, every implementation must discover the same repository root, identify the same repository identity, classify the same copy type, validate the same minimum layout, locate the same constitutional and specification artifacts, and report the same readiness state without guessing.

Without this specification, processors may make incompatible assumptions about root selection, manifest authority, repository migration, mirror trust, fork claims, partial archives, generated indexes, or future extensions.

## Proposed Design

VDP-0001 defines a manifest-first repository model. A Veridion repository is discovered by locating `VERIDION.yaml`, validating the manifest as the bootstrap artifact, and then validating the repository layout and graph relationships described by accepted specifications and governance records.

Repository identity is immutable once established by valid repository records. Repository location is mutable and may change through rename, URL change, hosting migration, ownership transfer, canonical migration, mirror promotion, or archival process. Processors distinguish identity from location and must not treat a forge URL, filesystem path, or repository name as the repository identity.

The canonical layout assigns meaning to directories but does not make folder presence alone authoritative. Processors navigate semantic relationships: Constitution to Accepted VDPs, Accepted VDPs to reviews and acceptance records, decisions to implementations, implementations to derived artifacts, and diagnostics to evidence. Unknown directories and future fields are preserved and ignored safely unless an accepted specification grants them meaning.

## Normative Requirements

### Repository Identity

### VDP-0001-REQ-001 — Stable repository identity

A Veridion repository MUST have a repository identity that is distinct from its current location, hosting provider, filesystem path, repository name, owner name, or URL.

### VDP-0001-REQ-002 — Identity survival

Repository identity MUST survive hosting migration, repository rename, ownership transfer, mirror creation, archive creation, and local cloning.

### VDP-0001-REQ-003 — Location mutability

Repository location MUST be treated as mutable metadata and MUST NOT be used as the sole repository identity.

### VDP-0001-REQ-004 — No forge supremacy

No repository forge, including GitHub, GitLab, or a hosted Veridion service, MAY be treated as inherently authoritative by repository discovery alone.

### VDP-0001-REQ-005 — Identity evidence

A processor MUST establish repository identity from the bootstrap manifest and valid repository records before making canonicality claims.

### VDP-0001-REQ-006 — Unknown identity state

If repository identity cannot be established, a processor MUST classify the copy as untrusted or partial instead of inventing an identity.

### VDP-0001-REQ-007 — Fork identity

A fork MUST NOT claim canonical repository identity unless valid governance or recovery records establish canonical migration, authority transfer, or mirror promotion.

### VDP-0001-REQ-008 — Mirror identity

An official mirror MAY share the same repository identity as the canonical repository, but it MUST disclose mirror status and MUST NOT claim independent canonical authority.

### VDP-0001-REQ-009 — Archive identity

An archive MAY preserve repository identity for historical inspection when provenance and archived revision records are available.

### VDP-0001-REQ-010 — Spoofing resistance

Processors MUST treat self-declared identity claims as insufficient when provenance, canonical records, or governance records conflict with those claims.

### Repository Copy Classes

### VDP-0001-REQ-011 — Canonical repository definition

A Canonical Repository MUST be the repository location currently designated by valid governance records as authoritative for current Veridion source state.

### VDP-0001-REQ-012 — Official mirror definition

An Official Mirror MUST be a repository copy designated by valid governance records for availability, redundancy, preservation, or recovery without becoming independently authoritative.

### VDP-0001-REQ-013 — Archive definition

An Archive MUST be a preserved repository state intended for historical inspection, continuity, recovery, or evidence preservation.

### VDP-0001-REQ-014 — Working copy definition

A Working Copy MUST be a local repository copy used for ordinary reading, editing, development, validation, or review.

### VDP-0001-REQ-015 — Fork definition

A Fork MUST be a repository lineage or copy that may derive from Veridion history but is not canonical unless valid governance or recovery records grant canonical status.

### VDP-0001-REQ-016 — Temporary clone definition

A Temporary Clone MUST be a short-lived repository copy used for automation, validation, review, build, analysis, or inspection.

### VDP-0001-REQ-017 — Offline copy definition

An Offline Copy MUST be a repository copy inspected without requiring network access.

### VDP-0001-REQ-018 — Untrusted copy definition

An Untrusted Copy MUST be a repository copy whose provenance, identity, canonicality, or integrity has not been established.

### VDP-0001-REQ-019 — Copy class reporting

Processors SHOULD report the discovered copy class when presenting repository readiness or conformance diagnostics.

### Repository Manifest

### VDP-0001-REQ-020 — Bootstrap manifest filename

The repository bootstrap manifest filename MUST be `VERIDION.yaml`.

### VDP-0001-REQ-021 — Manifest role

`VERIDION.yaml` MUST be the machine bootstrap point for repository discovery, identity establishment, minimum metadata, capability advertisement, and layout discovery.

### VDP-0001-REQ-022 — Manifest authority boundary

The manifest MUST NOT override the Accepted Constitution, Accepted VDPs, valid governance records, or accepted repository recovery records.

### VDP-0001-REQ-023 — Minimum manifest metadata

The manifest MUST provide enough metadata to identify the repository, declare the manifest format version, locate constitutional artifacts, locate accepted specifications, and advertise repository capabilities.

### VDP-0001-REQ-024 — Manifest versioning

The manifest MUST declare a manifest format version, and processors MUST NOT silently interpret unsupported future manifest versions as supported versions.

### VDP-0001-REQ-025 — Manifest extensibility

The manifest MUST allow future extension fields or namespaces without requiring older processors to assign meaning to unsupported fields.

### VDP-0001-REQ-026 — Reserved namespaces

Future manifest namespaces for governance, schemas, diagnostics, extensions, capabilities, signatures, hosted services, MCP, CLI, validation, and provenance are reserved for accepted specifications.

### VDP-0001-REQ-027 — Manifest and filesystem

Manifest paths MUST be interpreted relative to the repository root unless an accepted specification defines another path-resolution rule.

### VDP-0001-REQ-028 — Manifest and Constitution

The manifest MUST identify where the Constitution is expected to be found, but constitutional authority MUST derive from the Accepted Constitution and valid records, not from manifest assertion alone.

### VDP-0001-REQ-029 — Manifest and accepted VDPs

The manifest MAY provide indexes or locations for Accepted VDPs, but processors MUST validate discovered VDP metadata and lifecycle state before treating a proposal as accepted.

### VDP-0001-REQ-030 — Manifest and schemas

The manifest MAY identify schema locations, but schema files MUST NOT override the authoritative Markdown VDPs unless an accepted specification grants schema authority for a defined purpose.

### VDP-0001-REQ-031 — Manifest diagnostics

Processors SHOULD produce diagnostics when the manifest is missing, duplicated, malformed, unsupported, inconsistent with repository records, or inconsistent with canonical layout.

### Discovery and Bootstrap Algorithm

### VDP-0001-REQ-032 — Deterministic discovery

Repository discovery MUST be deterministic for the same input path, repository state, processor version, and supported capability set.

### VDP-0001-REQ-033 — No guessing

Processors MUST NOT guess repository identity, canonicality, governance status, accepted proposal status, or layout validity when required evidence is missing or contradictory.

### VDP-0001-REQ-034 — Root location

Processors MUST locate the repository root by finding the nearest valid `VERIDION.yaml` according to the discovery algorithm.

### VDP-0001-REQ-035 — Manifest validation before trust

Processors MUST validate the manifest before using manifest-declared paths, capabilities, or repository metadata as trusted discovery inputs.

### VDP-0001-REQ-036 — Layout validation

Processors MUST validate required canonical directories before claiming repository layout conformance.

### VDP-0001-REQ-037 — Constitution discovery

Processors MUST locate VDP-0000 through manifest and layout rules before making constitutional authority claims.

### VDP-0001-REQ-038 — Accepted specification discovery

Processors MUST discover Accepted VDPs by validating VDP metadata and lifecycle state rather than by filename pattern alone.

### VDP-0001-REQ-039 — Schema discovery

Processors SHOULD discover schema files through manifest references and canonical layout, while preserving schema authority boundaries.

### VDP-0001-REQ-040 — Governance discovery

Processors SHOULD discover governance records through manifest references, canonical layout, and accepted governance specifications.

### VDP-0001-REQ-041 — Review discovery

Processors SHOULD discover review artifacts through canonical review locations and references from related specifications or records.

### VDP-0001-REQ-042 — Record discovery

Processors SHOULD discover acceptance, decision, migration, recovery, authority, and provenance records before making readiness or canonicality claims.

### VDP-0001-REQ-043 — Extension discovery

Processors MAY discover extensions only after core manifest and layout validation have succeeded or produced a partial-readiness state.

### VDP-0001-REQ-044 — Readiness classification

Processors MUST classify repository readiness as ready, partial, unsupported, or untrusted using explicit diagnostics.

### VDP-0001-REQ-045 — Offline operation

Processors MUST support offline inspection of repository artifacts without requiring network access to determine local readiness.

### VDP-0001-REQ-046 — Read-only operation

Processors MUST support read-only repository discovery and MUST NOT require writing files to determine repository identity or readiness.

### Canonical Layout

### VDP-0001-REQ-047 — Layout semantic authority

Canonical directories MUST be interpreted by semantic responsibility, not by folder existence alone.

### VDP-0001-REQ-048 — Constitution directory

`constitution/` MUST contain constitutional and specification artifacts that define normative project authority.

### VDP-0001-REQ-049 — Schemas directory

`schemas/` MUST contain machine-readable schemas that support validation without replacing authoritative Markdown specifications.

### VDP-0001-REQ-050 — Templates directory

`templates/` MUST contain reusable authoring templates and scaffolds that are non-authoritative until incorporated by accepted specifications.

### VDP-0001-REQ-051 — Examples directory

`examples/` MUST contain illustrative, non-production examples unless an accepted specification explicitly marks an example as authoritative for a defined purpose.

### VDP-0001-REQ-052 — Reviews directory

Review artifacts MUST be discoverable under a canonical review location or through accepted record references.

### VDP-0001-REQ-053 — Records directory

Governance, acceptance, migration, recovery, provenance, and decision records SHOULD be discoverable under a canonical record location or through accepted record references.

### VDP-0001-REQ-054 — Governance directory

Governance documentation and role records SHOULD be discoverable under a canonical governance location or through accepted constitutional references.

### VDP-0001-REQ-055 — Extensions directory

`extensions/` MAY contain optional repository extensions, but extension content MUST NOT alter core repository identity or accepted specifications without an accepted extension mechanism.

### VDP-0001-REQ-056 — Diagnostics directory

`diagnostics/` MAY contain validation results, reports, or diagnostic definitions, but diagnostics MUST remain evidence or derived artifacts unless accepted specifications grant authority.

### VDP-0001-REQ-057 — Scripts directory

`scripts/` MAY contain automation helpers, but scripts MUST NOT become normative merely because they exist or are executed by project tooling.

### VDP-0001-REQ-058 — Unknown directories

Processors MUST preserve unknown directories and MUST NOT treat them as errors solely because they are unknown.

### Repository Graph

### VDP-0001-REQ-059 — Graph over paths

Processors SHOULD model repository relationships as a graph of artifacts, records, evidence, implementations, schemas, diagnostics, and derived artifacts rather than as paths alone.

### VDP-0001-REQ-060 — Constitution to VDP relationship

The Constitution MUST be discoverable as the highest internal normative authority and MUST be related to dependent Accepted VDPs.

### VDP-0001-REQ-061 — VDP to review relationship

Accepted VDPs SHOULD be related to review artifacts, acceptance records, and decision records where those artifacts exist.

### VDP-0001-REQ-062 — Record to implementation relationship

Implementation artifacts SHOULD be related to the accepted specifications or decisions that authorize or constrain them.

### VDP-0001-REQ-063 — Derived artifact relationship

Derived artifacts MUST remain linked to their source artifacts when a processor presents them as repository evidence or navigation aids.

### VDP-0001-REQ-064 — Orphan artifact diagnostics

Processors SHOULD report orphan reviews, orphan acceptance records, orphan diagnostics, or derived artifacts whose authoritative source cannot be found.

### VDP-0001-REQ-065 — Relationship conflicts

Processors MUST report conflicts between manifest-declared relationships, filesystem-discovered relationships, and governance records.

### Conformance and Capabilities

### VDP-0001-REQ-066 — Repository discovery conformance

Repository Discovery conformance MUST require deterministic root discovery, manifest validation, identity classification, and readiness diagnostics.

### VDP-0001-REQ-067 — Repository layout conformance

Repository Layout conformance MUST require validation of required canonical directories and preservation of unknown directories.

### VDP-0001-REQ-068 — Governance conformance

Governance conformance MUST require discovery of constitutional artifacts, governance records, and authority records needed for claimed governance operations.

### VDP-0001-REQ-069 — Extensions conformance

Extensions conformance MUST require safe discovery of extensions without allowing extensions to override core repository semantics.

### VDP-0001-REQ-070 — Diagnostics conformance

Diagnostics conformance MUST require clear machine-readable or human-readable reporting of readiness, unsupported features, conflicts, and partial states.

### VDP-0001-REQ-071 — Hosted features conformance

Hosted Features conformance MUST NOT make the hosted platform authoritative merely because it renders, indexes, or validates repository content.

### VDP-0001-REQ-072 — Capability advertisement

The repository MAY advertise capabilities including governance, extensions, diagnostics, signatures, hosted, MCP, CLI, validation, and future capabilities.

### Multiple Repository Scenarios

### VDP-0001-REQ-073 — Nested repositories

When repositories are nested, the nearest valid repository root MUST win for an input path unless the user or caller explicitly selects another root.

### VDP-0001-REQ-074 — Monorepos

Monorepos MAY contain multiple Veridion repositories only when each repository has a distinct valid manifest and deterministic root.

### VDP-0001-REQ-075 — Submodules

Submodules or embedded repositories MUST be discovered as separate repository roots when they contain valid manifests.

### VDP-0001-REQ-076 — Multiple worktrees

Multiple worktrees sharing history MUST be treated as separate working locations that may share repository identity only when manifest and records support that conclusion.

### VDP-0001-REQ-077 — Vendor copies

Vendor copies MUST be classified as forks, archives, offline copies, temporary clones, or untrusted copies unless records establish another class.

### VDP-0001-REQ-078 — Temporary exports

Temporary exports lacking complete repository records MUST be classified as partial or untrusted rather than canonical.

### VDP-0001-REQ-079 — Archive bundles

Archive bundles MUST preserve enough manifest, record, and provenance data to support historical identity claims.

### Migration and Location Change

### VDP-0001-REQ-080 — Rename handling

A repository rename MUST NOT change repository identity.

### VDP-0001-REQ-081 — URL change handling

A URL change MUST NOT change repository identity.

### VDP-0001-REQ-082 — Hosting migration

Hosting migration MUST require a recorded migration or authority-transfer record before processors claim the new location is canonical.

### VDP-0001-REQ-083 — Canonical migration

Canonical migration MUST preserve repository identity, governance records, accepted specifications, review records, and historical provenance.

### VDP-0001-REQ-084 — Mirror promotion

Mirror promotion MUST require a recorded recovery or migration record that explains why the mirror became canonical.

### VDP-0001-REQ-085 — Archive creation

Archive creation MUST preserve the manifest, constitutional artifacts, accepted specifications, records, and provenance needed for future inspection.

### Repository Recovery

### VDP-0001-REQ-086 — Recovery provenance

Repository recovery MUST record provenance for the recovered repository state.

### VDP-0001-REQ-087 — Repository compromise recovery

Recovery from repository compromise MUST validate canonical history, preserve governance records, and publish a recovery record before canonicality is restored.

### VDP-0001-REQ-088 — History rewrite recovery

Recovery from history rewrite MUST distinguish legitimate preserved history from compromised, missing, rewritten, or unverifiable history.

### VDP-0001-REQ-089 — Hosting failure recovery

Recovery from hosting failure MAY use official mirrors or archives, but canonical status MUST require recorded recovery evidence.

### VDP-0001-REQ-090 — Partial corruption recovery

Recovery from partial corruption MUST identify affected artifacts, restored artifacts, validation evidence, and remaining uncertainty.

### VDP-0001-REQ-091 — Offline recovery

Offline recovery MAY establish local readiness but MUST NOT claim public canonicality without later publication of recovery records.

### VDP-0001-REQ-092 — Mirror verification

Recovery using mirrors SHOULD compare multiple available mirrors or archives when available and report verification gaps when comparison is not possible.

### Derived Artifacts

### VDP-0001-REQ-093 — Authoritative artifact boundary

Authoritative artifacts MUST be identified by accepted specifications, accepted governance records, or accepted repository records.

### VDP-0001-REQ-094 — Derived artifact boundary

Generated indexes, embeddings, search databases, caches, AI summaries, generated content, and hosted renderings MUST be treated as derived artifacts.

### VDP-0001-REQ-095 — Derived non-authority

Derived artifacts MUST NOT override authoritative artifacts.

### VDP-0001-REQ-096 — Stale derived artifacts

Processors SHOULD detect and report stale derived artifacts when source artifacts have changed or cannot be verified.

### Repository Security

### VDP-0001-REQ-097 — Manifest tampering

Processors MUST treat manifest tampering, unexpected manifest changes, and manifest-record conflicts as security-relevant diagnostics.

### VDP-0001-REQ-098 — Path traversal

Manifest paths and repository references MUST be validated to prevent path traversal outside intended repository boundaries.

### VDP-0001-REQ-099 — Symbolic links

Processors MUST handle symbolic links without allowing them to silently move authoritative artifact resolution outside the repository boundary.

### VDP-0001-REQ-100 — Filesystem normalization

Processors SHOULD detect case-insensitive filename conflicts, Unicode normalization conflicts, and duplicate logical filenames that could affect artifact resolution.

### VDP-0001-REQ-101 — Hostile copies

Processors MUST treat hostile mirrors, spoofed forks, malicious archives, partial clones, stale caches, and bootstrap poisoning as repository security concerns.

### AI, MCP, and Automation

### VDP-0001-REQ-102 — Shared bootstrap

Humans, CLIs, MCP servers, LLM agents, IDE extensions, automation, validators, hosted platforms, and third-party implementations SHOULD begin repository interpretation with the same bootstrap algorithm.

### VDP-0001-REQ-103 — Agent authority boundary

AI agents and MCP servers MUST NOT treat generated summaries, embeddings, tool memory, or model interpretations as authoritative repository state.

### Forward Compatibility and Failure Handling

### VDP-0001-REQ-104 — Unknown fields

Unknown manifest fields and unknown repository metadata MUST be preserved when possible and ignored safely unless an accepted specification assigns meaning to them.

### VDP-0001-REQ-105 — Future specifications

Unknown future specifications MUST NOT be treated as accepted or authoritative unless their metadata, lifecycle, and dependencies can be validated.

### VDP-0001-REQ-106 — Missing manifest

A missing manifest MUST produce an explicit discovery failure or partial-readiness diagnostic.

### VDP-0001-REQ-107 — Multiple manifests

Multiple candidate manifests MUST be resolved by deterministic nearest-root rules or reported as a conflict when deterministic resolution is impossible.

### VDP-0001-REQ-108 — Missing Constitution

A missing Constitution MUST prevent claims of full repository readiness.

### VDP-0001-REQ-109 — Conflicting mirrors

Conflicting mirror or canonicality claims MUST be reported and MUST NOT be silently reconciled.

### VDP-0001-REQ-110 — Broken records

Broken review history, missing governance records, orphan reviews, orphan acceptance records, repository downgrade, future manifest versions, and partial repositories MUST produce explicit diagnostics.

## Informative Notes

This specification intentionally defines repository semantics rather than implementation behavior. A processor may be a command-line tool, an MCP server, an IDE integration, a hosted service, a CI workflow, a library, or a human review procedure.

`VERIDION.yaml` is introduced as the bootstrap point, but this draft does not create the file. A later accepted specification or implementation task may define its exact schema, create the repository instance, and add validation tooling.

## Architecture

The repository model has four layers:

1. Discovery layer: input path, nearest manifest, manifest validation, root selection.
2. Authority layer: Constitution, Accepted VDPs, governance records, acceptance records, migration records, recovery records.
3. Navigation layer: canonical layout, repository graph, schemas, reviews, diagnostics, extensions.
4. Derived layer: indexes, embeddings, caches, generated summaries, rendered pages, hosted search, and AI-generated material.

Only the authority layer can define normative meaning. The discovery and navigation layers locate artifacts. The derived layer may improve usability but does not become authority.

## Interfaces

This specification defines semantic interfaces only:

- A repository exposes a bootstrap manifest at `VERIDION.yaml`.
- A processor accepts an input path or repository copy and returns a root, copy class, readiness state, diagnostics, and discovered artifact relationships.
- A repository may advertise capabilities through the manifest, subject to future accepted specifications.

No command syntax, API schema, MCP resource shape, or hosted protocol is defined in this draft.

## Algorithms

Deterministic bootstrap pseudocode:

```text
input: start path or repository location

candidate_roots = walk from start path toward filesystem or archive boundary
candidate_manifests = find VERIDION.yaml at each candidate root

if no candidate manifest:
  return discovery failure or partial repository diagnostic

select nearest candidate manifest
validate manifest syntax and supported manifest version

if manifest invalid:
  return unsupported or untrusted repository diagnostic

root = directory containing selected manifest
validate manifest-declared identity metadata
classify copy type from manifest, records, and provenance
validate required canonical layout
locate VDP-0000
locate Accepted VDPs and dependencies
locate schemas, reviews, governance records, repository records, diagnostics, and extensions
build non-authoritative repository graph
classify readiness as ready, partial, unsupported, or untrusted
return root, identity, copy class, readiness, graph, and diagnostics
```

The algorithm never resolves missing authority by inference. It reports partial or untrusted state when evidence is absent.

## Evidence Requirements

Evidence for repository readiness includes the manifest, constitutional artifacts, accepted VDP metadata, governance records, review records, acceptance records, migration records, recovery records, schema references, diagnostic outputs, and provenance records where available.

Processors that report conformance should preserve enough evidence for a reviewer to reconstruct how the root, identity, copy class, readiness state, and major diagnostics were determined.

## Reasoning Requirements

Repository processors should distinguish facts, assumptions, inferences, and unsupported claims. A processor may infer that a local copy is a working copy from local context, but it must not infer canonicality, acceptance, or governance authority without records.

## Validation Strategy

Validation for this draft can be performed by checking metadata conformance, canonical section presence, contiguous requirement identifiers, absence of unresolved placeholders, consistency between the prose algorithm and normative requirements, and cross-reference validity.

Future validation tooling may additionally test discovery fixtures, manifest parsing, nested repository cases, archive cases, hostile path cases, and derived artifact staleness cases.

## Scoring Considerations

Not applicable. Repository discovery and canonical layout do not define scoring.

## Security Considerations

Repository discovery is security-sensitive because a hostile copy can impersonate a canonical repository, hide or rewrite governance records, poison generated indexes, abuse path references, exploit symbolic links, or exploit filesystem normalization differences. Processors should prefer explicit diagnostics over silent recovery when trust evidence is incomplete.

## Performance Considerations

Discovery should be bounded by repository, filesystem, archive, or caller-defined boundaries. Processors should avoid unnecessary full-repository scans before validating the nearest manifest. Derived indexes and caches may improve performance but remain non-authoritative and must not replace validation of authoritative artifacts.

## Compatibility

This specification is designed for forward compatibility. Unknown directories, unknown capabilities, unknown manifest fields, unknown future specifications, and unsupported optional features should be preserved and ignored safely where possible. Unsupported mandatory features should produce diagnostics rather than silent misinterpretation.

## Migration

This draft does not migrate the current repository to `VERIDION.yaml`; it defines the future repository semantics for such a migration. A later change may add the manifest and validate current layout against this specification.

Repository rename, URL change, hosting migration, canonical migration, mirror promotion, archive creation, and ownership transfer must preserve identity and records according to the normative requirements.

## Extensibility

Future VDPs may define the exact `VERIDION.yaml` schema, repository record format, diagnostics registry, extension mechanism, signature model, hosted feature model, MCP resources, CLI commands, and conformance test fixtures. Those extensions must not silently change repository identity, authority hierarchy, or derived artifact boundaries.

## Alternatives Considered

- Filename-only discovery: rejected because it cannot establish identity, authority, copy class, or readiness.
- Git remote URL identity: rejected because repository identity must survive forge migration, rename, mirror creation, and ownership transfer.
- Git root discovery only: rejected because Veridion must support archives, exports, offline copies, and future storage systems.
- Generated index authority: rejected because generated indexes, embeddings, and AI summaries can become stale or incorrect.
- Fully specified Version 1 manifest schema: deferred to avoid over-design before the repository has implementation experience.

## Open Questions

- What exact fields will the first `VERIDION.yaml` schema require?
- Where should repository records live once a records specification exists?
- Should repository identity eventually include cryptographic identifiers, signed attestations, or both?
- How should hosted platforms expose repository graph data without becoming authority?
- Which conformance fixtures should be created first for nested repositories, archives, and hostile copies?

## Future Work

- Define the concrete `VERIDION.yaml` schema.
- Create repository record and recovery record formats.
- Define diagnostics identifiers and severity conventions.
- Define CLI, MCP, hosted, and IDE discovery interfaces.
- Add conformance fixtures for discovery and layout validation.
- Define extension loading and capability negotiation.
- Evaluate signature and provenance models.

## References

- VDP--001: Specification Specification.
- VDP-0000: Veridion Constitution.
- `docs/specification-process.md`.
- `docs/proposal-lifecycle.md`.
- `docs/repository/BOOTSTRAP-ALGORITHM.md`.

## Appendices

### Appendix A: Canonical Layout Summary

| Path | Purpose | Authority | Optionality | Future extension |
| --- | --- | --- | --- | --- |
| `constitution/` | Constitutional and specification artifacts. | Authoritative when artifacts are Accepted under VDP rules. | Required for readiness. | May contain future constitutional specifications. |
| `schemas/` | Machine-readable validation schemas. | Supportive unless accepted specifications grant scoped authority. | Required when referenced by manifest or specifications. | May add schema families. |
| `templates/` | Authoring templates and scaffolds. | Non-authoritative unless incorporated by accepted specifications. | Optional for repository operation. | May add templates by domain. |
| `examples/` | Informative examples. | Non-authoritative by default. | Optional. | May add examples by domain. |
| `reviews/` | Review artifacts. | Evidence unless accepted as records. | Optional unless lifecycle requires review evidence. | May be nested under `docs/` or a future canonical records area. |
| `records/` | Governance, acceptance, migration, recovery, and provenance records. | Authoritative when valid under accepted specifications. | Optional until records specification exists. | Reserved for future specification. |
| `governance/` | Governance documentation and role records. | Depends on Constitution and accepted records. | Optional until governance records require it. | May be organized by role or phase. |
| `extensions/` | Optional repository extensions. | Non-authoritative unless accepted extension rules apply. | Optional. | Reserved for future extension mechanism. |
| `diagnostics/` | Validation reports and diagnostic definitions. | Evidence or derived output unless accepted rules apply. | Optional. | Reserved for future diagnostics registry. |
| `scripts/` | Automation helpers. | Non-authoritative by existence alone. | Optional. | May contain implementation helpers. |
