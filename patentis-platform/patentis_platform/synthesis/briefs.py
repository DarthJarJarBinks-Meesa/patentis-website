"""Structured opportunity briefs + feasibility gating."""

from __future__ import annotations

import uuid
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from patentis_platform.db.models import Organization, OpportunityBrief, PatentRecord, Project, TechnologyRegion
from patentis_platform.enterprise.interactions import format_org_profile_for_prompt, log_interaction
from patentis_platform.feasibility.pubmed import feasibility_from_keywords
from patentis_platform.enterprise.org_adapters import resolve_inference_adapter
from patentis_platform.synthesis.router import chat_json


FEASIBILITY_THRESHOLD = 0.25


def _mock_brief(region: TechnologyRegion, patents: list[PatentRecord]) -> dict[str, Any]:
    cites = [{"patent_id": p.external_id, "title": p.title} for p in patents[:5]]
    return {
        "title": f"Whitespace opportunity in {region.cpc_subclass}",
        "gap_summary": (
            f"Region {region.cpc_subclass} shows composite score "
            f"{region.composite_whitespace_score or 0:.2f} with scarcity-momentum signals."
        ),
        "why_exists": (
            "Fragmented assignee landscape and accelerating filings suggest room for differentiated claims."
        ),
        "assignee_landscape": f"HHI proxy {region.assignee_hhi:.3f}; top share {region.top_assignee_share:.2f}.",
        "enabling_science": "Linked literature review recommended — run FeasibilityPass agent.",
        "product_directions": [
            "Modular sensing layer decoupled from disposable consumable",
            "Edge-device inference with clinician-in-the-loop calibration",
        ],
        "confidence": 0.55,
        "disclaimers": (
            "Decision support only — not legal advice. Inventorship requires human contribution."
        ),
        "_citations": cites,
    }


async def generate_brief_for_region(
    session: AsyncSession,
    project_id: UUID,
    region_id: UUID,
    extra_context: str = "",
    actor_user_id: Optional[UUID] = None,
) -> OpportunityBrief:
    proj = await session.get(Project, project_id)
    if not proj:
        raise ValueError("Project not found")

    org = await session.get(Organization, proj.org_id)
    profile = org.profile_json if org and org.profile_json else {}
    company_ctx = format_org_profile_for_prompt(profile)

    region = await session.get(TechnologyRegion, region_id)
    if not region:
        raise ValueError("Region not found")

    p_res = await session.execute(
        select(PatentRecord).where(PatentRecord.cpc_subclass == region.cpc_subclass).limit(12)
    )
    patents = list(p_res.scalars().all())
    keywords = [region.cpc_subclass, "medical device", "diagnostic", "therapeutic"]
    feas = await feasibility_from_keywords(keywords)

    inference = await resolve_inference_adapter(session, proj.org_id)
    adapter_note = ""
    if inference.get("uses_customer_adapter"):
        adapter_note = (
            f"\nInference uses org-private LoRA overlay only for this tenant "
            f"(version {inference.get('org_lora_version')}, path scoped to org). "
            "Base Patentis-SFT was not trained on customer data.\n"
        )

    patent_context = "\n".join(f"- {p.external_id}: {p.title}\n  {p.abstract[:400]}" for p in patents)
    prompt_user = (
        f"Technology region CPC subclass: {region.cpc_subclass}\n"
        f"Feature summary: scarcity={region.scarcity_score:.2f}, "
        f"concentration={region.concentration_score:.2f}, momentum={region.momentum_score:.2f}\n"
        f"PubMed feasibility proxy: {feas['score']:.2f} (hit count {feas['hit_count']})\n"
        f"Representative patents:\n{patent_context}\n"
        f"Extra context from hybrid retrieval:\n{extra_context}\n\n"
        f"Company-specific profile (private tenant context — align suggestions with these strengths and boundaries):\n"
        f"{company_ctx}\n"
        f"{adapter_note}\n"
        "Return JSON with keys: title, gap_summary, why_exists, assignee_landscape, "
        "enabling_science, product_directions (array of strings), confidence (0-1), disclaimers."
    )
    parsed = await chat_json(
        system=(
            "You are Patentis, an innovation intelligence assistant. Produce concise, factual "
            "structured JSON only. Ground statements in supplied patents — do not invent "
            "legal positions. Humans must remain inventors. Prefer product_directions that "
            "fit the company's stated capabilities when supported by the patent evidence."
        ),
        user=prompt_user,
        temperature=0.25,
    )
    if not parsed:
        parsed = _mock_brief(region, patents)
    withheld = feas["score"] < FEASIBILITY_THRESHOLD
    cites = parsed.pop("_citations", None) or [
        {"patent_id": p.external_id, "title": p.title} for p in patents[:5]
    ]
    bid = uuid.uuid4()
    ob = OpportunityBrief(
        id=bid,
        project_id=project_id,
        region_id=region_id,
        payload=parsed if not withheld else {"withheld_reason": "Low scientific feasibility proxy"},
        citations=cites if not withheld else [],
        feasibility_score=feas["score"],
        withheld_low_feasibility=withheld,
    )
    session.add(ob)
    await log_interaction(
        session,
        org_id=proj.org_id,
        signal_type="brief_generated",
        payload={
            "region_id": str(region_id),
            "withheld": withheld,
            "feasibility": feas["score"],
            "title_preview": str(parsed.get("title", ""))[:400],
        },
        user_id=actor_user_id,
        project_id=project_id,
        resource_type="opportunity_brief",
        resource_id=str(bid),
    )
    await session.commit()
    await session.refresh(ob)
    return ob
