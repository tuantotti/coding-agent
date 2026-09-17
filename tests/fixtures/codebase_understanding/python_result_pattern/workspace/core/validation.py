"""Input validation helpers. All validators return a Result, never raise."""

import re

from core.result import Result

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_email(email: str) -> Result[str]:
    """Validate an email address, returning a normalized value on success."""
    normalized = email.strip().lower()
    if not _EMAIL_RE.match(normalized):
        return Result.fail(f"invalid email address: {email!r}")
    return Result.ok(normalized)
