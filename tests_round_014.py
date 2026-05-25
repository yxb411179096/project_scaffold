import io
import re
import sqlite3
import uuid

from app import create_app
from config import DATABASE_PATH
from services.embedding_service import EmbeddingServiceError, embed_text, test_embedding_connection
from services.knowledge_chunk_service import build_chunk_metadata, split_text_into_chunks
from services.vector_store_service import (
    VectorStoreError,
    enrich_search_results_with_documents,
    get_chroma_client,
    get_or_create_collection,
    search_similar,
)


def _extract_doc_id(location):
    match = re.search(r"/knowledge/(\d+)", str(location or ""))
    return int(match.group(1)) if match else None


def _create_sample_doc(client, title_prefix, raw_text):
    response = client.post(
        "/knowledge/new",
        data={
            "title": f"{title_prefix} Sample",
            "doc_type": "教案",
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修一",
            "unit": "Unit 1",
            "lesson_type": "Reading",
            "tags": "round14,test",
            "raw_text": raw_text,
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    doc_id = _extract_doc_id(response.headers.get("Location"))
    assert doc_id
    return doc_id


def run():
    app = create_app()
    app.config["TESTING"] = True
    title_prefix = f"[TEST] Round14 {uuid.uuid4().hex[:8]}"
    cleanup_ids = []

    chunks = split_text_into_chunks(
        "Paragraph one with English.\n\n第二段包含中文内容。它应该保留段落结构。\n\n"
        "This third paragraph is intentionally long. " * 20,
        max_chars=800,
        overlap=120,
    )
    assert chunks, "split_text_into_chunks should return chunks."
    assert all(chunk.strip() for chunk in chunks)

    metadata = build_chunk_metadata(
        {
            "id": 42,
            "title": "Demo Title",
            "doc_type": "教案",
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修一",
            "unit": "Unit 1",
            "lesson_type": "Reading",
            "tags": "demo",
        },
        2,
    )
    assert metadata["document_id"] == 42
    assert metadata["chunk_index"] == 2
    assert metadata["title"] == "Demo Title"

    with sqlite3.connect(DATABASE_PATH) as conn:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_chunks'"
        ).fetchone()
        assert exists, "knowledge_chunks table was not created."

    embedding_probe = test_embedding_connection()
    embedding_available = embedding_probe.get("status") == "available"
    if not embedding_available:
        try:
            embed_text("connection test")
            embedding_available = True
        except EmbeddingServiceError as exc:
            assert "ollama" in str(exc).lower() or "embedding" in str(exc).lower()

    client_obj = get_chroma_client()
    assert client_obj is not None
    collection = get_or_create_collection()
    assert collection is not None

    with app.test_client() as client:
        assert client.get("/").status_code == 200
        assert client.get("/ppt/new").status_code == 200
        assert client.get("/ppt/from-manuscript").status_code == 200
        assert client.get("/settings/ai-models").status_code == 200
        assert client.get("/settings/agent-bindings").status_code == 200
        assert client.get("/knowledge").status_code == 200
        assert client.get("/knowledge/search-semantic").status_code == 200
        assert client.get("/knowledge/new").status_code == 200

        doc_id = _create_sample_doc(
            client,
            title_prefix,
            "This is a reading lesson. Students predict, discuss, and summarize.\n\n"
            "The second paragraph explains vocabulary support and classroom interaction.\n\n"
            "第三段补充教学活动与板书设计。"
        )
        cleanup_ids.append(doc_id)
        detail = client.get(f"/knowledge/{doc_id}")
        assert detail.status_code == 200
        assert "向量状态" in detail.get_data(as_text=True)

        enriched = enrich_search_results_with_documents(
            [
                {
                    "document_id": doc_id,
                    "chroma_id": f"doc_{doc_id}_chunk_0",
                    "chunk_text": "Fallback chunk text.",
                    "metadata": {"document_id": doc_id, "chunk_index": 0},
                    "distance": 0.25,
                    "score": 0.75,
                }
            ]
        )
        assert enriched[0]["title"] == f"{title_prefix} Sample"
        assert enriched[0]["document_id"] == doc_id

        if embedding_available:
            index_resp = client.post(f"/knowledge/{doc_id}/index", follow_redirects=False)
            assert index_resp.status_code in (302, 303)
            detail_after_index = client.get(f"/knowledge/{doc_id}")
            assert detail_after_index.status_code == 200
            detail_text = detail_after_index.get_data(as_text=True)
            assert "indexed" in detail_text or "已建立向量索引" in detail_text

            with sqlite3.connect(DATABASE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM knowledge_documents WHERE id=?",
                    (doc_id,),
                ).fetchone()
                assert row is not None
                assert str(row["embedding_status"]) == "indexed"
                assert int(row["chunk_count"] or 0) > 0
                assert str(row["vector_collection"] or "").strip()
                chunks_row = conn.execute(
                    "SELECT COUNT(*) AS c FROM knowledge_chunks WHERE document_id=?",
                    (doc_id,),
                ).fetchone()
                assert int(chunks_row["c"] or 0) > 0

            collection = get_or_create_collection()
            chroma_rows = collection.get(where={"document_id": doc_id}, include=["metadatas", "documents"])
            metadatas = chroma_rows.get("metadatas") or []
            assert metadatas, "Chroma metadata should not be empty."
            assert any((meta or {}).get("title") for meta in metadatas), "Chroma metadata should include title."

            search_results = search_similar(
                "predict discuss summarize vocabulary support",
                filters={
                    "doc_type": "教案",
                    "grade": "高一",
                    "textbook": "人教版",
                    "volume": "必修一",
                    "unit": "Unit 1",
                    "lesson_type": "Reading",
                },
                top_k=3,
            )
            assert search_results, "search_similar should return results."
            assert search_results[0]["document_id"] == doc_id
            assert search_results[0]["title"]

            search_page = client.get(
                "/knowledge/search-semantic",
                query_string={
                    "query": "predict discuss summarize vocabulary support",
                    "top_k": 3,
                    "doc_type": "教案",
                    "grade": "高一",
                    "textbook": "人教版",
                    "volume": "必修一",
                    "unit": "Unit 1",
                    "lesson_type": "Reading",
                },
            )
            assert search_page.status_code == 200
            assert title_prefix in search_page.get_data(as_text=True)

            delete_index_resp = client.post(f"/knowledge/{doc_id}/delete-index", follow_redirects=False)
            assert delete_index_resp.status_code in (302, 303)

        delete_resp = client.post(f"/knowledge/{doc_id}/delete", follow_redirects=False)
        assert delete_resp.status_code in (302, 303)
        cleanup_ids.remove(doc_id)

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "DELETE FROM knowledge_chunks WHERE document_id IN (SELECT id FROM knowledge_documents WHERE title LIKE ?)",
            (f"{title_prefix}%",),
        )
        conn.execute(
            "DELETE FROM knowledge_documents WHERE title LIKE ?",
            (f"{title_prefix}%",),
        )
        conn.commit()

    print("ROUND_014_OK")


if __name__ == "__main__":
    run()
