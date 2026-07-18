# Aletheore CLI `status` Command

**Status:** Draft, pending review
**Date:** 2026-07-18

## Problem

There's no way to check, from the terminal, what version of Aletheore is installed, whether a
newer one exists, or whether `aletheore login` (device flow, just shipped) actually left you
logged in and to which org. Right now the only way to find out any of that is reading `pip show`
output or re-running `aletheore login` itself and watching what it prints.

## Goals

- `aletheore status`: a single, read-only command reporting three independent things:
  1. **Installed version**, via `importlib.metadata.version("aletheore")` - the actual installed
     package metadata, not the stale hardcoded `__version__` string in `aletheore/__init__.py`
     (`0.1.0`, while `pyproject.toml` and the real installed metadata both say `0.3.0` - a
     pre-existing drift discovered while scoping this feature, left as-is; see Non-Goals).
  2. **Update availability**, by comparing the installed version against PyPI's real published
     `aletheore` package (`GET https://pypi.org/pypi/aletheore/json`, `info.version`) - real
     publishing infrastructure already exists (`.github/workflows/publish-pypi.yml`), so this is a
     meaningful check, not a stub.
  3. **Login state**, resolved the same way `_managed_audit` already resolves a token (env var
     `ALETHEORE_API_TOKEN` first, then the saved credentials file) - if one exists, verify it live
     against a new `GET /v1/whoami` backend endpoint and show which org/plan it belongs to,
     rather than just reporting "a token exists" with no idea if it still works.
- New backend route `GET /v1/whoami`, reusing the exact bearer-token-hash lookup pattern already
  implemented for managed audits (`get_installation_by_token_hash`) - not a new auth mechanism.

## Non-Goals

- **Not fixing the stale `__version__` string in `aletheore/__init__.py`.** A separate,
  pre-existing bug unrelated to this feature's own correctness (this command reads the real
  installed metadata via `importlib.metadata`, not that string, so it's unaffected either way).
  Flagged here for visibility, not fixed as part of this change.
- **No account management.** No `aletheore logout`, no token revocation from the CLI - a token
  minted via `aletheore login` is already revocable from the existing web dashboard. `status` is
  read-only.
- **No caching of the PyPI/whoami network calls.** Every `aletheore status` run makes both calls
  fresh - this is a manually-invoked diagnostic command, not something run in a hot loop, so
  caching would add complexity for no real benefit.
- **Graceful degradation, not hard failure, on network problems.** If PyPI is unreachable or
  `/v1/whoami` fails, `status` still prints the version and (if applicable) "a token is saved but
  couldn't be verified" rather than crashing the whole command over one failed sub-check.

## Architecture

### Backend: `github-app/app_server/managed_audit_api.py`

Same file as `start_managed_audit`, since both do raw-bearer-token-hash authentication - one new
route, no new imports beyond what's already there (`hashlib`, `get_installation_by_token_hash`):

```python
@managed_audit_router.get("/v1/whoami")
async def whoami(request: Request):
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")

    raw_token = auth_header.removeprefix("Bearer ")
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    installation = await get_installation_by_token_hash(request.app.state.db_pool, token_hash)
    if installation is None:
        raise HTTPException(status_code=401, detail="invalid or revoked token")
    return {"account_login": installation["account_login"], "plan": installation["plan"]}
```

### CLI: `prototype/aletheore/cli.py`

New `status` command, following the same "thin command, local imports, delegate to a helper"
pattern the `login` command already established:

```python
@app.command(help="show installed version, update availability, and login state")
def status() -> None:
    import importlib.metadata

    import httpx

    from aletheore.credentials import get_api_key, has_api_key

    installed_version = importlib.metadata.version("aletheore")

    try:
        pypi_response = httpx.get("https://pypi.org/pypi/aletheore/json", timeout=5.0)
        pypi_response.raise_for_status()
        latest_version = pypi_response.json()["info"]["version"]
        if latest_version == installed_version:
            version_note = "up to date"
        else:
            version_note = f"update available: {latest_version}"
    except httpx.HTTPError:
        version_note = "couldn't check for updates"

    console.print(f"Aletheore v{installed_version} ({version_note})")

    if not has_api_key("ALETHEORE_API_TOKEN", "aletheore-managed-audit"):
        console.print("Not logged in - run [bold]aletheore login[/bold]")
        return

    token = get_api_key("ALETHEORE_API_TOKEN", "aletheore-managed-audit", prompt_fn=lambda _msg: "")
    try:
        whoami_response = httpx.get(
            "https://app.aletheore.com/v1/whoami",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5.0,
        )
        whoami_response.raise_for_status()
        who = whoami_response.json()
        console.print(f"Logged in as: [bold]{who['account_login']}[/bold] ({who['plan']} plan)")
    except httpx.HTTPError:
        console.print("A token is saved locally, but it couldn't be verified right now.")
```

`get_api_key`'s `prompt_fn=lambda _msg: ""` means: if somehow neither the env var nor the saved
file actually had a value by the time this second call runs (a TOCTOU edge case between the
`has_api_key` check and this call - e.g. the file was deleted in between), it returns `None`
instead of blocking on a real terminal prompt inside a read-only status command. This mirrors the
existing `_managed_audit` call site's own resolution pattern exactly.

## Testing

- Backend: `github-app/tests/test_managed_audit_api.py` (or wherever `start_managed_audit`'s own
  tests live - read that file fresh before writing the plan's test tasks) - a valid, non-revoked
  token returns the right `account_login`/`plan`; a revoked or unknown token-hash returns 401; a
  missing/malformed `Authorization` header returns 401.
- CLI: mock `httpx.get` (via `unittest.mock.patch` or a fixture, matching this file's existing
  style) for both the PyPI and whoami calls - covers: up-to-date, update-available, PyPI
  unreachable, not-logged-in, logged-in-and-verified, logged-in-but-verification-fails.

## Success Criteria

1. `aletheore status` run with no saved token and no env var prints the version/update line and
   "Not logged in."
2. After a real `aletheore login`, `aletheore status` shows the real org name it's scoped to.
3. Revoking that token from the web dashboard, then running `aletheore status` again, shows
   "couldn't be verified" rather than a stale/wrong org name or a crash.
