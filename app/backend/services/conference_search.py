import os
from datetime import date

import httpx
import numpy as np

from models.schemas import Paper
from services.conference_registry import matches_registry
from services.rag import embed_texts

OPENALEX_WORKS = "https://api.openalex.org/works"
# OpenAlex asks for a contact email to route requests to its faster "polite pool" — optional.
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

CONFERENCE_YEARS_BACK = int(os.getenv("CONFERENCE_YEARS_BACK", "2"))
CONFERENCE_SEARCH_LIMIT = int(os.getenv("CONFERENCE_SEARCH_LIMIT", "10"))

# RRF constant — standard choice from the reciprocal-rank-fusion literature, not
# tuned for this data; it just controls how quickly rank position decays into score.
_RRF_K = 60
_VENUE_BOOST = 0.15


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """OpenAlex ships abstracts as a word -> [positions] inverted index, not plain text."""
    if not inverted_index:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inverted_index.items():
        for i in idxs:
            positions[i] = word
    return " ".join(positions[i] for i in sorted(positions))


def _build_boolean_query(keywords: list[str], wide: bool) -> str:
    """OpenAlex's `search` param parses inline AND/OR/NOT tokens and quoted phrases
    (verified against the live API), so this builds a real boolean query rather than
    relying on OpenAlex's own implicit term-matching over a space-joined string.

    `wide=False` -> tight AND of the top terms (precision pass).
    `wide=True`  -> two OR-groups ANDed together (recall pass, used when the tight
    pass is thin — see the comment below on why a flat OR-of-everything is too loose).
    """
    terms = [kw.strip() for kw in keywords if kw.strip()]
    if not terms:
        return ""
    if not wide:
        terms = terms[:4]
        if len(terms) == 1:
            return f'"{terms[0]}"'
        return " AND ".join(f'"{t}"' for t in terms)

    # Wide pass: split into two concept groups (OpenAlex's search parser supports
    # parens, verified against the live API) — OR within each half, AND across the
    # halves. A flat OR across every term is too loose: a single broad phrase like
    # "load distribution" alone pulls in completely unrelated fields (power systems,
    # pavement engineering) that happen to share it, with nothing anchoring the query
    # back to the actual subject.
    terms = terms[:8]
    if len(terms) <= 2:
        return " OR ".join(f'"{t}"' for t in terms)
    mid = max(1, len(terms) // 2)
    group_a = " OR ".join(f'"{t}"' for t in terms[:mid])
    group_b = " OR ".join(f'"{t}"' for t in terms[mid:])
    return f"({group_a}) AND ({group_b})"


async def _fetch_openalex(search_query: str, cutoff: str, limit: int) -> list[dict]:
    if not search_query:
        return []
    params = {
        "search": search_query,
        "filter": f"type:conference-paper,from_publication_date:{cutoff}",
        "per-page": limit,
        "sort": "relevance_score:desc",
    }
    if OPENALEX_MAILTO:
        params["mailto"] = OPENALEX_MAILTO

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                OPENALEX_WORKS,
                params=params,
                headers={"User-Agent": "Patentis/1.0 (research tool)"},
            )
            resp.raise_for_status()
            return resp.json().get("results", [])
    except Exception:
        return []


def _to_paper(item: dict) -> Paper | None:
    title = (item.get("display_name") or item.get("title") or "").strip()
    if not title:
        return None

    abstract = _reconstruct_abstract(item.get("abstract_inverted_index"))

    authors = [
        a.get("author", {}).get("display_name", "")
        for a in item.get("authorships", [])
        if a.get("author", {}).get("display_name")
    ][:6]

    published = item.get("publication_date") or (
        str(item["publication_year"]) if item.get("publication_year") else ""
    )

    source_info = item.get("primary_location", {}).get("source") or {}
    venue = source_info.get("display_name") or item.get("host_venue", {}).get("display_name")

    url = (
        item.get("primary_location", {}).get("landing_page_url")
        or item.get("doi")
        or item.get("id", "")
    )

    work_id = item.get("id", "").rsplit("/", 1)[-1]

    return Paper(
        id=f"oa_{work_id or title[:40]}",
        title=title,
        abstract=abstract,
        authors=authors,
        published=published,
        venue=venue,
        url=url,
        source="conference",
        relevance_score=item.get("relevance_score"),
    )


def _rerank_hybrid(
    papers: list[Paper],
    lexical_order: list[str],
    query_text: str,
    domains: list[str] | None,
) -> list[Paper]:
    """Fuse OpenAlex's lexical ranking with a semantic similarity ranking via
    reciprocal rank fusion, then apply a small boost for known medtech venues.

    This is a re-ranking step over OpenAlex's own candidate set, not a from-scratch
    vector search — building and maintaining a separate crawled index of conference
    abstracts is a much larger, ongoing undertaking than re-scoring the ~20-50
    candidates OpenAlex already retrieved for us.
    """
    if not papers:
        return []

    lexical_rank = {pid: i for i, pid in enumerate(lexical_order)}

    doc_texts = [f"{p.title}. {p.abstract[:600]}" for p in papers]
    query_vec = embed_texts([query_text])[0]
    doc_vecs = embed_texts(doc_texts)

    q = np.array(query_vec)
    d = np.array(doc_vecs)
    q_norm = q / (np.linalg.norm(q) + 1e-9)
    d_norms = d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-9)
    similarities = d_norms @ q_norm  # cosine similarity, one per paper

    semantic_order = [papers[i].id for i in np.argsort(-similarities)]
    semantic_rank = {pid: i for i, pid in enumerate(semantic_order)}

    scored: list[tuple[float, Paper]] = []
    for paper in papers:
        l_rank = lexical_rank.get(paper.id, len(papers))
        s_rank = semantic_rank.get(paper.id, len(papers))
        score = 1.0 / (_RRF_K + l_rank) + 1.0 / (_RRF_K + s_rank)

        matched = matches_registry(paper.venue, domains)
        paper.matched_venue = matched
        if matched:
            score += _VENUE_BOOST * score

        scored.append((score, paper))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    if scored:
        max_score = scored[0][0] or 1.0
        for score, paper in scored:
            paper.relevance_score = round(score / max_score, 4)

    return [paper for _, paper in scored]


async def search_conference_papers(
    keywords: list[str],
    query: str = "",
    years_back: int = CONFERENCE_YEARS_BACK,
    limit: int = CONFERENCE_SEARCH_LIMIT,
    domains: list[str] | None = None,
    venue_only: bool = False,
) -> list[Paper]:
    """
    Find recent conference proceedings papers relevant to `keywords`, ranked by a
    fusion of boolean lexical matching (OpenAlex) and semantic similarity to `query`.

    Conference papers surface new materials, designs, and methods faster than journal
    publication cycles, so this is used both to enrich idea generation and to widen the
    RAG corpus consulted during product-development chat.
    """
    if not keywords:
        return []

    cutoff = date.today().replace(year=date.today().year - years_back).isoformat()
    fetch_limit = max(limit * 3, 30)  # over-fetch candidates so re-ranking has room to work

    tight_query = _build_boolean_query(keywords, wide=False)
    raw_items = await _fetch_openalex(tight_query, cutoff, fetch_limit)

    if len(raw_items) < limit:
        wide_query = _build_boolean_query(keywords, wide=True)
        wide_items = await _fetch_openalex(wide_query, cutoff, fetch_limit)
        seen_ids = {item.get("id") for item in raw_items}
        raw_items.extend(item for item in wide_items if item.get("id") not in seen_ids)

    # raw_items is already relevance-ordered (tight pass first, wide-pass extras
    # appended after) — build papers and the matching lexical rank in one pass so
    # they can't drift apart.
    papers: list[Paper] = []
    lexical_order: list[str] = []
    seen_titles: set[str] = set()
    for item in raw_items:
        paper = _to_paper(item)
        if paper is None:
            continue
        title_key = paper.title.lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)
        papers.append(paper)
        lexical_order.append(paper.id)

    if venue_only:
        papers = [p for p in papers if matches_registry(p.venue, domains)]

    if not papers:
        return []

    query_text = query.strip() or " ".join(keywords)
    ranked = _rerank_hybrid(papers, lexical_order, query_text, domains)

    return ranked[:limit]
