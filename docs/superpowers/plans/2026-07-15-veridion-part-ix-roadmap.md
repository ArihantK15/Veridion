# Veridion Part IX (Roadmap Generation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Roadmap section to the audit report that prioritizes findings already stated
elsewhere in the same report — no new evidence, no new scanner code.

**Architecture:** Pure manual-content addition. One new file
(`manual/part-9-roadmap.md`) plus a small edit to `manual/part-1-operating-instructions.md`'s
output contract to insert the new section in the right position.

**Tech Stack:** None — this task has zero Python code and zero tests. Every previous part
(v1, Part IV, Part V, scan/query) added scanner logic with pytest coverage; this one doesn't,
because Part IX consumes evidence rather than producing it.

## Global Constraints

- No numeric scores, ROI/difficulty/risk ratings, or day-count timeframes (30/60/90-day
  language) anywhere in the new manual content — three qualitative tiers only (Immediate /
  Near-term / Longer-term).
- Every roadmap item must cite the specific earlier finding it comes from — this section
  introduces no new claims about the repository, only prioritizes what Repository
  Intelligence, Git Intelligence, Architecture Review, and Security already reported.
- All four prior sections must be explicitly considered, in order — if one contributes
  nothing, the report must say so plainly, not omit it silently.

---

## Task 1: Part IX manual content and Part I output-contract update

**Files:**
- Create: `prototype/manual/part-9-roadmap.md`
- Modify: `prototype/manual/part-1-operating-instructions.md`

**Interfaces:**
- Consumes: nothing — this is manual content read by the reasoning-phase agent, not code with
  a function signature.
- Produces: nothing consumed by other tasks — this is the only content task in this plan.

- [ ] **Step 1: Create the Part IX manual file**

Create `prototype/manual/part-9-roadmap.md`:
```markdown
# Part IX — Roadmap

This section governs how to produce the `## Roadmap` section of the report, appearing after
`## Security` and before `## Evidence Gaps`. Follow the mandatory verification rules in Part I
for everything below.

## What this section does

Synthesize and prioritize findings already stated earlier in this same report. This section
introduces no new evidence and makes no new claims about the repository — it reorders and
triages what Repository Intelligence, Git Intelligence, Architecture Review, and Security
already reported.

## Mandatory rules

1. **Every roadmap item must cite the specific earlier finding it comes from** — name the
   file, branch, cluster, or evidence field exactly as it was already stated earlier in this
   report. Do not restate a finding in generic terms that lose its specificity (e.g. "fix
   circular dependencies" is not acceptable on its own; "fix the two circular import chains
   named in Architecture Review" is).
2. **Do not introduce any claim that wasn't already made in Repository Intelligence, Git
   Intelligence, Architecture Review, or Security.** If you're tempted to recommend something
   evidence doesn't support (general advice like "improve documentation" or "modernize the
   stack" that isn't grounded in a specific finding already reported earlier in this report),
   leave it out entirely.
3. **Walk all four prior sections explicitly, in this order: Repository Intelligence, Git
   Intelligence, Architecture Review, Security.** For each one, either list what from it
   belongs on the roadmap, or state plainly that this section contributed nothing
   roadmap-worthy (for example: "Security: zero findings warranted inclusion — the
   dependency-vulnerability check found nothing and both secret findings were flagged
   `likely_placeholder`"). Do not skip a section silently just because it has nothing to add.
4. **Use exactly three tiers: Immediate, Near-term, Longer-term.** No numeric scores, no
   ROI/difficulty/risk ratings, no day-count estimates (30/60/90-day language or similar). A
   tier assignment plus one sentence of evidence-grounded rationale per item is the complete
   format — nothing more elaborate.
5. **State which tiering criterion applies when assigning a tier**, using the heuristic below
   — so the assignment itself is inspectable, not a bare assertion.

## Tiering heuristic

- **Immediate**: High-confidence findings from earlier sections representing either an active
  risk (a real, non-placeholder secret finding; a confirmed circular import or layer
  violation) or a trivial, no-judgment-needed fix (unpushed local commits sitting on one
  machine; a dependency already flagged with a real advisory in
  `security.dependency_vulnerabilities.findings`).
- **Near-term**: High-confidence findings needing real but bounded effort — adding test
  coverage for a specific high-fan-in untested module named earlier in Repository
  Intelligence, reviewing or merging specific named branches with real `ahead_of_main` counts
  from Git Intelligence, addressing a specific named god-module.
- **Longer-term**: Medium- or Low-confidence findings needing investigation before action
  (cross-cluster coupling flagged "worth investigating" in Architecture Review), or findings
  that are structurally larger in scope (expanding language coverage for files currently
  listed in `repository.unparseable_files`).

## What this section does not produce

No numeric scores of any kind. No ROI, difficulty, or risk ratings. No specific day-count
timeframes. No new claims about the repository beyond what earlier sections in this same
report already stated. No business, revenue, or market recommendations — those aren't
repo-derivable and are out of scope for this manual entirely.
```

- [ ] **Step 2: Update Part I's output contract**

In `prototype/manual/part-1-operating-instructions.md`, replace the output contract list:
```markdown
1. **Summary** — 3-5 sentences, no unsupported claims, citing the highest-confidence findings.
2. **Repository Intelligence** — findings from `evidence.repository`, per Part II below.
3. **Git Intelligence** — findings from `evidence.git`, per Part III below.
4. **Architecture Review** — findings from `evidence.architecture`, per Part IV below.
5. **Security** — findings from `evidence.security`, per Part V below.
6. **Evidence Gaps** — an explicit list of what `evidence.json` could not tell you
   (unparseable files, unavailable git data, anything you were tempted to claim but couldn't
   support).
```
with:
```markdown
1. **Summary** — 3-5 sentences, no unsupported claims, citing the highest-confidence findings.
2. **Repository Intelligence** — findings from `evidence.repository`, per Part II below.
3. **Git Intelligence** — findings from `evidence.git`, per Part III below.
4. **Architecture Review** — findings from `evidence.architecture`, per Part IV below.
5. **Security** — findings from `evidence.security`, per Part V below.
6. **Roadmap** — prioritized findings from the sections above, per Part IX below.
7. **Evidence Gaps** — an explicit list of what `evidence.json` could not tell you
   (unparseable files, unavailable git data, anything you were tempted to claim but couldn't
   support).
```

The sentence immediately after this list ("This list must be kept in sync with whichever parts
of the manual actually exist...") does not need to change — it already applies to this edit.

- [ ] **Step 3: Commit**

```bash
git add prototype/manual/part-9-roadmap.md prototype/manual/part-1-operating-instructions.md
git commit -m "docs: add Part IX roadmap manual, update Part I output contract"
```

---

## Task 2: Live dogfood verification (not automated)

No code changes — confirms the new section behaves correctly in a real reasoning-phase run.
This requires an explicit go-ahead before the live `claude` call against Procta's private
source, same authorization boundary as every previous part.

- [ ] **Step 1: Run the full reasoning-phase audit against Procta**

Only after checking with the user first:
```bash
cd /Users/arihantkaul/Documents/GitHub/Veridion
veridion audit /Users/arihantkaul/proctored-browser
```

- [ ] **Step 2: Check the Roadmap section's position**

Confirm `.veridion/audit-report.md` has a `## Roadmap` section appearing after `## Security`
and before `## Evidence Gaps` — this is Success Criterion 1 from the design spec.

- [ ] **Step 3: Verify every roadmap item traces to an earlier finding**

For each item under Immediate/Near-term/Longer-term, confirm the specific file, branch,
cluster, or evidence field it names also appears earlier in the same report (Repository
Intelligence, Git Intelligence, Architecture Review, or Security) — not just a plausible-sounding
claim invented fresh in the Roadmap section. This is Success Criterion 2.

- [ ] **Step 4: Confirm no numeric scores anywhere in the section**

Read the Roadmap section specifically for any number presented as a score, rating, or
day-count estimate (as opposed to a number that's a direct citation of an evidence field, like
"92 importers" when citing a fan-in finding — citing an already-reported number is fine, a new
score invented for this section is not). This is Success Criterion 3.

- [ ] **Step 5: Confirm section-by-section coverage**

Confirm the report explicitly addresses all four prior sections (Repository Intelligence, Git
Intelligence, Architecture Review, Security) — either with roadmap items drawn from that
section, or an explicit statement that the section contributed nothing. Do not force a
"contributes nothing" case to occur if it doesn't happen naturally on this real run — this
step is about confirming the report handles whichever case actually occurs (something from
every section, or an explicit empty-section statement) correctly, not about engineering a
specific outcome. This is Success Criterion 4.

- [ ] **Step 6: Record the outcome**

If all four criteria pass, Part IX is done — report back with any surprises (a section that
turned out to have nothing roadmap-worthy, tier assignments that seem miscalibrated against
the stated heuristic). If any criterion fails, that's the next debugging task, not a new plan.

---

## Self-Review Notes

**Spec coverage:** all four numbered success criteria map directly to Task 2's steps 2-5. The
spec's four mandatory rules and the tiering heuristic are reproduced verbatim as real manual
content in Task 1, not summarized or left for the implementer to reconstruct.

**Placeholder scan:** no TBD/TODO; the manual content in Task 1 is complete, final prose, not
a description of what the file should eventually contain.

**Type consistency:** not applicable — this plan has no functions, types, or signatures
anywhere, since it adds no code.
