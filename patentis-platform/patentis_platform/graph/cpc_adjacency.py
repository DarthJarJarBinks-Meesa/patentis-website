"""CPC subclass adjacency for related-subgroup patent ingest and neighbor features."""

from __future__ import annotations

from patentis_platform.config import get_settings

# Medtech-focused adjacency (subclass + near neighbors). Extend via bulk CPC scheme later.
_MEDTECH_EDGES: list[tuple[str, str, str]] = [
    ("A61B", "A61B5", "child"),
    ("A61B", "A61B17", "child"),
    ("A61B", "A61B18", "child"),
    ("A61B5", "A61B", "parent"),
    ("A61B17", "A61B", "parent"),
    ("A61B18", "A61B", "parent"),
    ("A61F", "A61F2", "child"),
    ("A61F", "A61F13", "child"),
    ("A61F2", "A61F", "parent"),
    ("A61F13", "A61F", "parent"),
    ("A61N", "A61N1", "child"),
    ("A61N1", "A61N", "parent"),
    ("A61B", "A61F", "sibling"),
    ("A61F", "A61B", "sibling"),
    ("A61B", "A61N", "sibling"),
    ("A61N", "A61B", "sibling"),
    ("A61F", "A61N", "sibling"),
    ("A61N", "A61F", "sibling"),
]


def default_medtech_edges() -> list[tuple[str, str, str]]:
    return list(_MEDTECH_EDGES)


def adjacent_subclasses(cpc: str, include_self: bool = False) -> list[str]:
    """Return subclass + neighbors from static medtech graph."""
    out: set[str] = {cpc} if include_self else set()
    for a, b, _ in _MEDTECH_EDGES:
        if a == cpc:
            out.add(b)
        if b == cpc:
            out.add(a)
    if include_self:
        out.add(cpc)
    return sorted(out)


def active_cpc_prefixes() -> list[str]:
    settings = get_settings()
    return [p.strip() for p in settings.medtech_cpc_prefixes.split(",") if p.strip()]


def expanded_ingest_prefixes() -> list[str]:
    """Root prefixes plus one-hop adjacent subclasses for ingestion."""
    roots = active_cpc_prefixes()
    expanded: set[str] = set(roots)
    for r in roots:
        for n in adjacent_subclasses(r, include_self=True):
            if n.startswith(tuple(roots)) or any(n.startswith(root) for root in roots):
                expanded.add(n)
            else:
                expanded.add(n)
    return sorted(expanded)
