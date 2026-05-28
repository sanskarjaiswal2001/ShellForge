"""OTel-LogRecord audit sink — primary production backend.

Emits each audit event as an OTLP log record. The body is OCSF-formatted
JSON; attributes contain a flattened view for SIEMs that don't natively
parse OCSF.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from opentelemetry import trace
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LogRecord
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from src.interfaces.audit_sink import AuditEvent, AuditSink


class OtelAuditSink(AuditSink):
    def __init__(
        self,
        endpoint: str,
        protocol: str,
        service_name: str,
    ) -> None:
        self._endpoint = endpoint
        self._service_name = service_name

        resource = Resource.create({"service.name": service_name})
        self._provider = LoggerProvider(resource=resource)

        if protocol == "grpc":
            exporter = OTLPLogExporter(endpoint=endpoint, insecure=True)
        else:
            from opentelemetry.exporter.otlp.proto.http._log_exporter import (
                OTLPLogExporter as HttpExporter,
            )
            exporter = HttpExporter(endpoint=endpoint)

        self._processor = BatchLogRecordProcessor(exporter)
        self._provider.add_log_record_processor(self._processor)
        set_logger_provider(self._provider)
        self._logger = self._provider.get_logger("shellforge.audit")

    async def emit(self, event: AuditEvent) -> None:
        body = json.dumps(self._to_ocsf(event), separators=(",", ":"))
        attributes = {
            "tenant_id": event.tenant_id,
            "actor.user.uid": event.actor.user_uid,
            "actor.user.email": event.actor.user_email,
            "action": event.action,
            "resource.type": event.resource.type,
            "resource.uid": event.resource.uid,
            "outcome": event.outcome,
            "event.hash": event.event_hash,
            "event.prev_hash": event.prev_hash,
            "ocsf.class_uid": event.class_uid,
            "ocsf.activity_id": event.activity_id,
            "source": event.source,
        }
        record = LogRecord(
            timestamp=int(event.occurred_at.timestamp() * 1e9),
            trace_id=trace.get_current_span().get_span_context().trace_id,
            span_id=trace.get_current_span().get_span_context().span_id,
            severity_text="INFO",
            body=body,
            attributes=attributes,
        )
        self._logger.emit(record)

    async def flush(self) -> None:
        self._processor.force_flush(timeout_millis=5000)

    @staticmethod
    def _to_ocsf(event: AuditEvent) -> dict:
        return {
            "metadata": {
                "version": "1.7.0",
                "product": {"name": "shellforge", "vendor_name": "Betsol"},
                "log_name": "shellforge-audit",
            },
            "class_uid": event.class_uid,
            "category_uid": event.category_uid,
            "activity_id": event.activity_id,
            "time": int(event.occurred_at.timestamp() * 1000),
            "actor": {
                "user": {
                    "uid": event.actor.user_uid,
                    "email_addr": event.actor.user_email,
                    "type_id": 1,
                },
                "session": {"uid": event.actor.session_uid} if event.actor.session_uid else None,
            },
            "status": event.outcome,
            "unmapped": {
                "tenant_id": event.tenant_id,
                "action": event.action,
                "resource_type": event.resource.type,
                "resource_uid": event.resource.uid,
                "resource_name": event.resource.name,
                "resource_labels": event.resource.labels,
                "prev_hash": event.prev_hash,
                "event_hash": event.event_hash,
                "source": event.source,
                **event.details,
            },
        }
