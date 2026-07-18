# Aletheore Dependency Manifest Fallbacks

**Status:** Draft, pending review
**Date:** 2026-07-18

## Problem

The multi-language dependency vulnerability/license checking shipped today (commit `8f3e1ca`)
gave Go/Rust/Java/Ruby/PHP/C# real coverage for the first time, verified against a real
Kubernetes scan (206 Go deps, 9 vulnerability findings, 40 license findings). But putting the
new checker in front of the marketing website's showcase repos (Django, Express, Kubernetes)
surfaced a second, more fundamental gap: **every one of the 8 parsers only reads a single,
specific *lockfile*, and returns "0 findings" - indistinguishable from a clean scan - when that
exact file is absent**, even when the project has real, declared dependencies sitting one file
away in a manifest.

This isn't hypothetical. Verified against real, well-known public repositories today:

- **Python** (`_parse_pip_pins`, reads `requirements.txt` only): Django itself has no root
  `requirements.txt` - its real dependencies (`asgiref>=3.12.1`, `sqlparse>=0.5.0`) live in
  `pyproject.toml`'s `[project.dependencies]` (PEP 621). Confirmed by cloning Django at the
  website's own pinned commit (`3d34265d5d1b83fee5df3c1b6f55087b1a6a1ded`) - zero pins found today.
- **Maven** (`_parse_maven_pins`, reads root `pom.xml` only): confirmed against
  `spring-projects/spring-petclinic` (an idiomatic Spring Boot app) - **25 of its 30** real
  dependencies have no explicit `<version>` tag at all (inherited from the
  `spring-boot-starter-parent` BOM) and are silently dropped by the current
  `if group is None or artifact is None or version is None: continue` check. Separately confirmed
  against `apache/dubbo` (57 `<module>` entries in its root POM) that **no submodule's `pom.xml`
  is ever read** - only the root file.
- **Rust** (`_parse_cargo_pins`, reads `Cargo.lock` only): confirmed against `serde-rs/serde`
  (one of the most-depended-on crates in the ecosystem) - it ships **no `Cargo.lock`** at all,
  per standard Rust convention that libraries commit `Cargo.toml` only. Zero pins found today.
- **PHP** (`_parse_composer_pins`, reads `composer.lock` only): confirmed against
  `guzzle/guzzle` - **no `composer.lock`** committed, same library convention. Zero pins found
  today.
- **C#** (`_parse_nuget_pins`, reads `packages.lock.json` only): confirmed against Microsoft's
  own `dotnet-architecture/eShopOnWeb` reference app - `packages.lock.json` requires opting in
  via `RestorePackagesWithLockFile`, essentially never enabled by default, so **zero
  `packages.lock.json` files exist in the entire repo**. Worse, its dependencies use **Central
  Package Management** (`<PackageReference Include="X" />` with no `Version` attribute at all -
  the version lives in a separate `Directory.Packages.props` file), a second real pattern the
  current parser has no path to at all.
- **Ruby** (`_parse_gemfile_lock_pins`, reads `Gemfile.lock` only): `rails/rails` happens to
  commit a root `Gemfile.lock` (a monorepo dev-workflow convention), so this ecosystem isn't
  broken on today's showcase set, but a standalone gem library (the far more common case) ships
  only a `.gemspec` with `add_dependency` calls and no lockfile - same class of gap, smaller
  blast radius on the specific repos in play today.
- **npm** (`_parse_npm_pins`, reads `package.json` only): the softest version of this problem -
  confirmed `expressjs/express` and `fastify/fastify` (both libraries) ship **no
  `package-lock.json`** either, so `package.json`'s declared range is already the best available
  signal for library repos. The real gap here is narrower: for *application* repos that do
  commit a lockfile, the current parser still only reads the declared range floor (e.g.
  `^6.15.2` checked as `6.15.2`) rather than preferring the lockfile's actually-resolved version
  when one is present.

In every case, `check_vulnerabilities`/`check_dependency_licenses` report `{"checked": true,
"findings": []}` for a project with real, non-empty, unresolved dependencies - the exact same
shape as "we checked and it's clean." This is a correctness problem for the checker itself, not
just a stale website demo: any user scanning a real Python/Rust/PHP/C# project that follows
completely standard, idiomatic conventions gets a false-positive "no issues found" today.

## Goals

- For each of the 8 ecosystems, read the **richest available manifest** rather than only the one
  specific lockfile filename: fall back to (or, for Maven, additionally read) the
  human-authored dependency declaration when the current lockfile-only source is absent or
  under-populated.
- Fix the three Maven-specific gaps directly, since they aren't lockfile-vs-manifest at all:
  resolve `${property}` placeholders against the same file's own `<properties>` block, do a
  best-effort local `<dependencyManagement>` lookup within the same file for dependencies with no
  explicit `<version>`, and recursively read every child `pom.xml` listed under `<modules>`.
- Every new fallback path is exercised by a real fixture-based test in the same style as the
  existing parsers (`prototype/tests/test_vulnerabilities.py`, `test_licenses.py`).
- Once implemented, regenerate `website/showcase-data.js` (Task 7-equivalent validation run
  against Django/Express/Kubernetes at their existing pinned SHAs) so the marketing site's
  numbers reflect real findings instead of a false "0".

## Non-Goals

- **Not resolving dependencies from an *external* parent POM or BOM that isn't vendored in the
  repo.** Spring Boot's `spring-boot-starter-parent` itself lives on Maven Central, not in the
  scanned repo - fully resolving inherited versions would mean fetching and parsing that parent
  POM (and potentially its own parent, recursively) over the network. This spec's Maven fix is
  explicitly a *local, same-repo, best-effort* resolution (same file's `<properties>` and
  `<dependencyManagement>`, plus child modules' own POMs) - dependencies whose version is only
  knowable by fetching a POM the repo doesn't contain remain unresolved and are honestly skipped,
  not silently faked.
- **Not adding a 9th ecosystem or new registry integration.** This spec only adds fallback
  *parsing* for manifests in ecosystems that already have a working vulnerability/license
  fetcher wired up via `_LICENSE_FETCHERS` and `_query_batch`'s OSV.dev ecosystem identifiers -
  no new `_LICENSE_FETCHERS` entries, no new OSV ecosystem strings.
- **Not lockfile-format changes for Go.** `go.mod`'s `require` directives are always exact
  versions (Go modules don't support ranges the way npm/Composer do) - there is no
  manifest-vs-lockfile ambiguity for Go, so it is untouched by this spec.
- **Not deduping/merging pins across sources within one ecosystem.** If, hypothetically, a repo
  had both a lockfile and a manifest with overlapping packages, each ecosystem picks exactly one
  source per the precedence rule below (lockfile wins when present and non-empty) - there is no
  merge step to design or test.

## Design

### Precedence rule (npm, Rust, PHP, Ruby)

For these four ecosystems, the existing lockfile parser is authoritative when its file exists;
the new manifest parser is a **fallback used only when the lockfile is absent**. This preserves
today's accuracy for the common case (a real lockfile reflects the actually-resolved version;
a manifest's declared range is, at best, an approximation) while eliminating the current
all-or-nothing failure mode.

- **npm**: if `package-lock.json` exists, keep using it (reading `packages["node_modules/<name>"].version`
  for the actually-resolved version, which is more accurate than today's range-floor parsing of
  `package.json`); otherwise fall back to today's existing `package.json`-range behavior
  unchanged. This also *improves* accuracy for the case where a lockfile does exist, not just
  the case where it doesn't.
- **Rust**: if `Cargo.lock` exists, keep using it unchanged; otherwise fall back to parsing
  `Cargo.toml`'s `[dependencies]`/`[dev-dependencies]` tables (string form `"1.2.3"` or table
  form `{ version = "1.2.3" }`; entries using `{ workspace = true }` or a `path`/`git` key with no
  version are skipped - there is no resolvable version to check).
- **PHP**: if `composer.lock` exists, keep using it unchanged; otherwise fall back to parsing
  `composer.json`'s `require` block, stripping the same kind of range prefix (`^`, `~`, `>=`) npm
  already strips.
- **Ruby**: if `Gemfile.lock` exists, keep using it unchanged; otherwise fall back to parsing the
  repo's own `*.gemspec` file (there's normally exactly one at repo root for a gem library) for
  `add_dependency`/`add_runtime_dependency` calls with a literal string version argument (calls
  using a variable like today's Rails example - `s.add_dependency "activesupport", version` - have
  no literal version to extract and are skipped, same honesty principle as the Rust workspace
  case above).

### C#: two-tier fallback

`packages.lock.json` is opt-in and rare; even when absent, the *actual* version can live in one
of two other places depending on which .NET dependency-management style a project uses:

1. If `packages.lock.json` exists, keep using it unchanged (today's behavior).
2. Otherwise, parse every `*.csproj` in the repo for `<PackageReference Include="X" Version="Y" />`
   (both attributes on one element) - the traditional, most common style.
3. For `<PackageReference Include="X" />` with no `Version` attribute (Central Package
   Management), look up `X`'s version in a repo-root `Directory.Packages.props` file's
   `<PackageVersion Include="X" Version="Y" />` entries. If neither the `.csproj` nor
   `Directory.Packages.props` has a resolvable version for a given package, it's skipped.

### Python: additive, not exclusive

Unlike the four "lockfile vs. manifest" ecosystems above, Python's `requirements.txt` and
`pyproject.toml` aren't a resolved/unresolved pair - a real project can have either, both, or
(historically) neither. So this one is **additive**: parse `pyproject.toml` in addition to
`requirements.txt`, not as a fallback gated on the latter's absence.

- **PEP 621**: `[project.dependencies]` is a list of PEP 508 strings (`"asgiref>=3.12.1"`,
  `"sqlparse>=0.5.0"`). Only exact (`==`) or lower-bound-only (`>=`) specifiers with a single
  version number are usable for a vulnerability/license lookup; the specific version checked is
  the pinned/lower-bound number itself (accepting the same "not necessarily the actually-installed
  version" approximation the npm/PHP manifest fallbacks already accept - this is explicitly an
  approximation, not a resolved install). Specifiers with no version at all (`"tzdata; sys_platform
  == 'win32'"`) or an environment marker excluding the current platform are skipped, matching the
  existing `requirements.txt` parser's `if name and version:` guard.
- **Poetry**: `[tool.poetry.dependencies]` uses caret/tilde-style strings (`"^4.2"`) or an inline
  table (`{ version = "^4.2", optional = true }`) rather than PEP 508 - parsed separately, using
  the same range-prefix-stripping approach as npm's fallback.

### Maven: three local fixes, not a fallback source

These are fixed directly in `_parse_maven_pins` rather than added as a second function, since
they're gaps in reading the *same* `pom.xml`, not an alternate file:

1. **Property resolution**: before the existing `if not group.text or not artifact.text or not
   version.text: continue` check, if `version.text.strip()` matches `${...}`, look up the
   property name in the same file's `<properties>` element (a flat list of arbitrarily-named
   child elements, e.g. `<webjars-locator.version>0.52</webjars-locator.version>`) and substitute
   its text if found. If the property isn't defined locally (inherited from an external parent),
   the dependency is skipped - per the Non-Goals section, this is an honest limit, not a bug to
   paper over.
2. **Same-file `dependencyManagement` fallback**: for a `<dependency>` with no `<version>` child
   at all, look up a matching `groupId`+`artifactId` pair inside the same file's
   `<dependencyManagement><dependencies>` block (a real, common pattern for multi-module parent
   POMs that centralize versions for their own children) before giving up. If no match is found
   there either (as with Spring Boot's *external* parent BOM), it's skipped, honestly.
3. **Recursive module traversal**: read the root `pom.xml`'s `<modules><module>name</module>...`
   list; for each, recursively parse `<module-dir>/pom.xml` with the same three rules above,
   concatenating all discovered pins. Modules are relative directory names per the Maven spec
   (`<module>dubbo-common</module>` means `dubbo-common/pom.xml`); a listed module directory or
   `pom.xml` that doesn't exist is skipped rather than raising.

### What doesn't change

- `_LICENSE_FETCHERS` dispatch dict: unchanged. Every fallback parser reuses the exact same
  ecosystem string (`"PyPI"`, `"npm"`, `"crates.io"`, `"Packagist"`, `"NuGet"`, `"RubyGems"`,
  `"Maven"`) its lockfile-based counterpart already uses, so no new fetcher or dispatch entry is
  needed - the existing `_fetch_pypi_license`/`_fetch_npm_license`/etc. and `_query_batch`'s
  OSV.dev ecosystem identifiers work unmodified against pins from either source.
- `check_vulnerabilities`/`check_dependency_licenses`: unchanged in shape - they still concatenate
  every ecosystem's pins into one list and behave identically once pins exist; the fix is
  entirely inside each `_parse_*_pins` function's own file-discovery logic.

## Testing / Success Criteria

- Each new/modified parser gets a fixture-based test in the existing style: write a `tmp_path`
  repo with the specific manifest shape being tested (e.g. a `pyproject.toml` with PEP 621
  dependencies and no `requirements.txt`; a `pom.xml` with a `${property}` version and a
  `<properties>` block; a multi-module `pom.xml` plus a child module directory), assert the
  parser returns the expected `(name, version, ecosystem)` tuples.
- A precedence test per lockfile/manifest pair (npm, Rust, PHP, Ruby) confirms the lockfile wins
  when both files are present, using two fixtures with intentionally different versions for the
  same package name.
- Full existing regression suite continues to pass unchanged - no existing parser's fixture loses
  or gains pins it wasn't meant to.
- Real-world validation: re-run `aletheore scan` against Django and Express at their existing
  pinned commit SHAs (`3d34265d5d1b83fee5df3c1b6f55087b1a6a1ded`,
  `ae6dd37680e3a00618d6c8a3e522f0ee4eeba1a4` - same SHAs the marketing website already cites, no
  new pins needed) and confirm Django now reports a non-zero dependency count (it has 2-3 real
  runtime deps in `pyproject.toml`, so this is a small but real, honest number - not expected to
  be dramatic).
- `website/showcase-data.js` is regenerated afterward (rerunning
  `scripts/generate-showcase-data.sh` / `scripts/extract-showcase-data.py`) so the live site's
  Django card no longer implies a dependency-vulnerability scan found nothing when nothing was
  actually checked.
