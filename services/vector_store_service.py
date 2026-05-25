"""ChromaDB persistence and semantic search helpers."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from config import CHROMA_COLLECTION, CHROMA_PERSIST_DIR
from models.database import get_knowledge_documents_by_ids
from services.embedding_service import embed_text, EmbeddingServiceError


class VectorStoreError(Exception):
    """Raised when vector store operations fail."""


def _load_chromadb():
    try:
        import chromadb
    except ImportError as exc:
        raise VectorStoreError("chromadb 依赖未安装。请先运行 pip install -r requirements.txt") from exc
    return chromadb


@lru_cache(maxsize=1)
def get_chroma_client():
    chromadb = _load_chromadb()
    CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_PERSIST_DIR))


@lru_cache(maxsize=1)
def get_or_create_collection():
    client = get_chroma_client()
    try:
        return client.get_or_create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        raise VectorStoreError(f"Chroma collection 初始化失败：{exc}") from exc


def _coerce_metadata(metadata):
    safe = {}
    for key, value in (metadata or {}).items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            safe[key] = value
        else:
            safe[key] = str(value)
    return safe


def build_chroma_where(filters):
    """Build a Chroma-compatible where clause without invalid single-item logical groups."""

    clauses = []
    for key in ("grade", "textbook", "volume", "unit", "lesson_type", "doc_type"):
        value = (filters or {}).get(key)
        if isinstance(value, (list, tuple, set)):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if not cleaned:
                continue
            if len(cleaned) == 1:
                clauses.append({key: cleaned[0]})
            else:
                clauses.append({"$or": [{key: item} for item in cleaned]})
            continue

        value = str(value or "").strip()
        if value:
            clauses.append({key: value})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def _metadata_from_chunk(document, chunk, chunk_index):
    metadata = _coerce_metadata(chunk.get("metadata") or {})
    metadata["document_id"] = int(metadata.get("document_id") or document.get("id") or 0)
    metadata["title"] = str(metadata.get("title") or document.get("title") or "").strip()
    metadata["doc_type"] = str(metadata.get("doc_type") or document.get("doc_type") or "").strip()
    metadata["grade"] = str(metadata.get("grade") or document.get("grade") or "").strip()
    metadata["textbook"] = str(metadata.get("textbook") or document.get("textbook") or "").strip()
    metadata["volume"] = str(metadata.get("volume") or document.get("volume") or "").strip()
    metadata["unit"] = str(metadata.get("unit") or document.get("unit") or "").strip()
    metadata["lesson_type"] = str(metadata.get("lesson_type") or document.get("lesson_type") or "").strip()
    metadata["tags"] = str(metadata.get("tags") or document.get("tags") or "").strip()
    metadata["chunk_index"] = int(metadata.get("chunk_index") or chunk_index)
    return metadata


def _parse_document_id_from_chroma_id(chroma_id):
    match = re.search(r"doc_(\d+)_chunk_(\d+)", str(chroma_id or ""))
    if not match:
        return None
    return int(match.group(1))


def _normalize_search_item(item):
    metadata = dict(item.get("metadata") or {})
    document_id = metadata.get("document_id")
    if document_id in (None, ""):
        document_id = _parse_document_id_from_chroma_id(item.get("chroma_id"))
    try:
        document_id = int(document_id) if document_id not in (None, "") else None
    except (TypeError, ValueError):
        document_id = None

    chunk_index = metadata.get("chunk_index")
    try:
        chunk_index = int(chunk_index) if chunk_index not in (None, "") else None
    except (TypeError, ValueError):
        chunk_index = None

    flattened = {
        "document_id": document_id,
        "title": str(metadata.get("title") or "").strip(),
        "doc_type": str(metadata.get("doc_type") or "").strip(),
        "grade": str(metadata.get("grade") or "").strip(),
        "textbook": str(metadata.get("textbook") or "").strip(),
        "volume": str(metadata.get("volume") or "").strip(),
        "unit": str(metadata.get("unit") or "").strip(),
        "lesson_type": str(metadata.get("lesson_type") or "").strip(),
        "tags": str(metadata.get("tags") or "").strip(),
        "chunk_index": chunk_index,
        "chunk_text": str(item.get("chunk_text") or ""),
        "distance": item.get("distance"),
        "score": item.get("score"),
        "chroma_id": str(item.get("chroma_id") or "").strip(),
        "metadata": metadata,
    }
    return flattened


def enrich_search_results_with_documents(results):
    """Backfill missing metadata from SQLite KnowledgeDocument rows."""

    items = [_normalize_search_item(item) for item in results or []]
    doc_ids = [item["document_id"] for item in items if item.get("document_id") is not None]
    documents = get_knowledge_documents_by_ids(doc_ids)

    enriched_items = []
    for item in items:
        document = documents.get(item.get("document_id")) if item.get("document_id") is not None else None
        if document:
            if not item.get("title"):
                item["title"] = document.get("title") or ""
            if not item.get("doc_type"):
                item["doc_type"] = document.get("doc_type") or ""
            if not item.get("grade"):
                item["grade"] = document.get("grade") or ""
            if not item.get("textbook"):
                item["textbook"] = document.get("textbook") or ""
            if not item.get("volume"):
                item["volume"] = document.get("volume") or ""
            if not item.get("unit"):
                item["unit"] = document.get("unit") or ""
            if not item.get("lesson_type"):
                item["lesson_type"] = document.get("lesson_type") or ""
            if not item.get("tags"):
                item["tags"] = document.get("tags") or ""
            item["document_title"] = document.get("title") or ""
            item["document_doc_type"] = document.get("doc_type") or ""
            item["document_grade"] = document.get("grade") or ""
            item["document_textbook"] = document.get("textbook") or ""
            item["document_volume"] = document.get("volume") or ""
            item["document_unit"] = document.get("unit") or ""
            item["document_lesson_type"] = document.get("lesson_type") or ""
            item["document_tags"] = document.get("tags") or ""
        else:
            item["document_title"] = item.get("title") or ""
            item["document_doc_type"] = item.get("doc_type") or ""
            item["document_grade"] = item.get("grade") or ""
            item["document_textbook"] = item.get("textbook") or ""
            item["document_volume"] = item.get("volume") or ""
            item["document_unit"] = item.get("unit") or ""
            item["document_lesson_type"] = item.get("lesson_type") or ""
            item["document_tags"] = item.get("tags") or ""
        enriched_items.append(item)
    return enriched_items


def add_document_chunks(document, chunks, embeddings):
    collection = get_or_create_collection()
    if len(chunks or []) != len(embeddings or []):
        raise VectorStoreError("chunks 与 embeddings 数量不一致。")

    ids = []
    documents = []
    metadata_list = []
    for index, chunk in enumerate(chunks or []):
        chunk_index = int(chunk.get("chunk_index", index))
        chroma_id = str(chunk.get("chroma_id") or f"doc_{document['id']}_chunk_{chunk_index}")
        ids.append(chroma_id)
        documents.append(str(chunk.get("chunk_text") or ""))
        metadata = _metadata_from_chunk(document, chunk, chunk_index)
        metadata["chunk_summary"] = str(chunk.get("chunk_summary") or "")
        metadata["char_count"] = int(chunk.get("char_count") or 0)
        metadata["token_estimate"] = int(chunk.get("token_estimate") or 0)
        metadata["chroma_id"] = chroma_id
        metadata_list.append(metadata)

    try:
        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadata_list,
            embeddings=embeddings,
        )
    except Exception as exc:
        raise VectorStoreError(f"写入 ChromaDB 失败：{exc}") from exc
    return ids


def delete_document_vectors(document_id):
    collection = get_or_create_collection()
    try:
        collection.delete(where={"document_id": int(document_id)})
    except Exception as exc:
        raise VectorStoreError(f"删除 Chroma 向量失败：{exc}") from exc


def reset_document_index(document_id):
    try:
        delete_document_vectors(document_id)
    except VectorStoreError:
        # Keep deletion best-effort; callers can decide whether to surface it.
        pass


def search_similar(query, filters=None, top_k=5, query_embedding=None):
    collection = get_or_create_collection()
    embedding = query_embedding if query_embedding is not None else embed_text(query)
    where = build_chroma_where(filters)

    def _query(current_where):
        return collection.query(
            query_embeddings=[embedding],
            n_results=max(1, int(top_k or 5)),
            where=current_where,
            include=["documents", "metadatas", "distances"],
        )

    try:
        result = _query(where)
    except Exception as exc:
        if where is not None:
            try:
                result = _query(None)
            except Exception as retry_exc:
                raise VectorStoreError(f"Chroma 检索失败：{retry_exc}") from retry_exc
        else:
            raise VectorStoreError(f"Chroma 检索失败：{exc}") from exc

    items = []
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    for index, chroma_id in enumerate(ids):
        metadata = metadatas[index] if index < len(metadatas) else {}
        item = {
            "chroma_id": chroma_id,
            "chunk_text": documents[index] if index < len(documents) else "",
            "metadata": metadata or {},
            "distance": distances[index] if index < len(distances) else None,
            "score": None,
        }
        distance = item["distance"]
        if distance is not None:
            try:
                item["score"] = max(0.0, 1.0 - float(distance))
            except (TypeError, ValueError):
                item["score"] = None
        items.append(item)
    return enrich_search_results_with_documents(items)
