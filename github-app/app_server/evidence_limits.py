MAX_EVIDENCE_BYTES = 25 * 1024 * 1024  # 25MB


class EvidenceTooLargeError(ValueError):
    pass


def check_evidence_size(encoded: str, max_bytes: int = MAX_EVIDENCE_BYTES) -> None:
    size = len(encoded.encode("utf-8"))
    if size > max_bytes:
        raise EvidenceTooLargeError(
            f"evidence payload is {size} bytes, exceeding the {max_bytes} byte limit"
        )
