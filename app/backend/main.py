from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import search, session, analysis, ideas, chat
from services import llm as llm_service

app = FastAPI(title="Patentis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router, prefix="/api")
app.include_router(session.router, prefix="/api")
app.include_router(analysis.router, prefix="/api")
app.include_router(ideas.router, prefix="/api")
app.include_router(chat.router, prefix="/api")


@app.get("/api/health")
async def health():
    llm_status = await llm_service.check_health()
    return {
        "status": "ok",
        "llm": llm_status,
        "instruction_model": llm_service.INSTRUCTION_MODEL,
        "reasoning_model": llm_service.REASONING_MODEL,
    }
