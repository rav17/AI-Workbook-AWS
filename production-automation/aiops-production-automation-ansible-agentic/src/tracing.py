"""OpenTelemetry tracing for the AIOps Self-Healing pipeline.

Provides distributed tracing across pipeline stages (normalize → enrich →
match → guardrail → execute → notify) and AI reasoning calls. Traces are
exported to AWS X-Ray via OTLP when configured, or to stdout in dev mode.

Usage:
    from src.tracing import get_tracer, trace_pipeline_stage

    tracer = get_tracer(__name__)

    @trace_pipeline_stage("enrich")
    async def enrich(alert):
        ...

Configuration (environment variables):
    OTEL_ENABLED: "true" to enable tracing (default: "true")
    OTEL_SERVICE_NAME: Service name in traces (default: "aiops-self-healing")
    OTEL_EXPORTER: "xray" | "otlp" | "console" (default: "xray")
    OTEL_OTLP_ENDPOINT: OTLP collector endpoint (if using "otlp")
    ENVIRONMENT: Used as resource attribute

This module is safe to import even if opentelemetry is not installed —
it falls back to no-op implementations.
"""

import functools
import logging
import os
import time
from contextlib import contextmanager
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Feature flag: tracing can be disabled entirely
_TRACING_ENABLED = os.environ.get("OTEL_ENABLED", "true").lower() in ("true", "1", "yes")
_SERVICE_NAME = os.environ.get("OTEL_SERVICE_NAME", "aiops-self-healing")
_ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
_EXPORTER_TYPE = os.environ.get("OTEL_EXPORTER", "xray")

# Try to import OpenTelemetry; gracefully degrade if not installed
_otel_available = False
_tracer_provider = None

try:
    if _TRACING_ENABLED:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.trace import StatusCode

        _otel_available = True
        logger.info("OpenTelemetry SDK available — tracing enabled")
    else:
        logger.info("OpenTelemetry tracing disabled via OTEL_ENABLED=false")
except ImportError:
    logger.info(
        "OpenTelemetry SDK not installed — tracing disabled. "
        "Install with: pip install opentelemetry-sdk opentelemetry-exporter-otlp"
    )


def _init_tracer_provider() -> None:
    """Initialize the global TracerProvider with appropriate exporter."""
    global _tracer_provider

    if not _otel_available:
        return

    resource = Resource.create({
        "service.name": _SERVICE_NAME,
        "service.version": "1.0.0",
        "deployment.environment": _ENVIRONMENT,
    })

    _tracer_provider = TracerProvider(resource=resource)

    # Select exporter based on configuration
    if _EXPORTER_TYPE == "console":
        processor = BatchSpanProcessor(ConsoleSpanExporter())
    elif _EXPORTER_TYPE == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            endpoint = os.environ.get("OTEL_OTLP_ENDPOINT", "http://localhost:4317")
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        except ImportError:
            logger.warning("OTLP exporter not installed, falling back to console")
            processor = BatchSpanProcessor(ConsoleSpanExporter())
    else:
        # Default: X-Ray (use OTLP to X-Ray ADOT collector or console fallback)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            # ADOT collector on localhost:4317 exports to X-Ray
            endpoint = os.environ.get("OTEL_OTLP_ENDPOINT", "http://localhost:4317")
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
        except ImportError:
            # Fallback: just log spans
            processor = BatchSpanProcessor(ConsoleSpanExporter())

    _tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(_tracer_provider)
    logger.info("TracerProvider initialized (exporter=%s)", _EXPORTER_TYPE)


# Initialize on module load
if _otel_available:
    _init_tracer_provider()


class _NoOpSpan:
    """No-op span for when tracing is disabled."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any, description: str = "") -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class _NoOpTracer:
    """No-op tracer for when OpenTelemetry is not installed."""

    def start_span(self, name: str, **kwargs) -> _NoOpSpan:
        return _NoOpSpan()

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        yield _NoOpSpan()


def get_tracer(name: str = __name__) -> Any:
    """Get a tracer instance for the given module.

    Returns a real OpenTelemetry tracer if available, or a no-op tracer
    that has zero performance impact when tracing is disabled.
    """
    if _otel_available and _tracer_provider:
        return trace.get_tracer(name)
    return _NoOpTracer()


def trace_pipeline_stage(stage_name: str):
    """Decorator that traces an async pipeline stage function.

    Adds a span with:
    - stage name
    - incident_id (if available in kwargs or first arg)
    - duration
    - exception info on failure

    Usage:
        @trace_pipeline_stage("enrich")
        async def enrich(self, alert: NormalizedAlert) -> EnrichedAlert:
            ...
    """
    def decorator(func: Callable) -> Callable:
        if not _otel_available:
            return func  # Zero overhead when tracing disabled

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            tracer = get_tracer(func.__module__)
            with tracer.start_as_current_span(f"pipeline.{stage_name}") as span:
                # Try to extract incident_id for correlation
                incident_id = kwargs.get("incident_id", "")
                if not incident_id and len(args) > 1:
                    arg = args[1]  # first arg after self
                    if hasattr(arg, "incident_id"):
                        incident_id = arg.incident_id

                span.set_attribute("aiops.stage", stage_name)
                if incident_id:
                    span.set_attribute("aiops.incident_id", incident_id)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(StatusCode.OK)
                    return result
                except Exception as e:
                    span.set_status(StatusCode.ERROR, str(e))
                    span.record_exception(e)
                    raise

        return wrapper
    return decorator


def trace_bedrock_call(
    model_id: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    latency_ms: float = 0,
    success: bool = True,
    incident_id: str = "",
) -> None:
    """Record a Bedrock model invocation as a span event.

    Following OpenTelemetry GenAI semantic conventions:
    - gen_ai.system = "aws.bedrock"
    - gen_ai.request.model = model_id
    - gen_ai.usage.input_tokens = input_tokens
    - gen_ai.usage.output_tokens = output_tokens

    Args:
        model_id: The Bedrock model ID used.
        input_tokens: Tokens sent to model.
        output_tokens: Tokens received from model.
        latency_ms: Call duration in milliseconds.
        success: Whether the call succeeded.
        incident_id: Associated incident ID.
    """
    if not _otel_available:
        return

    tracer = get_tracer("aiops.bedrock")
    with tracer.start_as_current_span("gen_ai.invoke") as span:
        span.set_attribute("gen_ai.system", "aws.bedrock")
        span.set_attribute("gen_ai.request.model", model_id)
        span.set_attribute("gen_ai.usage.input_tokens", input_tokens)
        span.set_attribute("gen_ai.usage.output_tokens", output_tokens)
        span.set_attribute("gen_ai.response.latency_ms", latency_ms)
        span.set_attribute("aiops.incident_id", incident_id)

        if success:
            span.set_status(StatusCode.OK)
        else:
            span.set_status(StatusCode.ERROR, "Bedrock invocation failed")


def shutdown() -> None:
    """Flush and shut down the tracer provider. Called during graceful shutdown."""
    if _otel_available and _tracer_provider:
        _tracer_provider.shutdown()
        logger.info("TracerProvider shut down")
