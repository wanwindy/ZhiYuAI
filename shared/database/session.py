"""Async context helpers for the demo in-memory database."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass
class InMemorySession:
    """Placeholder session object for compatibility with older scripts."""

    token: str = field(default_factory=lambda: uuid4().hex)


@asynccontextmanager
async def get_session() -> InMemorySession:
    """Return an in-memory session placeholder."""
    session = InMemorySession()
    try:
        yield session
    finally:
        # Nothing to clean up, but keep the structure for later real DB swaps.
        return
