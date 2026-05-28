from app import create_app
from models.database import create_knowledge_document, create_knowledge_unit_draft, delete_knowledge_document, list_knowledge_unit_drafts
from services.textbook_catalog_service import CATALOG
from services.textbook_unit_split_service import (
    _quality_for_draft,
    build_unit_document_drafts,
    classify_draft_type,
    extract_unit_sections,
)


def run():
    # 1) reading extraction by "Reading and Thinking"
    txt1 = (
        "UNIT 3 THE INTERNET\nReading and Thinking\n"
        "Jan started an online community. She helped people with digital problems.\n"
        "Discovering Useful Structures\nGrammar block.\n"
    )
    sec1 = extract_unit_sections(txt1, textbook="人教版", volume="必修二", unit="Unit 3")
    assert "Jan started an online community" in (sec1.get("reading_and_thinking") or "")
    assert "Discovering Useful Structures" not in (sec1.get("reading_and_thinking") or "")

    # 2) reading extraction fallback by catalog reading_title
    txt2 = (
        "UNIT 5 THE VALUE OF MONEY\n"
        "The Million Pound Bank Note\n"
        "Henry walked in London and met two rich brothers. This is a story about money and values.\n"
        "Reading for Writing\n"
    )
    sec2 = extract_unit_sections(txt2, textbook="人教版", volume="必修三", unit="Unit 5")
    assert "Henry walked in London" in (sec2.get("reading_and_thinking") or "")

    # 3) vocabulary that looks like passage should be reclassified
    passage_like_vocab = (
        "Words and Expressions\n"
        "Jan decided to help older people. She created a support group online and shared practical tips.\n"
        "Many learners found useful information and became more confident in digital life.\n"
    )
    cls = classify_draft_type(passage_like_vocab, "vocabulary", unit="Unit 3", theme="The Internet")
    assert cls["draft_type"] in {"reading_text", "vocabulary"}
    if cls["draft_type"] == "reading_text":
        assert cls["force_warning"] is True

    # 4) reading_text char_count <300 not good
    q4, _ = _quality_for_draft({"draft_type": "reading_text", "draft_text": "Reading and Thinking\nshort text", "char_count": 120})
    assert q4 != "good"

    # 5) reading_text >=500 and clean can be good
    long_reading = "Reading and Thinking\n" + ("This is a meaningful paragraph about life and values. " * 20)
    q5, _ = _quality_for_draft({"draft_type": "reading_text", "draft_text": long_reading, "char_count": len(long_reading)})
    assert q5 in {"good", "warning"}

    # 6) catalog has required reading titles for 必修三 Unit1-5
    req3 = CATALOG.get("人教版", {}).get("必修三", {})
    for u in ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5"]:
        assert (req3.get(u) or {}).get("reading_title")

    # 7) unit split diagnostics-like check: missing reading detectable at service level
    split = [
        {
            "unit": "Unit 1",
            "theme": "Festivals and Celebrations",
            "text": "UNIT 1\nWords and Expressions\nfestival n. 节日\nculture n. 文化\n",
            "confidence": 0.9,
        }
    ]
    drafts = build_unit_document_drafts(
        {"id": 1, "grade": "高一", "textbook": "人教版", "volume": "必修三"},
        split,
    )
    assert not any(d.get("draft_type") == "reading_text" for d in drafts)

    # 8) bulk-create should not create suspected misclassified drafts
    app = create_app()
    app.config["TESTING"] = True
    src = create_knowledge_document(
        {
            "title": "[TEST] Round0263 Source",
            "doc_type": "教材",
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修三",
            "unit": "通用",
            "lesson_type": "Other",
            "source_type": "text",
            "parsed_text": "source",
            "summary": "test",
            "word_count": 100,
            "status": "parsed",
        }
    )
    try:
        bad = create_knowledge_unit_draft(
            {
                "source_document_id": src["id"],
                "unit": "Unit 3",
                "theme": "Diverse Cultures",
                "draft_type": "vocabulary",
                "suggested_title": "[TEST] suspicious vocab",
                "suggested_doc_type": "词汇表",
                "suggested_grade": "高一",
                "suggested_textbook": "人教版",
                "suggested_volume": "必修三",
                "suggested_unit": "Unit 3",
                "suggested_lesson_type": "Vocabulary",
                "suggested_tags": "test",
                "draft_text": "Words and Expressions\n" + ("Long paragraph sentence. " * 30),
                "char_count": 800,
                "quality_status": "good",
                "quality_warnings": "疑似课文内容被识别为词汇表，请人工确认。",
                "estimated_vocab_items": 3,
                "status": "pending",
            }
        )
        assert bad
        with app.test_client() as client:
            resp = client.post(
                "/knowledge/unit-drafts/bulk-create",
                data={"source_document_id": str(src["id"])},
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303)
        pending = list_knowledge_unit_drafts(source_document_id=src["id"], status="pending")
        assert any(d["id"] == bad["id"] for d in pending)

        # 9) split page should open (includes missing reading diagnostics in template)
        with app.test_client() as client:
            assert client.get(f"/knowledge/{src['id']}/unit-split").status_code == 200
    finally:
        delete_knowledge_document(src["id"])

    print("ROUND_0263_OK")


if __name__ == "__main__":
    run()
