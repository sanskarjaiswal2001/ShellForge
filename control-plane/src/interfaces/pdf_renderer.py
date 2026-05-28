"""PDF renderer protocol — compliance pack generator backend."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class PdfRenderer(Protocol):
    """Pluggable HTML → PDF renderer."""

    async def render(self, html: str, base_url: str | None = None) -> bytes:
        """Render an HTML document to PDF bytes."""
        ...
