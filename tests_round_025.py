import json

from app import create_app
from models.database import create_knowledge_document, delete_knowledge_document, get_db
from services.lesson_readiness_service import check_lesson_knowledge_readiness


def _seed_doc(title, **extra):
    payload = {
        "title": title,
        "doc_type": "课文",
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修三",
        "unit": "Unit 5",
        "lesson_type": "Reading",
        "source_type": "text",
        "file_name": "",
        "original_file_path": "",
        "text_file_path": "",
        "parsed_text": "test content",
        "summary": "test",
        "word_count": 20,
        "tags": "test",
        "status": "parsed",
        "error_message": "",
        "embedding_status": "indexed",
        "chunk_count": 3,
        "vector_collection": "english_teaching_knowledge",
        "embedding_error": "",
        "indexed_at": "2026-01-01 00:00:00",
        "is_whole_book": 0,
    }
    payload.update(extra)
    return create_knowledge_document(payload)


def run():
    # 1 no material -> missing
    req = {"textbook": "人教版", "grade": "高一", "volume": "必修三", "unit": "Unit 5", "lesson_type": "Reading", "topic": ""}
    base = check_lesson_knowledge_readiness(req)
    assert base["status"] in {"missing", "warning"}

    # 2 whole-book only -> warning
    whole = _seed_doc(
        "[TEST] Round025 Whole Book",
        doc_type="教材",
        is_whole_book=1,
        lesson_type="Other",
    )
    try:
        whole_readiness = check_lesson_knowledge_readiness(req)
        assert whole_readiness["status"] == "warning"
    finally:
        delete_knowledge_document(whole["id"])

    # 3 reading plan + vocab should improve score
    reading = _seed_doc("[TEST] Round025 Reading", doc_type="课文", lesson_type="Reading")
    plan = _seed_doc("[TEST] Round025 Plan", doc_type="教案", lesson_type="Reading")
    vocab = _seed_doc("[TEST] Round025 Vocab", doc_type="词汇表", lesson_type="Vocabulary")
    try:
        improved = check_lesson_knowledge_readiness(req)
        assert improved["score"] >= base["score"]
        assert improved["has_lesson_plan"] is True
        assert improved["has_vocabulary"] is True
    finally:
        delete_knowledge_document(reading["id"])
        delete_knowledge_document(plan["id"])
        delete_knowledge_document(vocab["id"])

    # 4 placeholder does not count as ready
    placeholder = _seed_doc(
        "[TEST] Round025 Placeholder 资料占位",
        doc_type="其他",
        tags="资料占位",
        lesson_type="Reading",
        word_count=0,
        status="pending",
        embedding_status="not_indexed",
        chunk_count=0,
    )
    try:
        ph = check_lesson_knowledge_readiness(req)
        assert ph["has_reading"] is False or ph["status"] != "ready"
    finally:
        delete_knowledge_document(placeholder["id"])

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        # 5 readiness endpoint
        r = client.get("/ppt/knowledge-readiness?textbook=人教版&grade=高一&volume=必修二&unit=Unit%203&lesson_type=Reading")
        assert r.status_code == 200
        data = r.get_json()
        assert isinstance(data, dict)
        assert data.get("supplement_links")

        # 6/7 new and manuscript pages contain readiness entry
        new_html = client.get("/ppt/new").data.decode("utf-8", errors="ignore")
        assert "知识库准备度" in new_html
        manu_html = client.get("/ppt/from-manuscript").data.decode("utf-8", errors="ignore")
        assert "知识库准备度" in manu_html

        # 8/9 create task with missing readiness should still continue and persist readiness
        title = "[TEST] Round025 New Task"
        res = client.post(
            "/ppt/new",
            data={
                "course_title": title,
                "grade": "高一",
                "textbook": "人教版",
                "volume": "必修三",
                "unit": "Unit 5",
                "lesson_type": "Reading",
                "duration": "45",
                "student_level": "中等",
                "style": "常规课",
                "ppt_style": "default",
                "extra_requirements": "",
            },
            follow_redirects=False,
        )
        assert res.status_code in (302, 303)
        location = res.headers.get("Location") or ""
        assert "/ppt/task/" in location and "/edit" in location
        task_id = int(location.split("/ppt/task/")[1].split("/")[0])
        with get_db() as conn:
            row = conn.execute("SELECT id, knowledge_context_json FROM lesson_tasks WHERE id=?", (task_id,)).fetchone()
            assert row is not None
            ctx = json.loads(row["knowledge_context_json"] or "{}")
            assert "readiness" in ctx
            conn.execute("DELETE FROM ppt_slides WHERE task_id=?", (row["id"],))
            conn.execute("DELETE FROM lesson_tasks WHERE id=?", (row["id"],))

    print("ROUND_025_OK")


if __name__ == "__main__":
    run()
