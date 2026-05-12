import uuid
from models.schemas import Session

_sessions: dict[str, Session] = {}


def create_session(query: str) -> Session:
    session = Session(id=str(uuid.uuid4()), query=query)
    _sessions[session.id] = session
    return session


def get_session(session_id: str) -> Session:
    if session_id not in _sessions:
        raise KeyError(f"Session {session_id} not found")
    return _sessions[session_id]


def update_session(session_id: str, updates: dict) -> Session:
    session = get_session(session_id)
    session_dict = session.model_dump()
    session_dict.update(updates)
    _sessions[session_id] = Session(**session_dict)
    return _sessions[session_id]
