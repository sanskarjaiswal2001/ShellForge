"""WeasyPrint PDF renderer — default backend (pure-Python, no Chromium)."""

from __future__ import annotations

import asyncio

from src.interfaces.pdf_renderer import PdfRenderer


class WeasyprintRenderer(PdfRenderer):
    async def render(self, html: str, base_url: str | None = None) -> bytes:
        # WeasyPrint is sync; run in thread to avoid blocking the event loop.
        def _render() -> bytes:
            from weasyprint import HTML
            return HTML(string=html, base_url=base_url).write_pdf()

        return await asyncio.to_thread(_render)
