"""Shared pytest configuration.

``src.settings`` requires ``TAVILY_API_KEY`` with no default, so importing any
``src.agents.*`` module (even just to inspect a subagent spec, with no network
calls) fails collection unless the environment already has it set. Provide a
harmless placeholder for tests that only need the import to succeed.
"""

import os

os.environ.setdefault("TAVILY_API_KEY", "test-placeholder")
