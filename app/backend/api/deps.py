from fastapi import Header, HTTPException
from services.llm import OPENAI_API_KEY


def get_groq_key(x_groq_api_key: str = Header(default="")) -> str:
    key = x_groq_api_key or OPENAI_API_KEY
    if not key:
        raise HTTPException(status_code=400, detail="OpenAI API key required. Add OPENAI_API_KEY to backend/.env")
    return key
