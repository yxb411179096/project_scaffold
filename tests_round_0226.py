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
        "parsed_text": "Unit 3 The Internet",
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
        normal = _seed_doc("[TEST] 0226 normal")
        placeholder = _seed_doc(
            "[TEST] 0226 资料占位",
            doc_type="其他",
            tags="资料占位",
            status="pending",
            word_count=0,
        )
        try:
            res = client.get("/knowledge")
            assert res.status_code == 200
            html = res.data.decode("utf-8", errors="ignore")
            assert "knowledge-page-shell" in html
            assert "knowledge-doc-card" in html
            assert "建议元信息" in html
            assert "资料占位" in html
            assert "查看" in html
            assert "删除" in html
            assert client.get("/knowledge/governance").status_code == 200
            assert client.get("/knowledge/coverage").status_code == 200
            assert client.get("/knowledge/search-semantic").status_code == 200
        finally:
            delete_knowledge_document(normal["id"])
            delete_knowledge_document(placeholder["id"])
    print("ROUND_0226_OK")


if __name__ == "__main__":
    run()
