from app import create_app
from models.database import (
    create_knowledge_document,
    create_knowledge_unit_draft,
    delete_knowledge_document,
    list_knowledge_unit_drafts,
)
from services.textbook_unit_split_service import (
    build_unit_document_drafts,
    detect_unit_boundaries,
    split_text_by_units,
)


TEXT_WITH_DUPLICATES = """
Contents
UNIT 1 FESTIVALS AND CELEBRATIONS p. 12
UNIT 2 MORALS AND VIRTUES p. 28
UNIT 3 DIVERSE CULTURES p. 46
UNIT 4 SPACE EXPLORATION p. 66
UNIT 5 THE VALUE OF MONEY p. 88

UNIT 1 Festivals and Celebrations
Reading and Thinking
Main classroom text paragraph one.
Main classroom text paragraph two.
Words and Expressions
festival, celebrate, tradition, culture, event, value

WORKBOOK
UNIT 1 Festivals and Celebrations
Workbook exercise only.

UNIT 2 Morals and Virtues
Reading and Thinking
Text for unit 2.

UNIT 3 Diverse Cultures
Reading and Thinking
Text for unit 3.

UNIT 4 Space Exploration
Reading and Thinking
Text for unit 4.

UNIT 5 The Value of Money
Reading and Thinking
Text for unit 5.

APPENDICES
UNIT 3 Diverse Cultures
Appendix list only.
"""


def _seed_source_doc(title_suffix="[TEST] Round0261 Source"):
    text = TEXT_WITH_DUPLICATES
    return create_knowledge_document(
        {
            "title": title_suffix,
            "doc_type": "教材",
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修三",
            "unit": "通用",
            "lesson_type": "Other",
            "source_type": "text",
            "parsed_text": text,
            "summary": "round0261",
            "word_count": len(text),
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
    # 1) duplicate unit boundaries should dedupe to one per unit.
    boundaries = detect_unit_boundaries(TEXT_WITH_DUPLICATES, textbook="人教版", volume="必修三")
    units = [b["unit"] for b in boundaries]
    assert len(units) == len(set(units))

    # 2) for 必修三 keep catalog units 1-5.
    expected = {"Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"}
    assert set(units).issubset(expected)
    assert "Unit 3" in units

    # 3) directory/workbook hits should not dominate (dedup + confidence kept reasonable).
    main_u1 = next((b for b in boundaries if b["unit"] == "Unit 1"), None)
    assert main_u1 is not None
    assert main_u1.get("confidence", 0) >= 0.5

    # 4) short unit_textbook (<300) should be low_quality.
    tiny_split = [
        {"unit": "Unit 3", "theme": "Diverse Cultures", "text": "UNIT 3\nshort", "confidence": 0.9},
    ]
    tiny_drafts = build_unit_document_drafts(
        {"id": 1, "grade": "高一", "textbook": "人教版", "volume": "必修三"},
        tiny_split,
    )
    assert any(
        d["draft_type"] == "unit_textbook" and d.get("quality_status") == "low_quality"
        for d in tiny_drafts
    )

    # 5) long vocabulary should keep vocabulary draft.
    vocab_text = "Words and Expressions\n" + "\n".join([f"word{i} meaning example" for i in range(50)])
    vocab_split = [
        {"unit": "Unit 2", "theme": "Morals and Virtues", "text": f"UNIT 2\n{vocab_text}", "confidence": 0.8},
    ]
    vocab_drafts = build_unit_document_drafts(
        {"id": 2, "grade": "高一", "textbook": "人教版", "volume": "必修三"},
        vocab_split,
    )
    assert any(d["draft_type"] == "vocabulary" for d in vocab_drafts)

    app = create_app()
    app.config["TESTING"] = True
    src_doc = _seed_source_doc()
    try:
        with app.test_client() as client:
            # 9) split page open
            assert client.get(f"/knowledge/{src_doc['id']}/unit-split").status_code == 200

            # 8) rerun split should not infinitely increase pending drafts.
            resp1 = client.post(f"/knowledge/{src_doc['id']}/unit-split", follow_redirects=False)
            assert resp1.status_code in (302, 303)
            pending1 = len(list_knowledge_unit_drafts(source_document_id=src_doc["id"], status="pending"))

            resp2 = client.post(f"/knowledge/{src_doc['id']}/unit-split", follow_redirects=False)
            assert resp2.status_code in (302, 303)
            pending2 = len(list_knowledge_unit_drafts(source_document_id=src_doc["id"], status="pending"))
            assert pending2 <= pending1 + 2

        # 6/7) low-quality drafts should not be bulk-created.
        good = create_knowledge_unit_draft(
            {
                "source_document_id": src_doc["id"],
                "unit": "Unit 3",
                "theme": "Diverse Cultures",
                "draft_type": "unit_textbook",
                "suggested_title": "[TEST] good",
                "suggested_doc_type": "教材",
                "suggested_grade": "高一",
                "suggested_textbook": "人教版",
                "suggested_volume": "必修三",
                "suggested_unit": "Unit 3",
                "suggested_lesson_type": "Other",
                "suggested_tags": "test",
                "draft_text": "A" * 1200,
                "char_count": 1200,
                "confidence": 0.9,
                "quality_status": "good",
                "quality_warnings": "",
                "status": "pending",
            }
        )
        low = create_knowledge_unit_draft(
            {
                "source_document_id": src_doc["id"],
                "unit": "Unit 4",
                "theme": "Space Exploration",
                "draft_type": "unit_textbook",
                "suggested_title": "[TEST] low",
                "suggested_doc_type": "教材",
                "suggested_grade": "高一",
                "suggested_textbook": "人教版",
                "suggested_volume": "必修三",
                "suggested_unit": "Unit 4",
                "suggested_lesson_type": "Other",
                "suggested_tags": "test",
                "draft_text": "tiny text",
                "char_count": 9,
                "confidence": 0.3,
                "quality_status": "low_quality",
                "quality_warnings": "文本过短",
                "status": "pending",
            }
        )
        assert good["status"] == "pending" and low["status"] == "pending"

        with app.test_client() as client:
            resp = client.post(
                "/knowledge/unit-drafts/bulk-create",
                data={"source_document_id": str(src_doc["id"])},
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303)

        all_pending = list_knowledge_unit_drafts(source_document_id=src_doc["id"], status="pending")
        still_low_pending = [d for d in all_pending if d.get("quality_status") == "low_quality"]
        assert len(still_low_pending) >= 1
    finally:
        # cleanup test docs
        from models.database import query_knowledge_documents

        docs = query_knowledge_documents({"keyword": "[TEST]"}, limit=200)
        for d in docs:
            delete_knowledge_document(d["id"])

    print("ROUND_0261_OK")


if __name__ == "__main__":
    run()
