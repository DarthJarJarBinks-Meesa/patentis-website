from fastapi import APIRouter, HTTPException
from models.schemas import SelectionRequest
from services import session_store

router = APIRouter()


@router.get("/session/{session_id}")
async def get_session(session_id: str):
    try:
        session = session_store.get_session(session_id)
        return session.model_dump()
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")


@router.patch("/session/{session_id}/selection")
async def update_selection(session_id: str, req: SelectionRequest):
    try:
        session = session_store.update_session(
            session_id,
            {
                "selected_patent_ids": req.patent_ids,
                "selected_paper_ids": req.paper_ids,
            },
        )
        return {"selected_patent_ids": session.selected_patent_ids, "selected_paper_ids": session.selected_paper_ids}
    except KeyError:
        raise HTTPException(status_code=404, detail="Session not found")
