"""Shared state backends for multi-task ECS scaling.

Provides a Redis/ElastiCache-backed shared state layer that allows
storm detection, alert inhibition, and resolved tracking to work
correctly across multiple ECS tasks.

When REDIS_URL is set, components use Redis for shared counters,
sets, and hashes. When not set, falls back to in-memory (single-task only).
"""
