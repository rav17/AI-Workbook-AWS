from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from weakref import WeakValueDictionary

from aria.agents.aria.receivables.models import AuthoritySource, TrustedContext

# Process-local issuance, not production authentication.
# Serialized/copied models carry no authority.
_issued: WeakValueDictionary[int, TrustedContext] = WeakValueDictionary()


def _issue(context: TrustedContext) -> TrustedContext:
    _issued[id(context)] = context
    return context


class UntrustedContextError(ValueError):
    """The caller did not provide an independently trusted identity context."""


def synthetic_harness_context(
    *, tenant_id: str, user_id: str, session_id: str, correlation_id: str
) -> TrustedContext:
    if tenant_id != "TENANT-SYN-001":
        raise UntrustedContextError("synthetic tenant is outside the approved scope")
    return _issue(
        TrustedContext(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            correlation_id=correlation_id,
            authority_source=AuthoritySource.SYNTHETIC_HARNESS,
        )
    )


def context_from_provider(provider: Any) -> TrustedContext:
    if provider is None or not callable(getattr(provider, "trusted_context", None)):
        raise UntrustedContextError("a separately trusted context provider is required")
    value = provider.trusted_context()
    if isinstance(value, TrustedContext):
        context = value
    elif isinstance(value, Mapping):
        context = TrustedContext.model_validate(value)
    else:
        raise UntrustedContextError("trusted provider returned an invalid context")
    if context.authority_source != AuthoritySource.TRUSTED_SERVER_PROVIDER:
        raise UntrustedContextError("provider context has the wrong authority source")
    return _issue(context)


def require_context(context: TrustedContext, *, tenant_id: str | None = None) -> TrustedContext:
    if not isinstance(context, TrustedContext):
        raise UntrustedContextError("typed trusted context is required")
    if _issued.get(id(context)) is not context:
        raise UntrustedContextError("context was not issued by the harness or trusted provider")
    if tenant_id is not None and context.tenant_id != tenant_id:
        raise UntrustedContextError("tenant scope mismatch")
    if context.analyst_role != "receivables_operations_analyst":
        raise UntrustedContextError("analyst role is not authorized in the synthetic harness")
    return context


def reject_payload_identity(payload: Mapping[str, Any]) -> None:
    identity_fields = {
        "_verified_principal",
        "tenant_id",
        "user_id",
        "session_id",
        "analyst_id",
        "analyst_role",
    }
    if identity_fields.intersection(payload):
        raise UntrustedContextError("identity fields are not accepted from request payloads")
