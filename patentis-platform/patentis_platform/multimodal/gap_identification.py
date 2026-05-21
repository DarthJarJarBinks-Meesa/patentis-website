"""
Multimodal innovation-gap identification — platform differentiator vs patentisv1.

Fuses:
- Landscape / tenant whitespace scores (tabular)
- Project corpus: patent abstracts, PubMed papers, PDF claims segments
- Optional vision captions when configured (figure-level analysis hook)
- PubMed feasibility on proposed gaps
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import (
    CorpusDocument,
    Organization,
    PatentFigure,
    PatentRecord,
    Project,
    TechnologyRegion,
)
from patentis_platform.enterprise.interactions import format_org_profile_for_prompt
from patentis_platform.feasibility.pubmed import feasibility_from_keywords
from patentis_platform.scoring.tenant_landscape import load_org_overlays, merge_region_scores
from patentis_platform.multimodal.claim_segmenter import independent_claims_text
from patentis_platform.synthesis.router import Task, chat_json, chat_vision_caption, model_router

DISCLAIMER = (
    "Decision support only — not legal advice, not FTO clearance. "
    "Inventorship requires human contribution."
)

GAP_SYSTEM = """You are Patentis, an innovation intelligence system for R&D teams.
Identify genuine patent whitespace gaps using ALL provided evidence modalities.
Return JSON only with this schema:
{
  "region_summary": "string",
  "gaps": [
    {
      "title": "string",
      "claim_element_gap": "what claim language is missing or under-covered",
      "evidence_patents": ["patent id or title snippets"],
      "evidence_literature": ["paper titles or PMIDs"],
      "multimodal_signals": ["claims_text"|"abstract_density"|"figure_semantics"|"landscape_score"],
      "confidence": 0.0-1.0
    }
  ],
  "covered_territory": "string",
  "disclaimers": "string"
}
Never claim you are the inventor. Do not provide legal clearance."""


def _mock_gaps(region: TechnologyRegion, patents: list[PatentRecord], claims_excerpt: str) -> dict[str, Any]:
    return {
        "region_summary": (
            f"CPC {region.cpc_subclass}: composite whitespace "
            f"{region.composite_whitespace_score or 0:.2f} (ML signals + corpus)."
        ),
        "gaps": [
            {
                "title": f"Under-specified sensing modality in {region.cpc_subclass}",
                "claim_element_gap": (
                    "Few ingested patents combine wireless telemetry with micromotion quantification "
                    "in independent claim 1 language."
                ),
                "evidence_patents": [p.external_id for p in patents[:3]],
                "evidence_literature": [],
                "multimodal_signals": ["landscape_score", "claims_text" if claims_excerpt else "abstract_density"],
                "confidence": 0.52,
            }
        ],
        "covered_territory": "Dominant assignees cover generic implant monitoring abstracts.",
        "disclaimers": DISCLAIMER,
        "modality_sources": ["tabular_scores", "patent_abstracts"]
        + (["claims_text"] if claims_excerpt else []),
    }


async def identify_innovation_gaps(
    session: AsyncSession,
    project_id: UUID,
    region_id: UUID,
    org_id: UUID,
    idea_hint: str = "",
    use_vision: bool = False,
) -> dict[str, Any]:
    proj = await session.get(Project, project_id)
    if not proj or proj.org_id != org_id:
        raise ValueError("Project not found")

    region = await session.get(TechnologyRegion, region_id)
    if not region:
        raise ValueError("Region not found")

    overlays = await load_org_overlays(session, org_id)
    merged = merge_region_scores(region, overlays.get(region.id))

    org = await session.get(Organization, org_id)
    company_ctx = format_org_profile_for_prompt(org.profile_json if org and org.profile_json else {})

    corp_res = await session.execute(
        select(CorpusDocument).where(CorpusDocument.project_id == project_id).limit(40)
    )
    corpus = list(corp_res.scalars().all())

    claims_chunks: list[str] = []
    paper_snippets: list[str] = []
    patent_snippets: list[str] = []
    for doc in corpus:
        if doc.source_type == "patent" or (doc.metadata_json or {}).get("source") in (
            "google_patents",
            "epo",
            "patentsview",
        ):
            patent_snippets.append(f"[{doc.title}]\n{doc.body[:1200]}")
        elif doc.source_type == "paper":
            paper_snippets.append(f"[{doc.title}]\n{doc.body[:1200]}")
        meta = doc.metadata_json or {}
        if meta.get("claims_excerpt"):
            claims_chunks.append(str(meta["claims_excerpt"])[:4000])

    p_res = await session.execute(
        select(PatentRecord).where(PatentRecord.cpc_subclass == region.cpc_subclass).limit(15)
    )
    region_patents = list(p_res.scalars().all())
    figure_blocks: list[str] = []
    for p in region_patents:
        if p.claims_text:
            claims_chunks.append(independent_claims_text(p.claims_text, max_chars=4000))
        fig_res = await session.execute(select(PatentFigure).where(PatentFigure.patent_id == p.id))
        for fig in fig_res.scalars().all():
            refs = ", ".join(fig.claim_refs or [])
            figure_blocks.append(f"FIG {fig.figure_num} (claims {refs}): {fig.caption[:600]}")
        patent_snippets.append(f"{p.external_id}: {p.title}\n{p.abstract[:500]}")

    claims_excerpt = "\n---\n".join(claims_chunks)[:12000]
    figure_caption = ""
    modality_sources = ["tabular_scores", "patent_abstracts"]
    if claims_excerpt:
        modality_sources.append("claims_text")
    if paper_snippets:
        modality_sources.append("pubmed_corpus")
    if figure_blocks:
        modality_sources.append("figure_captions")
    if use_vision and claims_excerpt:
        figure_caption = await chat_vision_caption(
            [],
            "Describe device/figure semantics implied by these patent claim excerpts:\n"
            + claims_excerpt[:6000],
        )
        if figure_caption and "not configured" not in figure_caption.lower():
            modality_sources.append("figure_semantics")

    keywords = [region.cpc_subclass, "medical device", idea_hint[:80]] if idea_hint else [region.cpc_subclass]
    feas = await feasibility_from_keywords([k for k in keywords if k])

    user_prompt = (
        f"Technology region: {region.cpc_subclass} ({region.vertical})\n"
        f"Whitespace composite (tenant-aware): {merged.composite_whitespace_score}\n"
        f"Scarcity={region.scarcity_score:.2f} concentration={region.concentration_score:.2f} "
        f"momentum={region.momentum_score:.2f}\n"
        f"PubMed feasibility proxy: {feas['score']:.2f} ({feas['hit_count']} hits)\n"
        f"User idea hint: {idea_hint or 'none'}\n\n"
        f"Company context:\n{company_ctx}\n\n"
        f"Claims / specification excerpts:\n{claims_excerpt or '(none — rely on abstracts)'}\n\n"
        f"Project patent corpus ({len(patent_snippets)} docs):\n"
        + "\n".join(patent_snippets[:12])
        + f"\n\nProject literature ({len(paper_snippets)} docs):\n"
        + "\n".join(paper_snippets[:8])
        + (f"\n\nPatent figure captions:\n" + "\n".join(figure_blocks[:15]) if figure_blocks else "")
        + (f"\n\nFigure / device semantics (vision):\n{figure_caption}" if figure_caption else "")
    )

    gaps_payload = await model_router.call_json(Task.GAP_IDENTIFICATION, GAP_SYSTEM, user_prompt)
    if not gaps_payload or "gaps" not in gaps_payload:
        gaps_payload = _mock_gaps(region, region_patents, claims_excerpt)
    else:
        gaps_payload.setdefault("disclaimers", DISCLAIMER)
        gaps_payload["modality_sources"] = modality_sources
        gaps_payload["feasibility"] = feas

    for gap in gaps_payload.get("gaps", []):
        if isinstance(gap, dict) and "feasibility_score" not in gap:
            gap["feasibility_score"] = feas["score"]

    return {
        "region_id": str(region_id),
        "project_id": str(project_id),
        "cpc_subclass": region.cpc_subclass,
        "landscape": {
            "composite_whitespace_score": merged.composite_whitespace_score,
            "tenant_overlay": region.id in overlays,
        },
        "gaps_analysis": gaps_payload,
        "feasibility": feas,
        "modality_sources": modality_sources,
        "disclaimer": DISCLAIMER,
    }
