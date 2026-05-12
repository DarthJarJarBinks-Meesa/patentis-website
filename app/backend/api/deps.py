from fastapi import Header, HTTPException
from services.llm import GROQ_API_KEY


def get_groq_key(x_groq_api_key: str = Header(default="")) -> str:
    key = x_groq_api_key or GROQ_API_KEY
    if not key:
        raise HTTPException(status_code=400, detail="Groq API key required. Enter it on the app's home screen.")
    return key
