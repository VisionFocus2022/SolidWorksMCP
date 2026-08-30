"""Per-domain tool registry (N14): server.py's tool surface, split by domain.

Each module exposes ``register(mcp)`` and decorates its own verbatim-moved
tool functions; :func:`register_all` wires every domain onto the FastMCP
instance owned by :mod:`solidworks_mcp.server`. Product tools
(:mod:`.products`) register only under their env gate.
"""

from __future__ import annotations

from . import (
    assembly,
    drawing,
    features,
    file_io,
    misc,
    part,
    products,
    prompts,
    properties,
)

_DOMAINS = (
    misc,
    part,
    features,
    properties,
    file_io,
    drawing,
    assembly,
    prompts,
    products,
)


def register_all(mcp) -> int:
    """Register every domain; returns the number of domains registered."""
    for domain in _DOMAINS:
        domain.register(mcp)
    return len(_DOMAINS)
