import chromadb
from sentence_transformers import SentenceTransformer
import os

_CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma")
_client = chromadb.PersistentClient(path=_CHROMA_PATH)
_embed_model = SentenceTransformer("all-MiniLM-L6-v2")


def _collection(session_id: str):
    return _client.get_or_create_collection(
        name=f"session_{session_id.replace('-', '_')}",
        metadata={"hnsw:space": "cosine"},
    )


def embed_documents(session_id: str, documents: list[dict]) -> None:
    """
    documents: list of {id, text, metadata}
    Skips documents that are already in the collection.
    """
    col = _collection(session_id)
    existing = set(col.get()["ids"])

    new_docs = [d for d in documents if d["id"] not in existing]
    if not new_docs:
        return

    ids = [d["id"] for d in new_docs]
    texts = [d["text"] for d in new_docs]
    metadatas = [d.get("metadata", {}) for d in new_docs]
    embeddings = _embed_model.encode(texts, show_progress_bar=False).tolist()

    col.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)


def query_collection(session_id: str, query: str, n_results: int = 10) -> list[dict]:
    col = _collection(session_id)
    count = col.count()
    if count == 0:
        return []

    n = min(n_results, count)
    embedding = _embed_model.encode([query], show_progress_bar=False)[0].tolist()
    results = col.query(
        query_embeddings=[embedding],
        n_results=n,
        include=["documents", "metadatas", "distances"],
    )
    return [
        {"text": doc, "metadata": meta, "distance": dist}
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        )
    ]


def get_all_documents(session_id: str) -> list[dict]:
    col = _collection(session_id)
    result = col.get(include=["documents", "metadatas"])
    return [
        {"text": doc, "metadata": meta}
        for doc, meta in zip(result["documents"], result["metadatas"])
    ]


def delete_collection(session_id: str) -> None:
    try:
        _client.delete_collection(f"session_{session_id.replace('-', '_')}")
    except Exception:
        pass
