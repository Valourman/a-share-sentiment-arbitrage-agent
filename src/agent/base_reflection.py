"""Backward-compatible import path for the canonical generic ReflectionAgent.

Generic paradigms live in ``src.agents``; ``src.agent`` contains the finance
application. Keep this module so existing callers do not need to migrate.
"""

from src.agents.reflection_agent import ReflectionAgent

__all__ = ["ReflectionAgent"]
