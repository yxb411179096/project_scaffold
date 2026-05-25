import json
import re
import sqlite3
import uuid

from app import create_app
from config import DATABASE_PATH
from services.agents import generate_lesson_design
import routes.ppt_routes as ppt_routes
import services.knowledge_retrieval_service as krs
import services.llm_service as llm_service
from services.embedding_service import EmbeddingServiceError, test_embedding_connection
from services.knowledge_retrieval_service import (
    build_knowledge_filters,
    build_knowledge_query,
    build_chroma_where,
    format_knowledge_context_for_prompt,
    retrieve_knowledge_context,
)


def _extract_doc_id(location):
    match = re.search(r"/knowledge/(\d+)", str(location or ""))
    return int(match.group(1)) if match else None


def _create_knowledge_doc(client, title_prefix, raw_text):
    response = client.post(
        "/knowledge/new",
        data={
            "title": f"{title_prefix} Knowledge",
            "doc_type": "教案",
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修一",
            "unit": "Unit 1",
            "lesson_type": "Reading",
            "tags": "round15,test",
            "raw_text": raw_text,
        },
        follow_redirects=False,
    )
    assert response.status_code in (302, 303)
    doc_id = _extract_doc_id(response.headers.get("Location"))
    assert doc_id
    return doc_id


def _cleanup_prefix(prefix):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            "DELETE FROM ppt_slides WHERE task_id IN (SELECT id FROM lesson_tasks WHERE course_title LIKE ?)",
            (f"{prefix}%",),
        )
        conn.execute(
            "DELETE FROM lesson_tasks WHERE course_title LIKE ?",
            (f"{prefix}%",),
        )
        conn.execute(
            "DELETE FROM knowledge_chunks WHERE document_id IN (SELECT id FROM knowledge_documents WHERE title LIKE ?)",
            (f"{prefix}%",),
        )
        conn.execute(
            "DELETE FROM knowledge_documents WHERE title LIKE ?",
            (f"{prefix}%",),
        )
        conn.commit()


def run():
    app = create_app()
    app.config["TESTING"] = True
    title_prefix = f"[TEST] Round15 {uuid.uuid4().hex[:8]}"
    cleanup_ids = []

    query = build_knowledge_query(
        {
            "topic": "Unit 3 Sports and Fitness",
            "grade": "高一",
            "textbook": "人教版",
            "unit": "Unit 3",
            "lesson_type": "Reading",
            "extra_requirements": "Use classroom interaction and vocabulary support.",
        },
        manuscript_text="Students predict, discuss, and summarize the reading lesson.",
    )
    assert "Sports and Fitness" in query or "Unit 3" in query

    filters = build_knowledge_filters(
        {
            "grade": "",
            "textbook": "全部",
            "volume": "通用",
            "unit": "",
            "lesson_type": "",
        }
    )
    assert filters == {}

    assert build_chroma_where({}) is None
    assert build_chroma_where({"lesson_type": "Reading"}) == {"lesson_type": "Reading"}
    assert build_chroma_where({"lesson_type": ["Reading"]}) == {"lesson_type": "Reading"}
    multi_or = build_chroma_where({"lesson_type": ["Reading", "reading"]})
    assert isinstance(multi_or, dict) and "$or" in multi_or
    assert len(multi_or["$or"]) >= 2
    multi_and = build_chroma_where({"grade": "高一", "textbook": "人教版", "lesson_type": "Reading"})
    assert isinstance(multi_and, dict) and "$and" in multi_and
    assert len(multi_and["$and"]) >= 2

    unit_filters = build_knowledge_filters(
        {
            "grade": "高一",
            "textbook": "人教版",
            "volume": "必修一",
            "unit": "unit4",
            "lesson_type": "reading",
        }
    )
    assert "unit" in unit_filters
    assert isinstance(unit_filters["unit"], list)
    assert any(str(item).lower() == "unit 4" or str(item).lower() == "unit4" for item in unit_filters["unit"])
    assert "lesson_type" in unit_filters
    assert isinstance(unit_filters["lesson_type"], list)
    assert any(str(item).lower() == "reading" for item in unit_filters["lesson_type"])
    assert build_chroma_where(unit_filters) is not None
    assert ppt_routes.normalize_relaxed_level("no_filters") == "no_filters"
    assert ppt_routes.normalize_relaxed_level(3) == "lesson_type_only"
    assert ppt_routes.normalize_relaxed_level(None) == "unknown"
    assert ppt_routes.normalize_relaxed_level("0") == "exact"

    prompt_text = format_knowledge_context_for_prompt(
        {
            "query": "reading lesson support",
            "top_k": 2,
            "relaxed": False,
            "results": [
                {
                    "document_id": 11,
                    "title": "Unit 1 Reading Lesson",
                    "doc_type": "教案",
                    "grade": "高一",
                    "textbook": "人教版",
                    "volume": "必修一",
                    "unit": "Unit 1",
                    "lesson_type": "Reading",
                    "chunk_text": "Lead-in -> prediction -> reading -> summary.",
                    "distance": 0.21,
                    "score": 0.79,
                }
            ],
        }
    )
    assert "知识库参考资料 1" in prompt_text
    assert "Unit 1 Reading Lesson" in prompt_text
    assert "命中数量" in prompt_text

    original_search_similar = krs.search_similar
    try:
        calls = []

        def _stage_search(query, filters=None, top_k=5, query_embedding=None):
            calls.append(filters or {})
            if len(calls) == 4:
                return [
                    {
                        "document_id": 88,
                        "title": "Stage Four Match",
                        "doc_type": "教案",
                        "grade": "高一",
                        "textbook": "人教版",
                        "volume": "必修一",
                        "unit": "Unit 4",
                        "lesson_type": "Reading",
                        "chunk_text": "Matched by relaxed filters.",
                        "distance": 0.12,
                        "score": 0.88,
                    }
                ]
            return []

        krs.search_similar = _stage_search
        relaxed_context = retrieve_knowledge_context(
            {
                "use_knowledge_base": True,
                "grade": "高一",
                "textbook": "人教版",
                "unit": "unit4",
                "volume": "必修一",
                "lesson_type": "Reading",
                "extra_requirements": "fallback test",
            },
            top_k=3,
            manuscript_text="Simple text.",
        )
        assert relaxed_context["failed"] is False
        assert relaxed_context["result_count"] == 1
        assert relaxed_context["relaxed"] is True
        assert relaxed_context["relaxed_level"] == "lesson_type_only"
        assert calls[0].get("unit")
        assert calls[3].get("lesson_type")
    finally:
        krs.search_similar = original_search_similar

    original_ollama_payload = llm_service._call_ollama_payload
    try:
        retry_state = {"count": 0}

        def _fake_ollama_payload(*_args, **_kwargs):
            retry_state["count"] += 1
            if retry_state["count"] == 1:
                raise llm_service.LLMServiceError("Model returned an empty response.")
            return {"ok": True}

        llm_service._call_ollama_payload = _fake_ollama_payload
        retry_result = llm_service._call_ollama_payload_with_retry(
            {"model_name": "qwen3:30b", "base_url": "http://127.0.0.1:11434"},
            "system",
            "user",
            120,
            0.35,
            1024,
            True,
        )
        assert retry_state["count"] == 2
        assert retry_result == {"ok": True}

        retry_state["count"] = 0

        def _always_empty(*_args, **_kwargs):
            retry_state["count"] += 1
            raise llm_service.LLMServiceError("Model returned an empty response.")

        llm_service._call_ollama_payload = _always_empty
        rule_result = generate_lesson_design(
            {
                "lesson_type": "Reading",
                "topic": "The Power of Reading",
            }
        )
        assert retry_state["count"] == 2
        assert isinstance(rule_result, dict)
        assert rule_result.get("teaching_objectives")
    finally:
        llm_service._call_ollama_payload = original_ollama_payload

    embedding_probe = test_embedding_connection()
    embedding_available = embedding_probe.get("status") == "available"

    with app.test_client() as client:
        assert client.get("/knowledge").status_code == 200
        assert client.get("/knowledge/search-semantic").status_code == 200
        assert client.get("/ppt/new").status_code == 200
        assert client.get("/ppt/from-manuscript").status_code == 200
        assert "use_knowledge_base" in client.get("/ppt/new").get_data(as_text=True)
        assert "use_knowledge_base" in client.get("/ppt/from-manuscript").get_data(as_text=True)

        edit_task_title = f"{title_prefix} Relaxed Level Task"
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO lesson_tasks
                (course_title, grade, textbook, unit, lesson_type, duration, student_level, style, extra_requirements,
                 use_knowledge_base, knowledge_query, knowledge_top_k, knowledge_context_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    edit_task_title,
                    "高一",
                    "人教版",
                    "Unit 4",
                    "Reading",
                    45,
                    "高一",
                    "课堂教学",
                    "",
                    1,
                    "reading",
                    5,
                    json.dumps(
                        {
                            "enabled": True,
                            "query": "reading",
                            "top_k": 5,
                            "result_count": 0,
                            "relaxed": True,
                            "relaxed_level": "no_filters",
                            "used_filters": {},
                            "failed": False,
                            "error": "",
                            "results": [],
                        },
                        ensure_ascii=False,
                    ),
                    "draft",
                ),
            )
            relaxed_task_id = cur.lastrowid
            conn.commit()

        relaxed_resp = client.get(f"/ppt/task/{relaxed_task_id}/edit")
        assert relaxed_resp.status_code == 200
        relaxed_html = relaxed_resp.get_data(as_text=True)
        assert "无筛选语义检索" in relaxed_html

        legacy_task_title = f"{title_prefix} Legacy Relaxed Task"
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO lesson_tasks
                (course_title, grade, textbook, unit, lesson_type, duration, student_level, style, extra_requirements,
                 use_knowledge_base, knowledge_query, knowledge_top_k, knowledge_context_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    legacy_task_title,
                    "高一",
                    "人教版",
                    "Unit 4",
                    "Reading",
                    45,
                    "高一",
                    "课堂教学",
                    "",
                    1,
                    "reading",
                    5,
                    json.dumps(
                        {
                            "enabled": True,
                            "query": "reading",
                            "top_k": 5,
                            "result_count": 0,
                            "relaxed": True,
                            "relaxed_level": 3,
                            "used_filters": {},
                            "failed": False,
                            "error": "",
                            "results": [],
                        },
                        ensure_ascii=False,
                    ),
                    "draft",
                ),
            )
            legacy_task_id = cur.lastrowid
            conn.commit()

        legacy_resp = client.get(f"/ppt/task/{legacy_task_id}/edit")
        assert legacy_resp.status_code == 200
        assert "仅按课型匹配" in legacy_resp.get_data(as_text=True)

        none_level_title = f"{title_prefix} None Level Task"
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO lesson_tasks
                (course_title, grade, textbook, unit, lesson_type, duration, student_level, style, extra_requirements,
                 use_knowledge_base, knowledge_query, knowledge_top_k, knowledge_context_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    none_level_title,
                    "高一",
                    "人教版",
                    "Unit 4",
                    "Reading",
                    45,
                    "高一",
                    "课堂教学",
                    "",
                    1,
                    "reading",
                    5,
                    json.dumps(
                        {
                            "enabled": True,
                            "query": "reading",
                            "top_k": 5,
                            "result_count": 0,
                            "relaxed": False,
                            "relaxed_level": None,
                            "used_filters": {},
                            "failed": False,
                            "error": "",
                            "results": [],
                        },
                        ensure_ascii=False,
                    ),
                    "draft",
                ),
            )
            none_task_id = cur.lastrowid
            conn.commit()

        none_resp = client.get(f"/ppt/task/{none_task_id}/edit")
        assert none_resp.status_code == 200
        assert "未知" in none_resp.get_data(as_text=True)

        link_task_title = f"{title_prefix} Link Task"
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute(
                """
                INSERT INTO lesson_tasks
                (course_title, grade, textbook, unit, lesson_type, duration, student_level, style, extra_requirements,
                 use_knowledge_base, knowledge_query, knowledge_top_k, knowledge_context_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    link_task_title,
                    "高一",
                    "人教版",
                    "Unit 4",
                    "Reading",
                    45,
                    "高一",
                    "课堂教学",
                    "",
                    1,
                    "reading",
                    5,
                    json.dumps(
                        {
                            "enabled": True,
                            "query": "reading",
                            "top_k": 5,
                            "result_count": 1,
                            "relaxed": False,
                            "relaxed_level": "exact",
                            "used_filters": {},
                            "failed": False,
                            "error": "",
                            "results": [
                                {
                                    "document_id": 123456,
                                    "title": "Linked Knowledge Document",
                                    "doc_type": "教案",
                                    "grade": "高一",
                                    "textbook": "人教版",
                                    "volume": "必修一",
                                    "unit": "Unit 4",
                                    "lesson_type": "Reading",
                                    "tags": "test",
                                    "chunk_text": "Reference chunk for edit page link test.",
                                    "distance": 0.12,
                                    "score": 0.88,
                                }
                            ],
                        },
                        ensure_ascii=False,
                    ),
                    "draft",
                ),
            )
            link_task_id = cur.lastrowid
            conn.commit()

        link_resp = client.get(f"/ppt/task/{link_task_id}/edit")
        assert link_resp.status_code == 200
        link_html = link_resp.get_data(as_text=True)
        assert "查看原资料" in link_html
        assert "/knowledge/123456" in link_html

        plain_title = f"{title_prefix} Plain"
        plain_resp = client.post(
            "/ppt/new",
            data={
                "course_title": plain_title,
                "grade": "高一",
                "textbook": "人教版",
                "unit": "Unit 1",
                "lesson_type": "Reading",
                "duration": "45",
                "student_level": "中等",
                "style": "常规课",
                "extra_requirements": "No knowledge base.",
            },
            follow_redirects=False,
        )
        assert plain_resp.status_code in (302, 303)

        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM lesson_tasks WHERE course_title=?",
                (plain_title,),
            ).fetchone()
            assert row is not None
            assert int(row["use_knowledge_base"] or 0) == 0
            assert str(row["knowledge_context_json"] or "").strip() == ""
            slide_count = conn.execute(
                "SELECT COUNT(*) AS c FROM ppt_slides WHERE task_id=?",
                (row["id"],),
            ).fetchone()["c"]
            assert int(slide_count or 0) > 0

        failure_title = f"{title_prefix} KB Failure"
        original_route_retriever = ppt_routes.retrieve_knowledge_context
        try:
            def _forced_failure(*_args, **_kwargs):
                return {
                    "enabled": True,
                    "ok": False,
                    "failed": True,
                    "error": "forced failure",
                    "query": "forced failure query",
                    "top_k": 3,
                    "used_filters": {},
                    "relaxed": False,
                    "results": [],
                    "result_count": 0,
                    "trace": {
                        "type": "knowledge_retrieval",
                        "query": "forced failure query",
                        "top_k": 3,
                        "filters": {},
                        "result_count": 0,
                        "relaxed": False,
                        "failed": True,
                        "error": "forced failure",
                        "duration_ms": 1,
                    },
                }

            ppt_routes.retrieve_knowledge_context = _forced_failure
            failure_resp = client.post(
                "/ppt/new",
                data={
                    "course_title": failure_title,
                    "grade": "高一",
                    "textbook": "人教版",
                    "unit": "Unit 1",
                    "lesson_type": "Reading",
                    "duration": "45",
                    "student_level": "中等",
                    "style": "常规课",
                    "extra_requirements": "Knowledge fallback test.",
                    "use_knowledge_base": "on",
                    "knowledge_top_k": "3",
                    "knowledge_query": "forced failure query",
                },
                follow_redirects=True,
            )
            assert failure_resp.status_code == 200
            failure_text = failure_resp.get_data(as_text=True)
            assert "知识库参考资料" in failure_text
            assert "失败" in failure_text or "未检索到匹配资料" in failure_text
        finally:
            ppt_routes.retrieve_knowledge_context = original_route_retriever

        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM lesson_tasks WHERE course_title=?",
                (failure_title,),
            ).fetchone()
            assert row is not None
            assert int(row["use_knowledge_base"] or 0) == 1
            assert "forced failure" in str(row["knowledge_context_json"] or "")
            slide_count = conn.execute(
                "SELECT COUNT(*) AS c FROM ppt_slides WHERE task_id=?",
                (row["id"],),
            ).fetchone()["c"]
            assert int(slide_count or 0) > 0

        if embedding_available:
            knowledge_doc_id = _create_knowledge_doc(
                client,
                title_prefix,
                "This is a reading lesson reference. Students predict, discuss, and summarize.\n\n"
                "It also supports vocabulary and interaction design.",
            )
            cleanup_ids.append(knowledge_doc_id)

            index_resp = client.post(f"/knowledge/{knowledge_doc_id}/index", follow_redirects=False)
            assert index_resp.status_code in (302, 303)

            with sqlite3.connect(DATABASE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM knowledge_documents WHERE id=?",
                    (knowledge_doc_id,),
                ).fetchone()
                assert row is not None
                assert str(row["embedding_status"] or "") == "indexed"
                assert int(row["chunk_count"] or 0) > 0

            success_title = f"{title_prefix} KB Success"
            success_resp = client.post(
                "/ppt/new",
                data={
                    "course_title": success_title,
                    "grade": "高一",
                    "textbook": "人教版",
                    "unit": "Unit 1",
                    "lesson_type": "Reading",
                    "duration": "45",
                    "student_level": "中等",
                    "style": "常规课",
                    "extra_requirements": "Knowledge success test.",
                    "use_knowledge_base": "on",
                    "knowledge_top_k": "3",
                    "knowledge_query": "predict discuss summarize vocabulary support",
                },
                follow_redirects=True,
            )
            assert success_resp.status_code == 200
            success_text = success_resp.get_data(as_text=True)
            assert "Knowledge Context" in success_text or "知识库参考资料" in success_text
            assert title_prefix in success_text

            with sqlite3.connect(DATABASE_PATH) as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM lesson_tasks WHERE course_title=?",
                    (success_title,),
                ).fetchone()
                assert row is not None
                context = json.loads(row["knowledge_context_json"])
                assert context["result_count"] > 0
                assert context["failed"] is False
                assert any(title_prefix in str(item.get("title") or "") for item in context.get("results") or [])

        else:
            # Keep the script informative when the local embedding service is unavailable.
            print("Embedding service unavailable; skipping live RAG success path.")

    _cleanup_prefix(title_prefix)

    print("ROUND_015_OK")


if __name__ == "__main__":
    run()
