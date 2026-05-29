"""HTTP reverse proxy with PII scrubbing.

Intercepts LLM API calls, scrubs PII/PHI/PCD from the request body,
forwards the sanitized request upstream, and returns the response.

Handles:
  - Anthropic Messages API (/v1/messages)
  - OpenAI Chat Completions (/v1/chat/completions)
  - Streaming: accumulate-and-scrub (safe for compliance)

Environment variables that the sandbox agent uses:
  ANTHROPIC_BASE_URL=http://scrubber:8888
  OPENAI_BASE_URL=http://scrubber:8888
  → All SDK calls automatically route through this proxy.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

import httpx
import structlog
from fastapi import APIRouter, Request, Response
from fastapi.responses import StreamingResponse

from src.config import get_settings
from src.scrubber import PiiScrubber


_log = structlog.get_logger(__name__)
router = APIRouter()


def _get_scrubber() -> PiiScrubber:
    """Lazy singleton — built once, reused across requests."""
    if not hasattr(_get_scrubber, "_instance"):
        _get_scrubber._instance = PiiScrubber(get_settings())  # type: ignore[attr-defined]
    return _get_scrubber._instance  # type: ignore[attr-defined]


def _upstream_url(path: str) -> str:
    settings = get_settings()
    if "messages" in path or "anthropic" in path:
        return f"{settings.anthropic_upstream}{path}"
    return f"{settings.openai_upstream}{path}"


def _forward_headers(request: Request) -> dict[str, str]:
    skip = {"host", "content-length", "transfer-encoding", "connection"}
    return {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in skip
    }


# ─── Anthropic Messages API ──────────────────────────────────────────────────


@router.post("/v1/messages")
async def proxy_anthropic_messages(request: Request) -> Response:
    return await _proxy_request(request, "/v1/messages")


@router.get("/v1/messages")
@router.delete("/v1/messages/{message_id}")
async def proxy_anthropic_passthrough(request: Request, message_id: str = "") -> Response:
    path = f"/v1/messages/{message_id}" if message_id else "/v1/messages"
    return await _proxy_passthrough(request, path)


# ─── OpenAI Chat Completions ─────────────────────────────────────────────────


@router.post("/v1/chat/completions")
async def proxy_openai_chat(request: Request) -> Response:
    return await _proxy_request(request, "/v1/chat/completions")


# ─── Models list (pass-through, no PII) ─────────────────────────────────────


@router.get("/v1/models")
async def proxy_models(request: Request) -> Response:
    return await _proxy_passthrough(request, "/v1/models")


# ─── Core proxy logic ────────────────────────────────────────────────────────


async def _proxy_request(request: Request, path: str) -> Response:
    """Scrub then forward. Handles both streaming and non-streaming."""
    scrubber = _get_scrubber()
    settings = get_settings()

    # Parse body
    try:
        body = await request.json()
    except Exception:
        body = {}

    # Scrub all text content in the request body
    scrubbed_body, entities_found = scrubber.scrub_dict(body)

    if entities_found:
        entity_types = list({e["type"] for e in entities_found})
        _log.warning(
            "scrubber.pii_detected",
            entity_types=entity_types,
            regime=settings.regime.value,
            path=path,
        )
        # Async Mistral audit — fire and forget
        original_sample = _extract_text_sample(body)
        scrubbed_sample = _extract_text_sample(scrubbed_body)
        asyncio.create_task(
            scrubber.async_audit(original_sample, scrubbed_sample, entities_found)
        )

    is_streaming = scrubbed_body.get("stream", False)
    upstream = _upstream_url(path)
    headers = _forward_headers(request)

    if is_streaming and settings.stream_mode == "accumulate":
        # Accumulate-and-scrub: collect all SSE chunks, then return as one response.
        # Adds ~0.2–2s latency but prevents split-token PII leakage.
        return await _streaming_accumulate(scrubbed_body, upstream, headers, scrubber)
    else:
        return await _non_streaming(scrubbed_body, upstream, headers)


async def _non_streaming(body: dict, upstream: str, headers: dict) -> Response:
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(upstream, json=body, headers=headers)
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
        media_type=resp.headers.get("content-type", "application/json"),
    )


async def _streaming_accumulate(
    body: dict, upstream: str, headers: dict, scrubber: PiiScrubber
) -> Response:
    """Collect all SSE chunks, scrub the assembled text, re-emit as single response."""
    accumulated_text = ""
    full_response = None

    async with httpx.AsyncClient(timeout=300) as client:
        async with client.stream("POST", upstream, json=body, headers=headers) as resp:
            async for chunk in resp.aiter_text():
                for line in chunk.splitlines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            event = json.loads(line[6:])
                            text = _extract_delta_text(event)
                            if text:
                                accumulated_text += text
                        except json.JSONDecodeError:
                            pass
                    if line == "data: [DONE]":
                        break

    # Scrub the assembled response text
    if accumulated_text:
        scrub_result = scrubber.scrub(accumulated_text)
        if scrub_result.entities_found:
            _log.warning(
                "scrubber.response_pii_detected",
                entity_types=[e["type"] for e in scrub_result.entities_found],
            )
        accumulated_text = scrub_result.scrubbed_text

    # Return as a simple non-streaming response with the scrubbed text.
    # Claude Code / Codex SDKs handle non-streaming responses fine.
    response_body = {
        "type": "message",
        "content": [{"type": "text", "text": accumulated_text}],
        "role": "assistant",
        "stop_reason": "end_turn",
    }
    return Response(
        content=json.dumps(response_body),
        media_type="application/json",
    )


async def _proxy_passthrough(request: Request, path: str) -> Response:
    upstream = _upstream_url(path)
    headers = _forward_headers(request)
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            method=request.method,
            url=upstream,
            headers=headers,
        )
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type"),
    )


# ─── Helpers ────────────────────────────────────────────────────────────────


def _extract_text_sample(body: dict) -> str:
    """Pull a representative text string from an API request body."""
    messages = body.get("messages", [])
    if messages:
        last = messages[-1]
        content = last.get("content", "")
        if isinstance(content, str):
            return content[:500]
        if isinstance(content, list):
            texts = [c.get("text", "") for c in content if isinstance(c, dict)]
            return " ".join(texts)[:500]
    return str(body)[:500]


def _extract_delta_text(event: dict) -> str:
    # Anthropic SSE format
    delta = event.get("delta", {})
    if delta.get("type") == "text_delta":
        return delta.get("text", "")
    # OpenAI SSE format
    choices = event.get("choices", [])
    if choices:
        return choices[0].get("delta", {}).get("content", "")
    return ""
