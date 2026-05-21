"""Org-scoped LoRA adapter storage (local path or Azure Blob URI)."""

from __future__ import annotations

import shutil
from pathlib import Path
from uuid import UUID

from patentis_platform.config import get_settings


def org_adapter_blob_path(org_id: UUID, version: str = "latest") -> str:
    """Canonical storage key / relative path for an org's LoRA weights."""
    settings = get_settings()
    prefix = settings.org_adapters_blob_prefix.rstrip("/")
    return f"{prefix}/{org_id}/lora-{version}/"


def org_adapter_local_dir(org_id: UUID, version: str = "latest") -> Path:
    """Dev/local filesystem mirror of org-scoped blob layout."""
    settings = get_settings()
    base = Path(settings.org_adapters_local_root)
    rel = org_adapter_blob_path(org_id, version)
    return base / rel


def write_adapter_placeholder(org_id: UUID, version: str, metadata: dict) -> str:
    """
    Persist adapter manifest locally (production: upload to Azure Blob container).
    Returns blob URI/path string stored on OrgModelAdapter.
    """
    import json

    d = org_adapter_local_dir(org_id, version)
    d.mkdir(parents=True, exist_ok=True)
    manifest = d / "adapter_manifest.json"
    manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return org_adapter_blob_path(org_id, version)


def delete_adapter_artifacts(org_id: UUID) -> bool:
    """Remove all local adapter files for an org (blob purge uses same prefix in production)."""
    settings = get_settings()
    root = Path(settings.org_adapters_local_root) / settings.org_adapters_blob_prefix.strip("/")
    org_dir = root / str(org_id)
    if org_dir.exists():
        shutil.rmtree(org_dir)
        return True
    return False
