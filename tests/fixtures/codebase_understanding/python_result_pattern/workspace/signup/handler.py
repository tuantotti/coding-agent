"""Signup request handling."""

from core.result import Result
from core.validation import validate_email


def handle_signup(email: str, password: str) -> Result[dict]:
    """Validate signup input and build a signup record."""
    email_result = validate_email(email)
    if not email_result.is_ok:
        return Result.fail(email_result.error)
    if len(password) < 8:
        return Result.fail("password must be at least 8 characters")
    return Result.ok({"email": email_result.value})
