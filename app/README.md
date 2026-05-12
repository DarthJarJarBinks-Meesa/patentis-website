# Patentis

Discover what hasn't been patented yet. Patentis maps an existing patent landscape, identifies genuine innovation gaps, generates novel product ideas, and guides you through development — all while ensuring you don't infringe on existing patents.

## How it works

1. **Search** — Describe a technology area. llama3.2 extracts keywords and queries USPTO, EPO, arXiv, and Semantic Scholar in parallel.
2. **Review** — See all retrieved patents and papers. Select which ones go into the analysis.
3. **Analyze** — deepseek-r1 reads the documents via RAG and produces a patent landscape map: covered territory, gaps, and research directions.
4. **Ideas** — deepseek-r1 generates 5 novel ideas filling the identified gaps. Select one to trigger an infringement check.
5. **Develop** — A chat interface (llama3.2) with full patent context guides you through development.

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **[Ollama](https://ollama.com)** — runs the local LLMs

## Quick start

```bash
./start.sh
```

The script will:
- Start Ollama (if not already running)
- Pull `llama3.2` and `deepseek-r1` if not already downloaded
- Create a Python virtual environment and install dependencies
- Install Node packages
- Start both servers

Open **http://localhost:5173**

> First run will download the sentence-transformer embedding model (~90 MB) and Ollama models (llama3.2 ~2 GB, deepseek-r1 ~4 GB). Subsequent runs are instant.

## Manual setup

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## EPO credentials (optional)

Register for free at [ops.epo.org](https://ops.epo.org) to get a client ID and secret. Add them to `backend/.env`:

```
EPO_CLIENT_ID=your_id
EPO_CLIENT_SECRET=your_secret
```

Without EPO credentials, Patentis uses USPTO + arXiv + Semantic Scholar (which covers the vast majority of patents).

## Architecture

```
patentis/
├── backend/
│   ├── main.py                   # FastAPI app
│   ├── api/routes/
│   │   ├── search.py             # POST /api/search
│   │   ├── session.py            # GET/PATCH /api/session/{id}
│   │   ├── analysis.py           # POST /api/session/{id}/analyze  (SSE)
│   │   ├── ideas.py              # POST /api/session/{id}/generate-ideas
│   │   │                         # POST /api/session/{id}/select-idea  (SSE)
│   │   └── chat.py               # POST /api/session/{id}/chat  (SSE)
│   ├── services/
│   │   ├── llm.py                # Ollama client + model routing
│   │   ├── patent_search.py      # USPTO PatentsView + EPO OPS
│   │   ├── paper_search.py       # arXiv + Semantic Scholar
│   │   ├── rag.py                # ChromaDB + sentence-transformers
│   │   └── session_store.py      # In-memory session state
│   └── models/schemas.py         # Pydantic models
└── frontend/
    └── src/
        ├── store.ts              # Zustand global state
        ├── api/client.ts         # Fetch + SSE helpers
        ├── pages/                # SearchPage → ReviewPage → AnalysisPage → IdeasPage → GuidancePage
        └── components/           # PatentCard, PaperCard, IdeaCard, ChatMessage, ThinkingBlock
```

## Model routing

| Task | Model |
|---|---|
| Keyword extraction | llama3.2 |
| Patent gap analysis | deepseek-r1 |
| Idea generation | deepseek-r1 |
| Infringement check | deepseek-r1 |
| Development guidance chat | llama3.2 |

deepseek-r1's reasoning traces (`<think>` blocks) are displayed in a collapsible panel so you can inspect the model's logic.

## Data sources (all free)

| Source | What it provides |
|---|---|
| USPTO PatentsView API | US patents — title, abstract, inventors, assignee |
| EPO OPS | European patents (requires free registration) |
| arXiv API | Academic preprints |
| Semantic Scholar API | Broader academic paper search |
