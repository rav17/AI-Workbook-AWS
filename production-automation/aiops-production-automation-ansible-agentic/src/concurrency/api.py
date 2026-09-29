"""FastAPI router for concurrency status and circuit breaker management."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/concurrency", tags=["concurrency"])

# Module-level reference to the ConcurrencyManager (set during app startup)
_concurrency_manager = None
_circuit_breaker_manager = None
_fleet_breaker = None
_bulkhead_manager = None


def configure_router(
    concurrency_manager,
    circuit_breaker_manager,
    fleet_breaker=None,
    bulkhead_manager=None,
) -> None:
    """Configure the router with runtime dependencies.

    Called during application startup to inject the manager instances.
    """
    global _concurrency_manager, _circuit_breaker_manager, _fleet_breaker, _bulkhead_manager
    _concurrency_manager = concurrency_manager
    _circuit_breaker_manager = circuit_breaker_manager
    _fleet_breaker = fleet_breaker
    _bulkhead_manager = bulkhead_manager


class ConcurrencyStatusResponse(BaseModel):
    """Response model for the concurrency status endpoint."""

    active_locks: int = Field(description="Number of active host locks")
    active_executions: dict = Field(description="Active execution details (max 1000)")
    queue_depths: dict[str, int] = Field(description="Queue depth per host")
    total_active_executions: int = Field(description="Total active execution count")


class ResetResponse(BaseModel):
    """Response model for circuit breaker reset."""

    success: bool
    previous_state: Optional[str] = None
    message: str


@router.get("/status", response_model=ConcurrencyStatusResponse)
async def get_concurrency_status() -> ConcurrencyStatusResponse:
    """Return current concurrency status including locks, queues, and circuit breakers.

    Returns active Host_Locks, Priority_Queue depths per host,
    Circuit_Breaker_States, and active Suppression_Window entries.
    Capped at 1000 entries per category.
    """
    if _concurrency_manager is None:
        raise HTTPException(
            status_code=503, detail="Concurrency manager not initialized"
        )

    status = _concurrency_manager.get_status()
    return ConcurrencyStatusResponse(**status)


@router.post("/circuit-breaker/{host}/reset", response_model=ResetResponse)
async def reset_circuit_breaker(host: str) -> ResetResponse:
    """Manually reset the circuit breaker for a specific host.

    Transitions the state from OPEN or HALF_OPEN to CLOSED, resetting
    the failure counter. Returns success even if already CLOSED.
    Returns 404 if the host has no circuit breaker state.
    """
    if _circuit_breaker_manager is None:
        raise HTTPException(
            status_code=503, detail="Circuit breaker manager not initialized"
        )

    result = await _circuit_breaker_manager.manual_reset(host)

    if not result.success and "not found" in result.message.lower():
        raise HTTPException(status_code=404, detail=result.message)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.message)

    return ResetResponse(
        success=result.success,
        previous_state=result.previous_state.value if result.previous_state else None,
        message=result.message,
    )


@router.get("/fleet-breaker/status")
async def get_fleet_breaker_status() -> dict:
    """Return fleet-wide circuit breaker status.

    Shows: state (closed/open/recovering), failures in window,
    threshold, cooldown remaining, ramp-up level.
    """
    if _fleet_breaker is None:
        return {"enabled": False, "state": "not_initialized"}

    return _fleet_breaker.get_status()


@router.post("/fleet-breaker/reset")
async def reset_fleet_breaker() -> dict:
    """Manually reset the fleet-wide circuit breaker to CLOSED.

    Use when you've confirmed the fleet issue is resolved and want to
    resume automation immediately (without waiting for cooldown).
    """
    if _fleet_breaker is None:
        raise HTTPException(
            status_code=503, detail="Fleet breaker not initialized"
        )

    message = _fleet_breaker.manual_reset()
    return {"success": True, "message": message}


@router.get("/bulkheads/status")
async def get_bulkhead_status() -> dict:
    """Return per-service bulkhead utilization.

    Shows: per-service active/available slots, global utilization,
    P1 reserved capacity.
    """
    if _bulkhead_manager is None:
        return {"enabled": False, "message": "Bulkhead manager not initialized"}

    return _bulkhead_manager.get_status()


@router.get("/poisoned-hosts")
async def get_poisoned_hosts() -> dict:
    """Return list of poisoned (unreachable) hosts.

    Poisoned hosts have all queued actions rejected until they are
    unpoisoned (manual or via successful health probe).
    """
    from src.concurrency.host_poisoning import HostPoisonManager
    # Access via module-level import pattern
    if _concurrency_manager is None:
        return {"hosts": [], "message": "Not initialized"}

    poison_mgr = getattr(_concurrency_manager, "_poison_manager", None)
    if poison_mgr is None:
        return {"hosts": [], "message": "Host poisoning not configured"}

    return {"hosts": poison_mgr.get_poisoned_hosts()}


@router.post("/hosts/{host}/unpoison")
async def unpoison_host(host: str) -> dict:
    """Manually unpoison a host (allow actions to resume).

    Use when a host has been repaired/replaced and should accept
    automation again.
    """
    if _concurrency_manager is None:
        raise HTTPException(status_code=503, detail="Not initialized")

    poison_mgr = getattr(_concurrency_manager, "_poison_manager", None)
    if poison_mgr is None:
        raise HTTPException(status_code=503, detail="Host poisoning not configured")

    success = poison_mgr.unpoison(host)
    if success:
        return {"success": True, "message": f"Host '{host}' unpoisoned"}
    else:
        raise HTTPException(status_code=404, detail=f"Host '{host}' is not poisoned")
