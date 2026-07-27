"""Curated medtech conference venues used to scope/boost conference-paper search.

OpenAlex indexes conference proceedings from Crossref but has no clean "is this a
medtech conference" filter, and resolving each society's proceedings to a stable
OpenAlex source ID is brittle (societies rotate publishers/proceedings series across
years). Matching on venue display_name substrings instead is a few points less precise
but doesn't silently break when a source ID changes upstream.

Domains are an allowlist, not a taxonomy — extend in place as new focus areas come up.
"""

CONFERENCE_REGISTRY: dict[str, list[str]] = {
    "orthopedics_spine": [
        "North American Spine Society",
        "NASS",
        "American Academy of Orthopaedic Surgeons",
        "AAOS",
        "International Society for the Advancement of Spine Surgery",
        "ISASS",
        "Orthopaedic Research Society",
        "Scoliosis Research Society",
        "Cervical Spine Research Society",
        "EFORT",
    ],
    "cardiovascular": [
        "Transcatheter Cardiovascular Therapeutics",
        "EuroPCR",
        "American College of Cardiology",
        "Heart Rhythm Society",
        "American Heart Association",
    ],
    "neuro": [
        "American Association of Neurological Surgeons",
        "Congress of Neurological Surgeons",
        "Society for Neuroscience",
    ],
    "general_biomedical": [
        "IEEE Engineering in Medicine and Biology",
        "EMBC",
        "Biomedical Engineering Society",
        "Radiological Society of North America",
        "RSNA",
        "World Congress of Biomechanics",
        "Design of Medical Devices",
    ],
}


def venue_terms(domains: list[str] | None = None) -> list[str]:
    keys = domains if domains else list(CONFERENCE_REGISTRY)
    terms: list[str] = []
    for key in keys:
        terms.extend(CONFERENCE_REGISTRY.get(key, []))
    return terms


def matches_registry(venue_name: str | None, domains: list[str] | None = None) -> bool:
    if not venue_name:
        return False
    venue_lower = venue_name.lower()
    return any(term.lower() in venue_lower for term in venue_terms(domains))
