import logging
from typing import List, Dict, Any, Optional

import chromadb
from django.conf import settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_embedding_model = None
_chroma_client   = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        model_name = getattr(settings, "EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
        logger.info("[Embedder] Loading model: %s", model_name)
        _embedding_model = SentenceTransformer(model_name)
    return _embedding_model


def get_chroma_client():
    global _chroma_client
    if _chroma_client is None:
        db_path = str(getattr(settings, "CHROMA_DB_PATH", "./chroma_db"))
        _chroma_client = chromadb.PersistentClient(path=db_path)
    return _chroma_client


def get_collection():
    client = get_chroma_client()
    name   = getattr(settings, "CHROMA_COLLECTION_NAME", "resume_chunks")
    return client.get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


def embed_text(text: str) -> List[float]:
    return get_embedding_model().encode(text, convert_to_numpy=True).tolist()


def store_chunks(chunks: List[Dict]) -> int:
    if not chunks:
        return 0
    collection = get_collection()
    model      = get_embedding_model()

    ids, documents, metadatas = [], [], []
    for chunk in chunks:
        ids.append(
            f"candidate_{chunk['candidate_id']}__{chunk['section']}__{chunk['chunk_index']}"
        )
        documents.append(chunk["text"])
        metadatas.append({
            "candidate_id"   : str(chunk["candidate_id"]),
            "section"        : chunk["section"],
            "source_filename": chunk["source_filename"],
            "chunk_index"    : str(chunk["chunk_index"]),
        })

    embeddings = model.encode([c["text"] for c in chunks], convert_to_numpy=True).tolist()
    collection.upsert(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    logger.info("[Embedder] Stored %d chunks", len(chunks))
    return len(chunks)


def delete_candidate_chunks(candidate_id: int) -> None:
    get_collection().delete(where={"candidate_id": str(candidate_id)})
    logger.info("[Embedder] Deleted chunks for candidate_id=%d", candidate_id)


def search_similar_chunks(
    job_description_text: str,
    top_k: int = 20,
    section_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    collection   = get_collection()
    jd_embedding = embed_text(job_description_text)

    query_params = {
        "query_embeddings": [jd_embedding],
        "n_results"       : top_k,
        "include"         : ["documents", "metadatas", "distances"],
    }
    if section_filter:
        query_params["where"] = {"section": section_filter}

    results = collection.query(**query_params)
    output  = []
    if results and results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            output.append({
                "chunk_id"       : chunk_id,
                "candidate_id"   : results["metadatas"][0][i].get("candidate_id"),
                "section"        : results["metadatas"][0][i].get("section"),
                "source_filename": results["metadatas"][0][i].get("source_filename"),
                "text"           : results["documents"][0][i],
                "distance"       : results["distances"][0][i],
            })
    return output