import pytest

from app_server.evidence_limits import EvidenceTooLargeError, check_evidence_size


def test_check_evidence_size_allows_small_payload():
    check_evidence_size("x" * 100, max_bytes=1000)


def test_check_evidence_size_rejects_oversized_payload():
    with pytest.raises(EvidenceTooLargeError, match="exceeding the 1000 byte limit"):
        check_evidence_size("x" * 1001, max_bytes=1000)


def test_check_evidence_size_measures_utf8_bytes_not_characters():
    # Each euro sign is 3 bytes in UTF-8 but 1 character - the check must
    # measure encoded bytes, not len(str), or a multi-byte payload could
    # sail well past the intended byte limit.
    payload = "€" * 400  # 400 chars, 1200 bytes
    with pytest.raises(EvidenceTooLargeError):
        check_evidence_size(payload, max_bytes=1000)
    check_evidence_size(payload, max_bytes=1200)
