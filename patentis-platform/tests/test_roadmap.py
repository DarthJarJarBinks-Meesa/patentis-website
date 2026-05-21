"""Roadmap module smoke tests."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from patentis_platform.graph.cpc_adjacency import adjacent_subclasses, expanded_ingest_prefixes
from patentis_platform.ingestion.uspto_bulk import parse_grant_xml
from patentis_platform.multimodal.claim_segmenter import segment_claims
from models.gap_evaluator import score_prediction
from models.masking_config import MaskingConfig


MINIMAL_GRANT = b"""<?xml version="1.0"?>
<us-patent-grant>
  <us-bibliographic-data-grant>
    <publication-reference>
      <document-id><doc-number>9999999</doc-number></document-id>
    </publication-reference>
    <invention-title>Test implant sensor</invention-title>
    <classification-cpc><main-cpc><classification-symbol>A61B5</classification-symbol></main-cpc></classification-cpc>
  </us-bibliographic-data-grant>
  <abstract><p>Wireless strain sensing for bone.</p></abstract>
  <claims>
    <claim id="CLM-00001"><claim-text>1. A device comprising a sensor.</claim-text></claim>
    <claim id="CLM-00002"><claim-text>2. The device of claim 1, wherein the sensor is wireless.</claim-text></claim>
  </claims>
</us-patent-grant>
"""


def test_parse_uspto_grant_xml():
    parsed = parse_grant_xml(MINIMAL_GRANT)
    assert parsed is not None
    assert "sensor" in parsed["title"].lower() or "implant" in parsed["title"].lower()
    assert parsed.get("claims_text")
    assert parsed.get("cpc_subclass", "").startswith("A61")


def test_cpc_adjacency():
    neighbors = adjacent_subclasses("A61B", include_self=False)
    assert "A61F" in neighbors or "A61B5" in neighbors
    assert len(expanded_ingest_prefixes()) >= 3


def test_claim_segmenter():
    blocks = segment_claims("1. A system.\n\n2. The system of claim 1.")
    assert len(blocks) >= 1


def test_gap_evaluator_hit_rate():
    config = MaskingConfig(score_threshold=0.3)
    record = {
        "completion": {
            "gap_description": "wireless implant strain sensing telemetry",
            "predicted_claim_space": "micromotion monitoring",
            "suggested_directions": ["RF backscatter"],
        },
        "hidden_patent_claims": [
            "A wireless strain sensor for implant micromotion detection and telemetry."
        ],
    }
    result = score_prediction(record, config)
    assert "hit_rate" in result
    assert result["n_hidden"] == 1
