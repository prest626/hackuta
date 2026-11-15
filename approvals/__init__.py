"""Approval gate. `propose` lives in approvals.core so API-5 can import it."""

from approvals.core import propose

__all__ = ["propose"]
