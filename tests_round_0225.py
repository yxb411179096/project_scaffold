from app import create_app
from models.database import create_knowledge_document, delete_knowledge_document


def _seed_doc(title, **extra):
    payload = {
        "title": title,
        "doc_type": "教材",
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修二",
        "unit": "Unit 3",
        "lesson_type": "Reading",
        "source_type": "text",
        "file_name": "",
        "original_file_path": "",
        "text_file_path": "",
        "parsed_text": "Unit 3 The Internet Reading and Thinking",
        "summary": "test",
        "word_count": 20,
        "tags": "test",
        "status": "parsed",
        "error_message": "",
        "embedding_status": "not_indexed",
        "chunk_count": 0,
        "vector_collection": "",
        "embedding_error": "",
        "indexed_at": "",
    }
    payload.update(extra)
    return create_knowledge_document(payload)


def run():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        normal = _seed_doc("[TEST] KB normal")
        placeholder = _seed_doc(
            "[TEST] KB 资料占位",
            doc_type="其他",
            tags="资料占位",
            word_count=0,
            status="pending",
        )
        whole = _seed_doc("[TEST] 人教版 必修二 全册 教材整本", is_whole_book=1)
        try:
            res = client.get("/knowledge")
            assert res.status_code == 200
            html = res.data.decode("utf-8", errors="ignore")
            assert "knowledge-doc-card" in html
            assert "[TEST] KB normal" in html
            assert "资料占位" in html
            assert "等待补充资料" in html
            assert "整本教材" in html
            assert "btn btn-sm btn-outline-primary" in html
            assert client.get("/knowledge/governance").status_code == 200
            assert client.get("/knowledge/coverage").status_code == 200
        finally:
            delete_knowledge_document(normal["id"])
            delete_knowledge_document(placeholder["id"])
            delete_knowledge_document(whole["id"])
    print("ROUND_0225_OK")


if __name__ == "__main__":
    run()
