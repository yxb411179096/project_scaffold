import sqlite3
import uuid

from app import create_app
from config import DATABASE_PATH
import routes.ppt_routes as ppt_routes
import services.llm_service as llm_service


def run():
    # 1) qwen json instruction
    assert "Return only valid JSON." in llm_service.QWEN_JSON_SYSTEM_INSTRUCTION
    assert "Do not include thinking process." in llm_service.QWEN_JSON_SYSTEM_INSTRUCTION

    # 2) qwen num_predict lower bound
    t, temp, tokens = llm_service._apply_qwen3_runtime_profile(
        "slide_content_agent",
        {"model_name": "qwen2.5:7b"},
        60,
        0.6,
        1024,
    )
    assert t >= 240
    assert 0.2 <= temp <= 0.35
    assert tokens >= 6000

    # 3) knowledge context trimming
    long_context = "header\n\n" + "\n\n".join(
        [f"【知识库参考资料 {i}】\n内容：{'x' * 2000}" for i in range(1, 10)]
    )
    compact = llm_service.trim_knowledge_context_for_prompt(long_context, max_chars=4000)
    assert len(compact) <= 4000
    assert "知识库参考资料" in compact

    # 4) empty response retry and 5) retry fallback behavior
    original_call = llm_service._call_ollama_payload
    state = {"count": 0}

    def _fake_retry(*args, **kwargs):
        state["count"] += 1
        if state["count"] == 1:
            raise llm_service.LLMServiceError("Model returned an empty response.")
        return {"ok": True}, {"prompt_length": 10, "response_length": 10}

    llm_service._call_ollama_payload = _fake_retry
    payload, meta = llm_service._call_ollama_payload_with_retry(
        "lesson_design_agent",
        {"model_name": "qwen2.5:7b", "base_url": "http://127.0.0.1:11434"},
        "sys",
        "user",
        120,
        0.3,
        1024,
        True,
    )
    assert payload["ok"] is True
    assert meta.get("retry_attempted") is True
    assert meta.get("retry_success") is True
    llm_service._call_ollama_payload = original_call

    # 6) JSON extraction robustness
    assert llm_service._extract_first_json_value('{"a":1}')["a"] == 1
    assert llm_service._extract_first_json_value("```json\n{\"a\":2}\n```")["a"] == 2
    assert llm_service._extract_first_json_value("note: ok\n{\"a\":3}\nthanks")["a"] == 3
    assert llm_service._extract_first_json_value("[{\"a\":4}]")[0]["a"] == 4

    # 7) JSON test endpoint
    app = create_app()
    app.config["TESTING"] = True
    name = f"[TEST] Round016 {uuid.uuid4().hex[:6]}"
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            INSERT INTO ai_model_configs
            (name, provider, base_url, model_name, api_key, timeout, enabled, is_default, purpose, created_at, updated_at)
            VALUES (?, 'ollama', 'http://127.0.0.1:11434', 'qwen2.5:7b', '', 60, 1, 0, 'round016', datetime('now'), datetime('now'))
            """,
            (name,),
        )
        row = conn.execute("SELECT id FROM ai_model_configs WHERE name=? ORDER BY id DESC LIMIT 1", (name,)).fetchone()
        config_id = int(row[0])
        conn.commit()

    original_json_test = ppt_routes.call_model_json_test

    def _fake_json_test(_cfg):
        return {
            "ok": True,
            "duration_ms": 123,
            "parsed": {"status": "ok", "model": "qwen2.5:7b", "message": "hello"},
            "error": "",
        }

    ppt_routes.call_model_json_test = _fake_json_test
    with app.test_client() as client:
        response = client.post(f"/settings/ai-models/{config_id}/test-json", follow_redirects=True)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert "JSON测试: 成功" in body
        assert "hello" in body
    ppt_routes.call_model_json_test = original_json_test

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("DELETE FROM ai_model_configs WHERE id=?", (config_id,))
        conn.commit()

    print("ROUND_016_OK")


if __name__ == "__main__":
    run()
