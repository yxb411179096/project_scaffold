from pathlib import Path
import tempfile

from pypdf import PdfWriter

from app import create_app
from models.database import create_knowledge_document, delete_knowledge_document, get_knowledge_document, query_knowledge_documents
from services.pdf_page_range_split_service import (
    build_page_range_drafts,
    clean_extracted_pdf_text,
    detect_text_garbled,
    extract_text_by_page_range,
    get_pdf_page_count,
)


def _make_blank_pdf(path: Path, pages=6):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=595, height=842)
    with path.open("wb") as f:
        writer.write(f)


def run():
    # 1) page count unavailable on missing pdf
    missing_doc = {"original_file_path": "/tmp/does-not-exist-027.pdf"}
    info_missing = get_pdf_page_count(missing_doc)
    assert info_missing["available"] is False

    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "sample.pdf"
        _make_blank_pdf(pdf_path, pages=6)
        doc_stub = {"original_file_path": str(pdf_path)}

        # 2) extract with page_offset returns mapped actual pages
        extracted = extract_text_by_page_range(doc_stub, start_page=1, end_page=2, page_offset=2)
        assert extracted["actual_start_page"] == 3
        assert extracted["actual_end_page"] == 4

    # 3) clean text
    cleaned = clean_extracted_pdf_text("  hello   world \n\n  12 \n\nA   B")
    assert "hello world" in cleaned
    assert "\n12\n" not in f"\n{cleaned}\n"

    # 4) garbled detect
    garbled = detect_text_garbled("abc ■■■ □□ � strange ###")
    assert garbled["garbled"] is True

    # 5/6) build page range drafts + garbled quality
    source_doc = {"id": 1, "grade": "高一", "textbook": "人教版", "volume": "必修一"}
    drafts = build_page_range_drafts(
        source_doc,
        [
            {
                "unit": "Unit 1",
                "theme": "Teenage Life",
                "start_page": 1,
                "end_page": 3,
                "actual_start_page": 5,
                "actual_end_page": 7,
                "text": "good text " * 200,
                "warnings": [],
            },
            {
                "unit": "Unit 2",
                "theme": "Travelling Around",
                "start_page": 4,
                "end_page": 4,
                "actual_start_page": 8,
                "actual_end_page": 8,
                "text": "乱码 ■■■ ■■■ �",
                "warnings": [],
            },
        ],
    )
    assert len(drafts) == 2
    assert drafts[0]["draft_type"] == "page_range_unit_textbook"
    assert drafts[1]["quality_status"] != "good"

    app = create_app()
    app.config["TESTING"] = True

    with tempfile.TemporaryDirectory() as td:
        pdf_path = Path(td) / "book.pdf"
        _make_blank_pdf(pdf_path, pages=12)
        source = create_knowledge_document(
            {
                "title": "[TEST] Round027 Source PDF",
                "doc_type": "教材",
                "grade": "高一",
                "textbook": "人教版",
                "volume": "必修一",
                "unit": "通用",
                "lesson_type": "Other",
                "source_type": "file",
                "file_name": "book.pdf",
                "original_file_path": str(pdf_path),
                "text_file_path": "",
                "parsed_text": "book text",
                "summary": "test",
                "word_count": 100,
                "tags": "整本教材",
                "status": "parsed",
                "is_whole_book": True,
            }
        )

        try:
            with app.test_client() as client:
                # 7) page range split page open
                assert client.get(f"/knowledge/{source['id']}/page-range-split").status_code == 200

                # generate drafts
                data = {
                    "page_offset": "0",
                    "enabled_Unit_1": "on",
                    "start_page_Unit_1": "1",
                    "end_page_Unit_1": "2",
                    "enabled_Unit_2": "on",
                    "start_page_Unit_2": "3",
                    "end_page_Unit_2": "4",
                }
                resp = client.post(f"/knowledge/{source['id']}/page-range-split", data=data, follow_redirects=False)
                assert resp.status_code in (302, 303)

                page = client.get(f"/knowledge/{source['id']}/page-range-split")
                assert page.status_code == 200
                assert b"Round027 Source PDF" in page.data

            from models.database import list_knowledge_unit_drafts
            drafts_rows = [d for d in list_knowledge_unit_drafts(source_document_id=source["id"]) if str(d.get("draft_type")).startswith("page_range_")]
            assert len(drafts_rows) >= 1
            d0 = drafts_rows[0]

            with app.test_client() as client:
                # 8) update draft
                resp = client.post(
                    f"/knowledge/page-range-drafts/{d0['id']}/update",
                    data={
                        "suggested_title": "[TEST] Updated Draft",
                        "suggested_doc_type": "教材",
                        "suggested_lesson_type": "Other",
                        "suggested_tags": "test,page_range",
                        "draft_text": "Updated text content for draft.",
                    },
                    follow_redirects=False,
                )
                assert resp.status_code in (302, 303)

                # 9) create document
                resp = client.post(f"/knowledge/page-range-drafts/{d0['id']}/create-document", follow_redirects=False)
                assert resp.status_code in (302, 303)

                # create-and-index route callable
                resp = client.post(f"/knowledge/page-range-drafts/{d0['id']}/create-and-index", follow_redirects=False)
                assert resp.status_code in (302, 303)

                # 11) old auto split still open
                assert client.get(f"/knowledge/{source['id']}/unit-split").status_code == 200

                # 12) old pages unaffected
                assert client.get("/knowledge").status_code == 200
                assert client.get("/knowledge/governance").status_code == 200
                assert client.get("/knowledge/coverage").status_code == 200

            # 10) created docs query no crash / coverage path usable
            created_docs = query_knowledge_documents({"keyword": "[TEST] Updated Draft"}, limit=10)
            assert len(created_docs) >= 1
            _ = get_knowledge_document(created_docs[0]["id"])
        finally:
            # cleanup test docs
            docs = query_knowledge_documents({"keyword": "[TEST]"}, limit=200)
            for doc in docs:
                delete_knowledge_document(doc["id"])

    print("ROUND_027_OK")


if __name__ == "__main__":
    run()
