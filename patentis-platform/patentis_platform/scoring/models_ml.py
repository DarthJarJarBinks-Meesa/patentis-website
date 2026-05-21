"""Feature vectors and sklearn models for whitespace scoring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from patentis_platform.db.models import TechnologyRegion


FEATURE_COLUMNS = (
    "patent_count",
    "neighbor_avg_count",
    "assignee_hhi",
    "top_assignee_share",
    "filing_growth_rate",
    "citation_acceleration",
    "pubmed_velocity",
    "semantic_sparsity",
    "scarcity_score",
    "concentration_score",
    "momentum_score",
)


def region_to_features(reg: TechnologyRegion) -> np.ndarray:
    return np.array(
        [
            np.log1p(reg.patent_count),
            np.log1p(reg.neighbor_avg_count),
            reg.assignee_hhi,
            reg.top_assignee_share,
            reg.filing_growth_rate,
            reg.citation_acceleration,
            reg.pubmed_velocity,
            reg.semantic_sparsity,
            reg.scarcity_score,
            reg.concentration_score,
            reg.momentum_score,
        ],
        dtype=np.float64,
    )


def stack_regions(regions: list[TechnologyRegion]) -> tuple[np.ndarray, np.ndarray]:
    X = np.vstack([region_to_features(r) for r in regions])
    y = np.array(
        [
            r.expert_calibration_label
            if r.expert_calibration_label is not None
            else 0.5 * (r.scarcity_score + r.momentum_score)
            for r in regions
        ],
        dtype=np.float64,
    )
    return X, y


def artifacts_dir() -> Path:
    base = Path(__file__).resolve().parent / "artifacts"
    base.mkdir(parents=True, exist_ok=True)
    return base


def model_joblib_path(org_id: str | None = None) -> Path:
    ad = artifacts_dir()
    if org_id:
        return ad / f"whitespace_models_org_{org_id}.joblib"
    return ad / "whitespace_models.joblib"


def train_and_save(regions: list[TechnologyRegion], org_id: str | None = None) -> dict:
    import joblib
    from sklearn.ensemble import IsolationForest, RandomForestRegressor

    if len(regions) < 2:
        raise ValueError("Need at least 2 regions to train")
    X, y = stack_regions(regions)
    iforest = IsolationForest(
        n_estimators=200,
        contamination=0.15,
        random_state=42,
    )
    iforest.fit(X)
    raw_if = iforest.decision_function(X)
    if_score = (raw_if - raw_if.min()) / (raw_if.max() - raw_if.min() + 1e-9)

    rf = RandomForestRegressor(n_estimators=200, max_depth=6, random_state=42)
    rf.fit(X, y)
    rf_pred = rf.predict(X)
    rf_norm = (rf_pred - rf_pred.min()) / (rf_pred.max() - rf_pred.min() + 1e-9)

    composite = 0.45 * if_score + 0.55 * rf_norm

    out = {
        "isolation_forest": iforest,
        "random_forest": rf,
        "last_region_ids": [str(r.id) for r in regions],
        "org_id": org_id,
    }
    path = model_joblib_path(org_id)
    joblib.dump(out, path)

    scores = [{"if": float(a), "rf": float(b), "composite": float(c)} for a, b, c in zip(if_score, rf_norm, composite)]
    return {"scores": scores, "artifact_path": str(path)}


def load_models(org_id: str | None = None):
    import joblib

    path = model_joblib_path(org_id)
    if not path.exists():
        return None
    return joblib.load(path)


def apply_saved_models(regions: list[TechnologyRegion], org_id: str | None = None) -> list[dict]:
    bundle = load_models(org_id)
    if not bundle and org_id:
        bundle = load_models(None)
    if not bundle:
        return []
    iforest: Any = bundle["isolation_forest"]
    rf: Any = bundle["random_forest"]
    X = np.vstack([region_to_features(r) for r in regions])
    raw_if = iforest.decision_function(X)
    if_score = (raw_if - raw_if.min()) / (raw_if.max() - raw_if.min() + 1e-9)
    rf_pred = rf.predict(X)
    rf_norm = (rf_pred - rf_pred.min()) / (rf_pred.max() - rf_pred.min() + 1e-9)
    composite = 0.45 * if_score + 0.55 * rf_norm
    return [
        {"if": float(a), "rf": float(b), "composite": float(c)}
        for a, b, c in zip(if_score, rf_norm, composite)
    ]
