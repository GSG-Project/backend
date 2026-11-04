"""Normalizes latency and token usage, marking unavailable metrics rather than reporting zero."""


def normalize_latency_ms(value: float | None) -> int | None:
    """Whole milliseconds, or None when the latency is unknown or invalid."""
    if value is None or value < 0:
        return None
    return round(value)


def normalize_token_count(value: int | None) -> int | None:
    """A token count, or None when the provider did not report a usable one."""
    if value is None or value < 0:
        return None
    return int(value)
