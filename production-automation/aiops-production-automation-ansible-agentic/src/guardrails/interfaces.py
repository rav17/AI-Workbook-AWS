"""Protocol interfaces for the Safe Execution Guardrails module."""

from typing import Protocol, runtime_checkable

from src.guardrails.models import CheckResult, RemediationAction


@runtime_checkable
class GuardrailCheck(Protocol):
    """Protocol for a single guardrail check in the evaluation chain."""

    @property
    def name(self) -> str:
        """Unique name identifying this guardrail check."""
        ...

    async def check(self, action: RemediationAction) -> CheckResult:
        """Evaluate the action against this guardrail.

        Args:
            action: The remediation action to evaluate.

        Returns:
            CheckResult indicating ALLOW, DENY, or DEFER.
        """
        ...


@runtime_checkable
class LockStore(Protocol):
    """Protocol for distributed lock storage."""

    async def acquire_lock(self, key: str, holder: str, ttl_seconds: int) -> bool:
        """Acquire a distributed lock.

        Args:
            key: Lock key identifier.
            holder: Identity of the lock holder.
            ttl_seconds: Time-to-live in seconds.

        Returns:
            True if lock was acquired, False if already held.
        """
        ...

    async def release_lock(self, key: str, holder: str) -> bool:
        """Release a distributed lock.

        Args:
            key: Lock key identifier.
            holder: Identity of the lock holder.

        Returns:
            True if lock was released, False if not held by this holder.
        """
        ...

    async def is_locked(self, key: str) -> bool:
        """Check if a lock is currently held.

        Args:
            key: Lock key identifier.

        Returns:
            True if the lock is held, False otherwise.
        """
        ...


@runtime_checkable
class ServiceRegistry(Protocol):
    """Protocol for querying service instance information."""

    async def get_instance_count(self, service_name: str) -> int:
        """Get the number of instances for a service.

        Args:
            service_name: Name of the service.

        Returns:
            Number of registered instances.
        """
        ...

    async def get_healthy_instances(self, service_name: str) -> list[str]:
        """Get list of healthy instance hostnames for a service.

        Args:
            service_name: Name of the service.

        Returns:
            List of healthy instance hostnames.
        """
        ...


@runtime_checkable
class LoadBalancerClient(Protocol):
    """Protocol for load balancer operations."""

    async def deregister_target(self, target_group: str, instance_id: str) -> bool:
        """Remove an instance from a load balancer target group.

        Args:
            target_group: Target group ARN or name.
            instance_id: Instance to deregister.

        Returns:
            True if deregistered successfully.
        """
        ...

    async def register_target(self, target_group: str, instance_id: str) -> bool:
        """Add an instance to a load balancer target group.

        Args:
            target_group: Target group ARN or name.
            instance_id: Instance to register.

        Returns:
            True if registered successfully.
        """
        ...

    async def is_target_active(self, target_group: str, instance_id: str) -> bool:
        """Check if an instance is in the active target list.

        Args:
            target_group: Target group ARN or name.
            instance_id: Instance to check.

        Returns:
            True if the instance is actively serving traffic.
        """
        ...
