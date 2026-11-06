import re

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TAG_ESCAPE_RE = re.compile(r"</?\s*untrusted_document[^>]*>", re.IGNORECASE)


def sanitize_untrusted_text(text: str, max_chars: int = 16_000) -> str:
    """
    Strip non-printable control characters and neutralize any embedded XML fence
    tags to prevent prompt injection breakout.
    """
    cleaned = _CONTROL_CHARS_RE.sub("", text)
    cleaned = _TAG_ESCAPE_RE.sub("[ESCAPED_FENCE_TAG]", cleaned)
    return cleaned[:max_chars].strip()


def fence_untrusted_document(source_id: str, content: str, max_chars: int = 16_000) -> str:
    """
    Wrap untrusted external SEC filing or news content inside a strict structural XML fence.
    """
    safe_id = re.sub(r"[^a-zA-Z0-9_\-\.]", "_", source_id)
    safe_body = sanitize_untrusted_text(content, max_chars=max_chars)
    return f'<untrusted_document source_id="{safe_id}">\n{safe_body}\n</untrusted_document>'
