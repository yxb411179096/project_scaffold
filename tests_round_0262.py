from app import create_app
from models.database import (
    create_knowledge_document,
    create_knowledge_unit_draft,
    delete_knowledge_document,
    list_knowledge_unit_drafts,
)
from services.textbook_unit_split_service import (
    _quality_for_draft,
    build_unit_document_drafts,
    extract_unit_sections,
)


def _make_vocab_lines(n):
    return "\n".join([f"word{i} n. 单词{i}" for i in range(1, n + 1)])


def run():
    # 1) vocabulary should cut at WORKBOOK
    unit_text1 = (
        "UNIT 3 THE INTERNET\nWords and Expressions\n"
        + _make_vocab_lines(12)
        + "\nWORKBOOK\nListen to the passage.\n"
    )
    sections1 = extract_unit_sections(unit_text1)
    vocab1 = sections1.get("vocabulary", "")
    assert "WORKBOOK" not in vocab1
    assert "Listen to the passage" not in vocab1

    # 2) vocabulary should cut at next UNIT
    unit_text2 = (
        "UNIT 3 THE INTERNET\nWords and Expressions\n"
        + _make_vocab_lines(11)
        + "\nUNIT 4 SPACE EXPLORATION\nReading and Thinking\n"
    )
    sections2 = extract_unit_sections(unit_text2)
    vocab2 = sections2.get("vocabulary", "")
    assert "UNIT 4 SPACE EXPLORATION" not in vocab2

    # 3) contamination cannot be good
    q3, w3 = _quality_for_draft(
        {
            "draft_type": "vocabulary",
            "draft_text": "Words and Expressions\n" + _make_vocab_lines(12) + "\nWORKBOOK\nComplete the sentences.",
            "char_count": 600,
        }
    )
    assert q3 != "good"
    assert "Workbook" in w3 or "练习" in w3

    # 4) <5 items => low_quality
    q4, _ = _quality_for_draft(
        {"draft_type": "vocabulary", "draft_text": "Words and Expressions\nword n. 词\nrun v. 跑", "char_count": 180}
    )
    assert q4 == "low_quality"

    # 5) 5-10 items => warning
    q5, _ = _quality_for_draft(
        {"draft_type": "vocabulary", "draft_text": "Words and Expressions\n" + _make_vocab_lines(7), "char_count": 260}
    )
    assert q5 == "warning"

    # 6) >10 clean items => good
    q6, _ = _quality_for_draft(
        {"draft_type": "vocabulary", "draft_text": "Words and Expressions\n" + _make_vocab_lines(12), "char_count": 460}
    )
    assert q6 == "good"

    # 7) cross-unit warning
    q7, w7 = _quality_for_draft(
        {
            "draft_type": "vocabulary",
            "draft_text": "Words and Expressions\nUnit 3\n"
            + _make_vocab_lines(11)
            + "\nUnit 4\nnext list",
            "char_count": 520,
        }
    )
    assert q7 != "good"
    assert "跨单元" in w7

    # 8) sticky OCR-like short text cannot be good
    q8, _ = _quality_for_draft(
        {
            "draft_type": "vocabulary",
            "draft_text": "SPORTS AND FITNESSUNIT 3 SPORTS AND FITNESSUNIT 3 skiing marathon track boxing badminton soccer 83",
            "char_count": 96,
        }
    )
    assert q8 != "good"

    # 9) bulk-create only good drafts, warning/low remain pending
    app = create_app()
    app.config["TESTING"] = True
    src = create_knowledge_document(
        {
            "title": "[TEST] Round0262 Source",
            "doc_type": "教材",
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修一",
            "unit": "通用",
            "lesson_type": "Other",
            "source_type": "text",
            "parsed_text": "unit split source",
            "summary": "test",
            "word_count": 100,
            "tags": "test",
            "status": "parsed",
        }
    )
    try:
        good = create_knowledge_unit_draft(
            {
                "source_document_id": src["id"],
                "unit": "Unit 3",
                "theme": "Sports and Fitness",
                "draft_type": "vocabulary",
                "suggested_title": "[TEST] good vocab",
                "suggested_doc_type": "词汇表",
                "suggested_grade": "高一",
                "suggested_textbook": "人教版",
                "suggested_volume": "必修一",
                "suggested_unit": "Unit 3",
                "suggested_lesson_type": "Vocabulary",
                "suggested_tags": "test",
                "draft_text": "Words and Expressions\n" + _make_vocab_lines(12),
                "char_count": 460,
                "quality_status": "good",
                "quality_warnings": "",
                "estimated_vocab_items": 12,
                "status": "pending",
            }
        )
        warn = create_knowledge_unit_draft(
            {
                "source_document_id": src["id"],
                "unit": "Unit 3",
                "theme": "Sports and Fitness",
                "draft_type": "vocabulary",
                "suggested_title": "[TEST] warn vocab",
                "suggested_doc_type": "词汇表",
                "suggested_grade": "高一",
                "suggested_textbook": "人教版",
                "suggested_volume": "必修一",
                "suggested_unit": "Unit 3",
                "suggested_lesson_type": "Vocabulary",
                "suggested_tags": "test",
                "draft_text": "Words and Expressions\n" + _make_vocab_lines(6),
                "char_count": 260,
                "quality_status": "warning",
                "quality_warnings": "词汇条目偏少",
                "estimated_vocab_items": 6,
                "status": "pending",
            }
        )
        low = create_knowledge_unit_draft(
            {
                "source_document_id": src["id"],
                "unit": "Unit 4",
                "theme": "Natural Disasters",
                "draft_type": "vocabulary",
                "suggested_title": "[TEST] low vocab",
                "suggested_doc_type": "词汇表",
                "suggested_grade": "高一",
                "suggested_textbook": "人教版",
                "suggested_volume": "必修一",
                "suggested_unit": "Unit 4",
                "suggested_lesson_type": "Vocabulary",
                "suggested_tags": "test",
                "draft_text": "word list",
                "char_count": 20,
                "quality_status": "low_quality",
                "quality_warnings": "文本过短",
                "estimated_vocab_items": 1,
                "status": "pending",
            }
        )
        assert good and warn and low
        with app.test_client() as client:
            resp = client.post(
                "/knowledge/unit-drafts/bulk-create",
                data={"source_document_id": str(src["id"])},
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303)
        pending = list_knowledge_unit_drafts(source_document_id=src["id"], status="pending")
        assert any(d["id"] == warn["id"] for d in pending)
        assert any(d["id"] == low["id"] for d in pending)
    finally:
        delete_knowledge_document(src["id"])

    # 10) draft builder keeps vocabulary draft with quality metadata
    drafts = build_unit_document_drafts(
        {"id": 99, "grade": "高一", "textbook": "人教版", "volume": "必修一"},
        [
            {
                "unit": "Unit 3",
                "theme": "Sports and Fitness",
                "text": "UNIT 3\nWords and Expressions\n" + _make_vocab_lines(12),
                "confidence": 0.8,
            }
        ],
    )
    vocab_drafts = [d for d in drafts if d.get("draft_type") == "vocabulary"]
    assert len(vocab_drafts) >= 1
    assert "estimated_vocab_items" in vocab_drafts[0]

    print("ROUND_0262_OK")


if __name__ == "__main__":
    run()
