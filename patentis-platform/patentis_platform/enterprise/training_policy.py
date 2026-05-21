"""
Enterprise ML training policy — enforced in code, not only docs.

Base Patentis-SFT:
  - Trains ONLY on public USPTO masked-patent supervision (masking_run_records).
  - NEVER on interaction_signals, opportunity_briefs, corpus_documents, org profiles, or DPO rows.

Per-org LoRA:
  - Trains ONLY when organization.training_opt_in is True.
  - Uses org-private preference data (expert ratings, DPO feedback) — never mixed into base SFT.
  - Weights stored at org-scoped blob paths; loaded only for that org's inference requests.
"""

from __future__ import annotations

BASE_SFT_ALLOWED_SOURCES = frozenset(
    {
        "masking_run_records",
        "uspto_bulk",
        "public_patent_corpus",
    }
)

FORBIDDEN_BASE_SFT_SOURCES = frozenset(
    {
        "interaction_signals",
        "opportunity_briefs",
        "corpus_documents",
        "organizations.profile_json",
        "dpo_feedback",
        "expert_ratings",
        "projects",
    }
)

BASE_SFT_POLICY_TEXT = (
    "Patentis-SFT (base) learns only from the public USPTO masked patent pipeline. "
    "No customer data is ever included in base model training."
)

ORG_ADAPTER_POLICY_TEXT = (
    "Per-organization LoRA adapters are optional. When enabled, adapters train privately on "
    "your org's preference signals, live in org-scoped storage, and are applied only to your "
    "organization's requests. Preferences do not leak to other tenants or the base model."
)

OPT_OUT_POLICY_TEXT = (
    "Opting out retires your adapter immediately and schedules deletion of interaction logs "
    "and adapter artifacts within 30 days."
)

RETENTION_DAYS_AFTER_OPT_OUT = 30


def assert_base_dataset_source(source: str) -> None:
    if source in FORBIDDEN_BASE_SFT_SOURCES:
        raise ValueError(
            f"Source '{source}' cannot be used for base Patentis-SFT training. "
            f"Allowed: {sorted(BASE_SFT_ALLOWED_SOURCES)}"
        )
    if source not in BASE_SFT_ALLOWED_SOURCES:
        raise ValueError(f"Unknown base SFT source '{source}' — add explicitly if public-only.")
