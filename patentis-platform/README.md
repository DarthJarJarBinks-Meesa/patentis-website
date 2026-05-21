# Patentis Platform

Innovation intelligence platform: whitespace scoring on patent-space signals, hybrid retrieval, structured briefs, multimodal ingestion, workflow agents.

## Quick start

```bash
cd infra && docker compose up -d   # Postgres 16 + pgvector + Redis

cd ..
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,full]"

export DATABASE_URL=postgresql+asyncpg://patentis:patentis@localhost:5433/patentis
uvicorn patentis_platform.api.main:app --reload --host 0.0.0.0 --port 8080
```

Initialize DB (first run):

```bash
python -m patentis_platform.db.init_db
```

Seed medtech CPC regions + sample patents (dev):

```bash
python -m patentis_platform.ingestion.seed_medtech
```

**v1-style search** (Google Patents + optional EPO + PubMed → project corpus):

```bash
# POST /api/projects/{id}/search  {"query": "implant micromotion sensing"}
```

**Multimodal gap identification** (landscape scores + claims/PDF + corpus + optional vision):

```bash
# POST /api/projects/{id}/regions/{region_id}/identify-gaps
# {"idea_hint": "...", "use_vision": true}
```

### Roadmap modules (implemented)

| Module | CLI / API |
|--------|-----------|
| USPTO bulk claims XML | `python -m workers.bulk_index /path/to/xml` · `POST /api/ingestion/uspto-bulk?path=...` |
| CPC adjacency + neighbor features | `POST /api/ingestion/cpc-graph/seed` · `POST /api/agents/ingest/cpc-adjacent` |
| Figure captioning | `POST /api/ingestion/figure-caption` |
| Prior art (Lens + Google Patents) | `GET /api/prior-art/search?q=...` |
| Literature (PubMed + arXiv + Semantic Scholar) | included in `POST /api/projects/{id}/search` |
| **Masked supervision** (hide 5–10 patents per CPC subgroup → predict gaps → score vs hidden claims) | `GET /api/training/masking/eligible-subgroups` · `POST /api/training/masking/run` · `python scripts/seed_masking_corpus.py` · `python models/auto_trainer.py` |
| Nightly jobs | `python -m workers.scheduler all` |

### Enterprise ML policy

- **Base Patentis-SFT** trains only on the public USPTO masked-patent pipeline (`masking_run_records`). Customer data is never included — enforced in `models/dataset_builder.py`.
- **Per-org LoRA** (optional): `POST /api/enterprise/training/opt-in` with admin consent; weights live under `org-adapters/{org_id}/` and load only for that org's inference.
- **Opt-out**: `POST /api/enterprise/training/opt-out` — adapter retired immediately; interaction logs and adapter files purged within 30 days (`workers.scheduler training-purge`).
- Policy: `GET /api/enterprise/training/policy` · Status: `GET /api/enterprise/training/status`

Train / refresh scoring (IF + RF on region features):

```bash
python -m patentis_platform.scoring.train --vertical medtech
```

Frontend:

```bash
cd web && npm install && npm run dev
```

## Environment

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Async SQLAlchemy URL (`postgresql+asyncpg://...`) |
| `REDIS_URL` | `redis://localhost:6379/0` for workers (optional) |
| `OPENAI_API_KEY` / `AZURE_OPENAI_*` | LLM router (optional; mock briefs if unset) |
| `PATENTSVIEW_API_KEY` | PatentsView API (optional; seed data works without) |
| `EPO_CLIENT_ID` / `EPO_CLIENT_SECRET` | EPO OPS (optional; see [patentisv1](https://github.com/Natheoah/patentisv1)) |
| `OPENAI_API_KEY` or `AZURE_OPENAI_*` | LLM + multimodal gap identification |
| `PLATFORM_JWT_SECRET` | HS256 for dev auth |
| `PLATFORM_API_KEYS` | Comma-separated keys for `X-API-Key` enterprise tier |

## Layout

- `patentis_platform/` — Python package: DB, ingestion, scoring, retrieval, synthesis, agents, enterprise
- `patentis_platform/api/` — FastAPI routes
- `workers/` — background job entry (Arq placeholder)
- `models/` — SFT / training script stubs + sample schema
- `web/` — Next.js UI (Landscape, Corpus, Analyst, Calibration)
- `infra/` — Docker Compose, Azure-aligned notes

## Azure (production sketch)

Deploy API to Azure Container Apps, Postgres Flexible Server + `vector` extension, Blob Storage for PDF corpus, Redis Cache for workers, Azure OpenAI behind the synthesis router.
