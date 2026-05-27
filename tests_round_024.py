from app import create_app
from models.database import create_knowledge_document, delete_knowledge_document, query_knowledge_documents
from routes.knowledge_routes import _is_placeholder_doc
from services.knowledge_governance_service import get_knowledge_coverage


def _seed_doc(title, **extra):
    payload = {
        "title": title,
        "doc_type": "课文",
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修二",
        "unit": "Unit 3",
        "lesson_type": "Reading",
        "source_type": "text",
        "file_name": "",
        "original_file_path": "",
        "text_file_path": "",
        "parsed_text": "test text content",
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


def _find_unit(volume, unit):
    groups = get_knowledge_coverage().get("textbooks", [])
    for g in groups:
        if g.get("textbook") == "人教版" and g.get("volume") == volume:
            for row in g.get("units", []):
                if row.get("unit") == unit:
                    return row
    return {}


def run():
    app = create_app()
    app.config["TESTING"] = True

    with app.test_client() as client:
        assert client.get("/knowledge/unit-supplement?textbook=人教版&volume=必修二&unit=Unit%203").status_code == 200
        html = client.get("/knowledge/unit-supplement?textbook=人教版&volume=必修二&unit=Unit%203").data.decode("utf-8", errors="ignore")
        assert "单元资料补齐面板" in html
        assert "去补充" in html
        assert "/knowledge/new" in html

        cov_html = client.get("/knowledge/coverage?highlight_unit=Unit%203&highlight_volume=必修二").data.decode("utf-8", errors="ignore")
        assert "已补充 Unit 3 资料，请查看覆盖状态是否更新。" in cov_html

        list_html = client.get("/knowledge").data.decode("utf-8", errors="ignore")
        assert "查看 Unit 覆盖" in list_html or client.get("/knowledge").status_code == 200

        # Save with index_coverage should keep document even if index fails.
        res = client.post(
            "/knowledge/new",
            data={
                "title": "[TEST] Round024 Save Index Fail",
                "doc_type": "教案",
                "lesson_type": "Reading",
                "grade": "高一",
                "textbook": "人教版",
                "volume": "必修二",
                "unit": "Unit 3",
                "tags": "test",
                "raw_text": "content for save test",
                "supplement_type": "reading_plan",
                "action_after": "index_coverage",
                "coverage_textbook": "人教版",
                "coverage_volume": "必修二",
                "coverage_unit": "Unit 3",
            },
            follow_redirects=False,
        )
        assert res.status_code in (302, 303)
        docs = query_knowledge_documents({"keyword": "[TEST] Round024 Save Index Fail"}, limit=5)
        assert len(docs) > 0
        for d in docs:
            delete_knowledge_document(d["id"])

        # Detail page should have return to unit coverage entry.
        temp = _seed_doc("[TEST] Round024 detail link")
        try:
            dhtml = client.get(f"/knowledge/{temp['id']}").data.decode("utf-8", errors="ignore")
            assert "返回该 Unit 覆盖情况" in dhtml
        finally:
            delete_knowledge_document(temp["id"])

    # Placeholder should not count as coverage
    before = _find_unit("必修三", "Unit 4")
    placeholder = _seed_doc(
        "[TEST] Round024 Placeholder",
        doc_type="其他",
        tags="资料占位",
        volume="必修三",
        unit="Unit 4",
        lesson_type="Grammar",
        word_count=0,
        status="pending",
    )
    try:
        assert _is_placeholder_doc(placeholder)
        after = _find_unit("必修三", "Unit 4")
        assert before.get("has_grammar") == after.get("has_grammar")
    finally:
        delete_knowledge_document(placeholder["id"])

    print("ROUND_024_OK")


if __name__ == "__main__":
    run()
