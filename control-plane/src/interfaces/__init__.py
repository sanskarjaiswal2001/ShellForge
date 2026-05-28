"""Swappability boundary.

Every external dependency lives behind a Protocol class in this package.
Implementations live in ``src.providers.*`` and are selected at startup via
the matching ``*_BACKEND`` env var.

Business logic NEVER imports a concrete implementation. It imports only
the Protocol class and is given an instance via FastAPI dependency injection.
"""

from src.interfaces.audit_sink import AuditEvent, AuditSink
from src.interfaces.compute_provider import (
    ComputeProvider,
    SandboxPhase,
    SandboxRef,
    SandboxSpec,
)
from src.interfaces.identity_provider import IdentityClaims, IdentityProvider
from src.interfaces.pdf_renderer import PdfRenderer
from src.interfaces.secret_provider import SecretProvider

__all__ = [
    "AuditEvent",
    "AuditSink",
    "ComputeProvider",
    "IdentityClaims",
    "IdentityProvider",
    "PdfRenderer",
    "SandboxPhase",
    "SandboxRef",
    "SandboxSpec",
    "SecretProvider",
]
