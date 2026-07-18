# Managed audits are billed to us, not the customer (a shared DeepSeek key, see
# scan_worker/managed_audit.py) - an uncapped endpoint lets anyone with a valid token
# spam audits and drain that balance. Cooldown scales with repo size because that's
# what actually drives cost: a real Procta-sized audit (~147K LOC) cost ~$0.12, while
# Aletheore's own ~21K-LOC self-audit didn't move the balance past two decimal places.
_TIERS = (
    (10_000, 3 * 3600),
    (50_000, 6 * 3600),
    (150_000, 12 * 3600),
)
_DEFAULT_COOLDOWN_SECONDS = 24 * 3600


def cooldown_seconds_for_loc(total_loc: int) -> int:
    for threshold, cooldown_seconds in _TIERS:
        if total_loc <= threshold:
            return cooldown_seconds
    return _DEFAULT_COOLDOWN_SECONDS


def total_loc_from_evidence(evidence: dict) -> int:
    languages = evidence.get("repository", {}).get("languages", [])
    return sum(language.get("lines", 0) for language in languages)
