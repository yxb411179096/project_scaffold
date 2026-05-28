from app import create_app
from models.database import (
    create_knowledge_document,
    create_knowledge_unit_draft,
    delete_knowledge_document,
    get_knowledge_document,
    get_knowledge_unit_draft,
    query_knowledge_documents,
)
from services.knowledge_governance_service import get_knowledge_coverage
from services.textbook_unit_split_service import (
    build_unit_document_drafts,
    detect_unit_boundaries,
    extract_unit_sections,
    split_text_by_units,
)


SAMPLE_TEXT = """
UNIT 1 TEENAGE LIFE
Reading and Thinking
Students should adapt to new school life.
Words and Expressions
teenager, challenge, volunteer

UNIT 2 WILDLIFE PROTECTION
Reading and Thinking
Protecting endangered animals matters.

UNIT 3 THE INTERNET
Reading and Thinking
Stronger Together: How We Have Been Changed by the Internet.
Words and Expressions
online community, digital divide, network
"""


def _seed_source_doc():
    return create_knowledge_document(
        {
            "title": "[TEST] Source Whole Book",
            "doc_type": "教材",
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修二",
            "unit": "通用",
            "lesson_type": "Other",
            "source_type": "text",
            "parsed_text": SAMPLE_TEXT,
            "summary": "test",
            "word_count": len(SAMPLE_TEXT),
            "tags": "整本教材",
            "status": "parsed",
            "embedding_status": "not_indexed",
            "chunk_count": 0,
            "vector_collection": "",
            "metadata_reviewed": False,
            "metadata_quality_score": 0,
            "metadata_warnings": "",
            "is_whole_book": True,
        }
    )


def run():
    # 1 detect boundaries
    boundaries = detect_unit_boundaries(SAMPLE_TEXT, textbook="人教版", volume="必修二")
    assert any(b["unit"] == "Unit 3" and "Internet" in (b.get("theme") or "") for b in boundaries)

    # 2 split
    units = split_text_by_units(SAMPLE_TEXT, boundaries)
    names = [u["unit"] for u in units]
    assert "Unit 1" in names and "Unit 2" in names and "Unit 3" in names

    # 3 sections
    unit3 = next(u for u in units if u["unit"] == "Unit 3")
    sections = extract_unit_sections(unit3["text"])
    assert "Reading and Thinking" in sections.get("reading_and_thinking", "")

    # 4/5 draft build
    source = {"id": 999, "grade": "高一", "textbook": "人教版", "volume": "必修二"}
    drafts = build_unit_document_drafts(source, units)
    assert any(d["draft_type"] == "unit_textbook" for d in drafts)
    assert any(d["draft_type"] == "reading_text" for d in drafts)

    app = create_app()
    app.config["TESTING"] = True

    src_doc = _seed_source_doc()
    try:
        # prepare one draft row for create endpoint
        first = next(d for d in drafts if d["draft_type"] == "unit_textbook")
        first["source_document_id"] = src_doc["id"]
        row = create_knowledge_unit_draft(first)

        with app.test_client() as client:
            # 8 page open
            assert client.get(f"/knowledge/{src_doc['id']}/unit-split").status_code == 200

            # 9 create-document endpoint
            resp = client.post(f"/knowledge/unit-drafts/{row['id']}/create-document", follow_redirects=False)
            assert resp.status_code in (302, 303)

        updated_draft = get_knowledge_unit_draft(row["id"])
        assert updated_draft["status"] == "created"
        created_doc = get_knowledge_document(updated_draft["created_document_id"])
        # 6 created document status parsed
        assert created_doc["status"] == "parsed"

        # 7 coverage counts only formal docs, not drafts
        coverage = get_knowledge_coverage()
        found_unit3 = False
        for g in coverage.get("textbooks", []):
            if g.get("textbook") == "人教版" and g.get("volume") == "必修二":
                for u in g.get("units", []):
                    if u.get("unit") == "Unit 3":
                        found_unit3 = True
        assert found_unit3

        # 10 old pages unaffected
        with app.test_client() as client:
            assert client.get("/knowledge").status_code == 200
            assert client.get("/knowledge/governance").status_code == 200
            assert client.get("/knowledge/coverage").status_code == 200

        delete_knowledge_document(created_doc["id"])
    finally:
        # cleanup source doc and any extra docs created from tests
        extras = query_knowledge_documents({"keyword": "[TEST] Source Whole Book"}, limit=20)
        for d in extras:
            delete_knowledge_document(d["id"])

    print("ROUND_026_OK")


if __name__ == "__main__":
    run()
