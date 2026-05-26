"""High-level knowledge indexing orchestration."""

from __future__ import annotations

import json
import hashlib

from config import CHROMA_COLLECTION
from models.database import (
    delete_knowledge_chunks_by_document,
    get_knowledge_document,
    list_knowledge_chunks_by_document,
    now,
    replace_knowledge_chunks,
    update_knowledge_document,
)
from services.document_parse_service import clean_extracted_text
from services.embedding_service import EmbeddingServiceError, embed_texts
from services.knowledge_chunk_service import (
    build_chunk_metadata,
    estimate_token_count,
    split_text_into_chunks,
    summarize_chunk_text,
)
from services.vector_store_service import (
    VectorStoreError,
    add_document_chunks,
    delete_document_vectors,
    search_similar,
)


def _load_document_text(document):
    text_file_path = str(document.get("text_file_path") or "").strip()
    if text_file_path:
        try:
            with open(text_file_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            if content.strip():
                return clean_extracted_text(content)
        except OSError:
            pass
    return clean_extracted_text(document.get("parsed_text") or "")


def _update_document_state(document, **changes):
    payload = dict(document)
    payload.update(changes)
    return update_knowledge_document(document["id"], payload)


def index_knowledge_document(doc_id):
    document = get_knowledge_document(doc_id)
    if not document:
        return {"ok": False, "message": "知识资料不存在。"}

    text = _load_document_text(document)
    text_hash = hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest() if text else ""
    if not text.strip():
        _update_document_state(
            document,
            embedding_status="failed",
            embedding_error="资料没有可用于向量化的文本内容。",
            indexed_at="",
        )
        return {"ok": False, "message": "资料没有可用于向量化的文本内容。"}

    chunks = split_text_into_chunks(text)
    if not chunks:
        _update_document_state(
            document,
            embedding_status="failed",
            embedding_error="未能切出有效文本块。",
            indexed_at="",
            chunk_count=0,
            vector_collection="",
        )
        return {"ok": False, "message": "未能切出有效文本块。"}

    chunk_rows = []
    for index, chunk_text in enumerate(chunks):
        metadata = build_chunk_metadata(document, index)
        chunk_rows.append(
            {
                "chunk_index": index,
                "chunk_text": chunk_text,
                "chunk_summary": summarize_chunk_text(chunk_text),
                "char_count": len(chunk_text),
                "token_estimate": estimate_token_count(chunk_text),
                "chroma_id": f"doc_{int(document['id'])}_chunk_{index}",
                "metadata": metadata,
                "metadata_json": json.dumps(metadata, ensure_ascii=False),
                "created_at": now(),
            }
        )

    _update_document_state(
        document,
        embedding_status="indexing",
        embedding_error="",
        indexed_at="",
        chunk_count=len(chunk_rows),
        vector_collection="",
    )
    try:
        delete_document_vectors(doc_id)
    except VectorStoreError:
        # Old vector cleanup is best-effort; reindex should still continue.
        pass
    delete_knowledge_chunks_by_document(doc_id)
    replace_knowledge_chunks(doc_id, chunk_rows)

    try:
        embeddings = embed_texts([row["chunk_text"] for row in chunk_rows])
        add_document_chunks(document, chunk_rows, embeddings)
    except (EmbeddingServiceError, VectorStoreError) as exc:
        _update_document_state(
            document,
            embedding_status="failed",
            embedding_error=str(exc),
            indexed_at="",
            chunk_count=len(chunk_rows),
            vector_collection="",
        )
        return {"ok": False, "message": str(exc), "chunk_count": len(chunk_rows)}

    updated = _update_document_state(
        document,
        embedding_status="indexed",
        embedding_error="",
        indexed_at=now(),
        chunk_count=len(chunk_rows),
        vector_collection=CHROMA_COLLECTION,
        last_indexed_text_hash=text_hash,
    )
    return {
        "ok": True,
        "message": "已建立向量索引。",
        "chunk_count": len(chunk_rows),
        "document": updated,
    }


def delete_knowledge_document_index(doc_id):
    document = get_knowledge_document(doc_id)
    if not document:
        return {"ok": False, "message": "知识资料不存在。"}

    warning = ""
    try:
        delete_document_vectors(doc_id)
    except VectorStoreError as exc:
        warning = str(exc)

    delete_knowledge_chunks_by_document(doc_id)
    updated = _update_document_state(
        document,
        embedding_status="not_indexed",
        embedding_error="",
        indexed_at="",
        chunk_count=0,
        vector_collection="",
    )
    return {
        "ok": True,
        "message": "已删除向量索引。",
        "warning": warning,
        "document": updated,
    }


def search_knowledge_semantic(query, filters=None, top_k=5):
    return search_similar(query, filters=filters, top_k=top_k)
