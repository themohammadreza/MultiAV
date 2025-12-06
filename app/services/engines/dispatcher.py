"""
Backwards-compatible dispatcher import.

The dispatcher has moved to ``app.services.orchestrator.dispatcher``.
"""

from app.services.orchestrator.dispatcher import run_all_engines  # noqa: F401
