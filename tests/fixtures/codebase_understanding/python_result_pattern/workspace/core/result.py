"""Lightweight Result type used across this codebase instead of exceptions."""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class Result(Generic[T]):
    """Represents either a successful value or an error message."""

    value: T | None
    error: str | None

    @property
    def is_ok(self) -> bool:
        """Return True when no error occurred."""
        return self.error is None

    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        """Build a successful result."""
        return cls(value=value, error=None)

    @classmethod
    def fail(cls, error: str) -> "Result[T]":
        """Build a failed result."""
        return cls(value=None, error=error)
