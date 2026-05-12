from pydantic import BaseModel, Field
from typing import Optional


class Patent(BaseModel):
    id: str
    title: str
    abstract: str
    claims: Optional[str] = None
    filing_date: Optional[str] = None
    assignee: Optional[str] = None
    inventors: list[str] = []
    url: str
    source: str  # 'uspto' or 'epo'


class Paper(BaseModel):
    id: str
    title: str
    abstract: str
    authors: list[str] = []
    published: Optional[str] = None
    url: str
    source: str  # 'pubmed'


class Idea(BaseModel):
    title: str
    tagline: str
    description: str
    key_innovation: str
    target_market: str
    technical_approach: str
    why_unpatented: str
    scientific_feasibility: str = ""
    supporting_research: str = ""


class ChatMessage(BaseModel):
    role: str  # 'user' or 'assistant'
    content: str


class Session(BaseModel):
    id: str
    query: str
    patents: list[Patent] = []
    papers: list[Paper] = []
    selected_patent_ids: list[str] = []
    selected_paper_ids: list[str] = []
    analysis: Optional[str] = None
    ideas: list[dict] = []
    selected_idea_index: Optional[int] = None
    infringement_check: Optional[str] = None
    messages: list[dict] = []


# --- Request/Response models ---

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=500)


class SearchResponse(BaseModel):
    session_id: str
    patents: list[Patent]
    papers: list[Paper]
    keywords: dict


class SelectionRequest(BaseModel):
    patent_ids: list[str]
    paper_ids: list[str]


class SelectIdeaRequest(BaseModel):
    idea_index: int


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
