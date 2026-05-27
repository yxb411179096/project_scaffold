from app import create_app
from models.database import create_knowledge_document, delete_knowledge_document, query_knowledge_documents
from services.knowledge_governance_service import get_knowledge_coverage


def _seed_doc(title, **extra):
    payload = {
        "title": title,
        "doc_type": "教材",
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修三",
        "unit": "Unit 5",
        "lesson_type": "Reading",
        "source_type": "text",
        "file_name": "",
        "original_file_path": "",
        "text_file_path": "",
        "parsed_text": "test text",
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


def _coverage_unit(volume, unit):
    coverage = get_knowledge_coverage().get("textbooks", [])
    for group in coverage:
        if group.get("textbook") == "人教版" and group.get("volume") == volume:
            for row in group.get("units", []):
                if row.get("unit") == unit:
                    return row
    return {}


def run():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        res = client.get(
            "/knowledge/new?grade=高一&textbook=人教版&volume=必修二&unit=Unit%203&supplement_type=reading_text&theme=The%20Internet"
        )
        assert res.status_code == 200
        html = res.data.decode("utf-8", errors="ignore")
        assert "当前补充类型" in html
        assert "人教版_必修二_Unit 3_The Internet_Reading 课文" in html
        assert "保存并建立索引" in html

        cov = client.get("/knowledge/coverage")
        assert cov.status_code == 200
        cov_html = cov.data.decode("utf-8", errors="ignore")
        assert "补充资料" in cov_html
        assert "name=\"supplement_type\"" in cov_html

        created = client.post(
            "/knowledge/new",
            data={
                "title": "[TEST] Round023 Coverage Return",
                "doc_type": "教案",
                "lesson_type": "Reading",
                "grade": "高一",
                "textbook": "人教版",
                "volume": "必修二",
                "unit": "Unit 3",
                "tags": "test",
                "raw_text": "This is a test lesson plan.",
                "supplement_type": "reading_plan",
                "action_after": "coverage",
                "coverage_textbook": "人教版",
                "coverage_volume": "必修二",
                "coverage_unit": "Unit 3",
            },
            follow_redirects=False,
        )
        assert created.status_code in (302, 303)
        assert "/knowledge/coverage" in (created.headers.get("Location") or "")
        created_docs = query_knowledge_documents({"keyword": "[TEST] Round023 Coverage Return"}, limit=5)
        for doc in created_docs:
            delete_knowledge_document(doc["id"])

    # Placeholder should not be treated as real coverage.
    unit_before = _coverage_unit("必修三", "Unit 5")
    placeholder = _seed_doc(
        "[TEST] Round023 Placeholder",
        doc_type="其他",
        tags="资料占位",
        volume="必修三",
        unit="Unit 5",
        lesson_type="Reading",
        word_count=0,
        status="pending",
    )
    try:
        unit_after = _coverage_unit("必修三", "Unit 5")
        assert unit_before.get("has_reading") == unit_after.get("has_reading")
    finally:
        delete_knowledge_document(placeholder["id"])

    print("ROUND_023_OK")


if __name__ == "__main__":
    run()
