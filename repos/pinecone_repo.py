import os
from pinecone import Pinecone

_pc = None
_index = None

def _get_index():
    global _pc, _index
    if _index is not None:
        return _index

    api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX")
    if not api_key or not index_name:
        raise RuntimeError("Missing env vars: PINECONE_API_KEY / PINECONE_INDEX")

    _pc = Pinecone(api_key=api_key)
    _index = _pc.Index(index_name)
    return _index

def namespace_for_user(user_id: str) -> str:
    prefix = os.getenv("PINECONE_NAMESPACE_PREFIX", "mem")
    return f"{prefix}:{user_id}"

def memory_namespace(user_id: str) -> str:
    return namespace_for_user(user_id)

def upsert_memory(user_id: str, items: list[dict]):
    """
    items: [{"id": str, "values": [float], "metadata": {...}}, ...]
    """
    idx = _get_index()
    ns = namespace_for_user(user_id)
    return idx.upsert(vectors=items, namespace=ns)

def query_memory(user_id: str, vector: list[float], top_k: int = 5):
    idx = _get_index()
    ns = namespace_for_user(user_id)
    return idx.query(vector=vector, top_k=top_k, include_metadata=True, namespace=ns)

def delete_memory_vectors(user_id: str, vector_ids: list[str]) -> None:
    ids = [vid for vid in vector_ids if vid]
    if not ids:
        return
    idx = _get_index()
    idx.delete(ids=ids, namespace=memory_namespace(user_id))
