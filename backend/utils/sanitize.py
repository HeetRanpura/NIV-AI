"""
Utilities for sanitizing user-provided input before LLM prompt interpolation.

Wrapping free-text in XML delimiters prevents prompt injection: the LLM system prompts
instruct models to treat content inside these tags as quoted data, never as instructions.
"""
from __future__ import annotations


def wrap_user_content(value: str | None, tag: str = "user_input") -> str:
    """
    Wraps user-provided free-text in XML delimiters to prevent prompt injection.

    LLM system prompts instruct models to treat content inside these tags as
    quoted data, never as instructions.

    Args:
        value: User-provided string, may be None or empty.
        tag: XML tag name to use as delimiter. Defaults to "user_input".

    Returns:
        XML-wrapped string safe for interpolation into LLM prompts.
        Returns empty-tag pair when value is None or empty.
    """
    if not value:
        return f"<{tag}></{tag}>"
    return f"<{tag}>{value}</{tag}>"
