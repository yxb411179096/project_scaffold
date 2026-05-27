from app import create_app
from models.database import create_knowledge_document, delete_knowledge_document, query_knowledge_documents
from services.knowledge_governance_service import (
    create_unit_placeholders,
    documents_need_reindex,
    evaluate_document_metadata,
    get_knowledge_coverage,
    suggest_metadata,
)


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
        "parsed_text": "UNIT 3 THE INTERNET Reading and Thinking Jan Tchamani online community digital divide",
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
    # 1 missing field detection
    report = evaluate_document_metadata({"title": "", "doc_type": "", "grade": "", "textbook": "", "volume": "", "unit": "", "lesson_type": "", "tags": ""})
    assert report["missing_fields"]

    # 2 whole book recognition
    whole = evaluate_document_metadata({"title": "人教版 必修二 全册 教材整本", "file_name": "必修二.pdf", "doc_type": "教材"})
    assert whole["is_whole_book"] is True

    # 3 metadata suggestion
    s = suggest_metadata({"title": "人教版 必修二 Unit 3 The Internet", "file_name": "", "parsed_text": "Reading and Thinking"})
    assert s["suggested_volume"] == "必修二"
    assert s["suggested_unit"] == "Unit 3"
    assert s["suggested_lesson_type"] == "Reading"

    # 3.1 keep existing valid value when no better inference
    keep = suggest_metadata(
        {
            "title": "课堂资料",
            "file_name": "",
            "parsed_text": "some notes without clear metadata",
            "grade": "高一",
            "volume": "必修一",
            "textbook": "人教版",
            "unit": "Unit 1",
            "lesson_type": "Other",
        }
    )
    assert keep["suggested_grade"] == "高一"
    assert keep["suggested_volume"] == "必修一"

    # 3.2 whole-book should not aggressively become Writing
    whole_s = suggest_metadata(
        {
            "title": "人教版 必修二 全册 教材整本",
            "file_name": "必修二.pdf",
            "parsed_text": "This book contains reading and writing sections.",
            "lesson_type": "Other",
        }
    )
    assert whole_s["suggested_lesson_type"] in {"Other", "通用"}

    # 3.3 Writing only when explicit in title/file
    writing_implicit = suggest_metadata(
        {
            "title": "Unit 3 materials",
            "file_name": "unit3_notes.txt",
            "parsed_text": "students will practice writing",
            "lesson_type": "Other",
        }
    )
    assert writing_implicit["suggested_lesson_type"] != "Writing"
    writing_explicit = suggest_metadata(
        {
            "title": "Reading for Writing - Unit 3",
            "file_name": "u3_reading_for_writing.docx",
            "parsed_text": "",
            "lesson_type": "Other",
        }
    )
    assert writing_explicit["suggested_lesson_type"] == "Writing"

    # 4 coverage includes unit 3 internet
    coverage = get_knowledge_coverage()
    found = False
    for g in coverage.get("textbooks", []):
        if g.get("textbook") == "人教版" and g.get("volume") == "必修二":
            for u in g.get("units", []):
                if u.get("unit") == "Unit 3" and "Internet" in (u.get("theme") or ""):
                    found = True
    assert found

    # 5 create placeholders no duplicate
    before = len([d for d in query_knowledge_documents({"keyword": "资料占位"}, limit=2000) if d.get("volume") == "必修二"])
    create_unit_placeholders("人教版", "必修二")
    mid = len([d for d in query_knowledge_documents({"keyword": "资料占位"}, limit=2000) if d.get("volume") == "必修二"])
    create_unit_placeholders("人教版", "必修二")
    after = len([d for d in query_knowledge_documents({"keyword": "资料占位"}, limit=2000) if d.get("volume") == "必修二"])
    assert mid >= before
    assert after == mid

    # 6 need reindex detect
    doc = _seed_doc("[TEST] Round22 Reindex")
    needs = documents_need_reindex()
    assert any(d["id"] == doc["id"] for d in needs)
    delete_knowledge_document(doc["id"])

    # 6.1 indexed + hash consistent should not need reindex
    indexed_doc = _seed_doc(
        "[TEST] Round22 Indexed Clean",
        embedding_status="indexed",
        chunk_count=5,
        last_indexed_text_hash="",
        indexed_at="2026-01-01 00:00:00",
    )
    first_check = documents_need_reindex()
    assert not any(d["id"] == indexed_doc["id"] for d in first_check)
    refreshed = [d for d in query_knowledge_documents({"keyword": "[TEST] Round22 Indexed Clean"}, limit=5) if d["id"] == indexed_doc["id"]][0]
    assert refreshed.get("last_indexed_text_hash")
    delete_knowledge_document(indexed_doc["id"])

    # 7/8/9/10 pages and old routes
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        assert client.get("/knowledge/governance").status_code == 200
        assert client.get("/knowledge/coverage").status_code == 200
        assert client.get("/knowledge").status_code == 200
        assert client.get("/knowledge/search-semantic").status_code == 200
        assert client.get("/ppt/new").status_code == 200
        clean_doc = _seed_doc(
            "[TEST] Round22 Detail Indexed",
            embedding_status="indexed",
            chunk_count=3,
            last_indexed_text_hash="",
            indexed_at="2026-01-01 00:00:00",
        )
        detail_html = client.get(f"/knowledge/{clean_doc['id']}").data.decode("utf-8", errors="ignore")
        assert "文本已变化或尚未索引，建议重新建立向量索引。" not in detail_html
        delete_knowledge_document(clean_doc["id"])

    print("ROUND_022_OK")


if __name__ == "__main__":
    run()
