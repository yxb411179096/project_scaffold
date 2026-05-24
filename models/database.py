import sqlite3
from contextlib import contextmanager
from datetime import datetime

from config import (
    DATABASE_PATH,
    EXPORT_DOCX_DIR,
    EXPORT_PPTX_DIR,
    KNOWLEDGE_TEXT_DIR,
    KNOWLEDGE_UPLOAD_DIR,
    UPLOAD_DIR,
)


AI_MODEL_PROVIDERS = ("mock", "ollama", "deepseek", "openai")
AGENT_BINDING_MODES = (
    "rule_only",
    "model_first",
    "model_then_fallback_model",
    "model_only",
    "disabled",
)
AGENT_NAMES = (
    "requirement_parser_agent",
    "lesson_design_agent",
    "ppt_outline_agent",
    "slide_content_agent",
    "language_polish_agent",
    "activity_review_agent",
    "layout_planner_agent",
    "json_schema_checker",
    "manuscript_analyzer_agent",
    "page_structure_detector_agent",
    "lesson_structure_extractor_agent",
    "original_page_parser_agent",
    "slide_splitter_agent",
    "content_compressor_agent",
)
AGENT_BINDING_DEFAULTS = {
    "requirement_parser_agent": {
        "mode": "rule_only",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.3,
        "max_tokens": 1024,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "lesson_design_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.35,
        "max_tokens": 1400,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "ppt_outline_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.3,
        "max_tokens": 1800,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "slide_content_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.35,
        "max_tokens": 2200,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "language_polish_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.2,
        "max_tokens": 1600,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "activity_review_agent": {
        "mode": "rule_only",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.3,
        "max_tokens": 1024,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "layout_planner_agent": {
        "mode": "rule_only",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.3,
        "max_tokens": 1024,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "json_schema_checker": {
        "mode": "rule_only",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.1,
        "max_tokens": 512,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "manuscript_analyzer_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.25,
        "max_tokens": 1200,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "page_structure_detector_agent": {
        "mode": "rule_only",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.15,
        "max_tokens": 900,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "lesson_structure_extractor_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.25,
        "max_tokens": 1800,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "original_page_parser_agent": {
        "mode": "rule_only",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.2,
        "max_tokens": 2200,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "slide_splitter_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.25,
        "max_tokens": 2200,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
    "content_compressor_agent": {
        "mode": "model_first",
        "primary_model_config_id": None,
        "fallback_model_config_id": None,
        "timeout_override": None,
        "temperature": 0.2,
        "max_tokens": 1600,
        "json_required": True,
        "fallback_to_rule": True,
        "enabled": True,
    },
}


def ensure_column(conn, table_name, column_name, definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}
    if column_name not in columns:
        try:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        except sqlite3.OperationalError as exc:
            if "duplicate column name" not in str(exc).lower():
                raise


def _seed_agent_bindings(conn):
    existing = {
        row[0]
        for row in conn.execute("SELECT agent_name FROM agent_model_bindings").fetchall()
    }
    for agent_name in AGENT_NAMES:
        if agent_name in existing:
            continue
        defaults = AGENT_BINDING_DEFAULTS[agent_name]
        conn.execute(
            """
            INSERT INTO agent_model_bindings
            (agent_name, mode, primary_model_config_id, fallback_model_config_id, timeout_override, temperature, max_tokens, json_required, fallback_to_rule, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_name,
                defaults["mode"],
                defaults["primary_model_config_id"],
                defaults["fallback_model_config_id"],
                defaults["timeout_override"],
                defaults["temperature"],
                defaults["max_tokens"],
                1 if defaults["json_required"] else 0,
                1 if defaults["fallback_to_rule"] else 0,
                1 if defaults["enabled"] else 0,
                now(),
                now(),
            ),
        )


def _apply_agent_binding_migrations(conn):
    """Adjust new-agent defaults when old rows still match the previous lightweight placeholders."""

    conn.execute(
        """
        UPDATE agent_model_bindings
        SET mode='rule_only', updated_at=?
        WHERE agent_name IN ('page_structure_detector_agent', 'original_page_parser_agent')
          AND mode='model_first'
          AND primary_model_config_id IS NULL
          AND fallback_model_config_id IS NULL
        """,
        (now(),),
    )


def init_db():
    EXPORT_PPTX_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DOCX_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lesson_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_title TEXT NOT NULL,
                grade TEXT,
                textbook TEXT,
                unit TEXT,
                lesson_type TEXT,
                duration INTEGER,
                student_level TEXT,
                style TEXT,
                extra_requirements TEXT,
                status TEXT DEFAULT 'draft',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ppt_slides (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER NOT NULL,
                slide_index INTEGER,
                slide_type TEXT,
                title TEXT,
                visible_content_json TEXT,
                slide_json TEXT,
                teacher_notes TEXT,
                teaching_purpose TEXT,
                estimated_time TEXT,
                interaction_type TEXT,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY(task_id) REFERENCES lesson_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_model_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                base_url TEXT,
                model_name TEXT,
                api_key TEXT,
                timeout INTEGER,
                enabled INTEGER DEFAULT 1,
                is_default INTEGER DEFAULT 0,
                purpose TEXT,
                last_test_status TEXT,
                last_test_message TEXT,
                last_tested_at TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_model_bindings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_name TEXT NOT NULL UNIQUE,
                mode TEXT NOT NULL,
                primary_model_config_id INTEGER,
                fallback_model_config_id INTEGER,
                timeout_override INTEGER,
                temperature REAL,
                max_tokens INTEGER,
                json_required INTEGER DEFAULT 1,
                fallback_to_rule INTEGER DEFAULT 1,
                enabled INTEGER DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY(primary_model_config_id) REFERENCES ai_model_configs(id),
                FOREIGN KEY(fallback_model_config_id) REFERENCES ai_model_configs(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS llm_call_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                agent_name TEXT,
                provider TEXT,
                model_name TEXT,
                status TEXT,
                duration_ms INTEGER,
                error_message TEXT,
                created_at TEXT,
                FOREIGN KEY(task_id) REFERENCES lesson_tasks(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                doc_type TEXT,
                grade TEXT,
                textbook TEXT,
                volume TEXT,
                unit TEXT,
                lesson_type TEXT,
                source_type TEXT,
                file_name TEXT,
                original_file_path TEXT,
                text_file_path TEXT,
                parsed_text TEXT,
                summary TEXT,
                word_count INTEGER DEFAULT 0,
                tags TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                embedding_status TEXT DEFAULT 'not_indexed',
                chunk_count INTEGER DEFAULT 0,
                vector_collection TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )
            """
        )

        ensure_column(conn, "ppt_slides", "slide_json", "TEXT")
        ensure_column(conn, "lesson_tasks", "generation_mode", "TEXT")
        ensure_column(conn, "lesson_tasks", "manuscript_generation_strategy", "TEXT")
        ensure_column(conn, "lesson_tasks", "manuscript_preserve_completion_mode", "TEXT")
        ensure_column(conn, "lesson_tasks", "manuscript_preserve_polish_mode", "TEXT")
        ensure_column(conn, "lesson_tasks", "manuscript_source_name", "TEXT")
        ensure_column(conn, "lesson_tasks", "manuscript_raw_text", "TEXT")
        ensure_column(conn, "lesson_tasks", "manuscript_summary", "TEXT")
        ensure_column(conn, "lesson_tasks", "manuscript_analysis_json", "TEXT")
        ensure_column(conn, "lesson_tasks", "source_word_count", "INTEGER")
        ensure_column(conn, "ai_model_configs", "base_url", "TEXT")
        ensure_column(conn, "ai_model_configs", "model_name", "TEXT")
        ensure_column(conn, "ai_model_configs", "api_key", "TEXT")
        ensure_column(conn, "ai_model_configs", "timeout", "INTEGER")
        ensure_column(conn, "ai_model_configs", "enabled", "INTEGER DEFAULT 1")
        ensure_column(conn, "ai_model_configs", "is_default", "INTEGER DEFAULT 0")
        ensure_column(conn, "ai_model_configs", "purpose", "TEXT")
        ensure_column(conn, "ai_model_configs", "last_test_status", "TEXT")
        ensure_column(conn, "ai_model_configs", "last_test_message", "TEXT")
        ensure_column(conn, "ai_model_configs", "last_tested_at", "TEXT")

        ensure_column(conn, "agent_model_bindings", "mode", "TEXT")
        ensure_column(conn, "agent_model_bindings", "primary_model_config_id", "INTEGER")
        ensure_column(conn, "agent_model_bindings", "fallback_model_config_id", "INTEGER")
        ensure_column(conn, "agent_model_bindings", "timeout_override", "INTEGER")
        ensure_column(conn, "agent_model_bindings", "temperature", "REAL")
        ensure_column(conn, "agent_model_bindings", "max_tokens", "INTEGER")
        ensure_column(conn, "agent_model_bindings", "json_required", "INTEGER DEFAULT 1")
        ensure_column(conn, "agent_model_bindings", "fallback_to_rule", "INTEGER DEFAULT 1")
        ensure_column(conn, "agent_model_bindings", "enabled", "INTEGER DEFAULT 1")

        ensure_column(conn, "llm_call_logs", "task_id", "INTEGER")
        ensure_column(conn, "llm_call_logs", "agent_name", "TEXT")
        ensure_column(conn, "llm_call_logs", "provider", "TEXT")
        ensure_column(conn, "llm_call_logs", "model_name", "TEXT")
        ensure_column(conn, "llm_call_logs", "status", "TEXT")
        ensure_column(conn, "llm_call_logs", "duration_ms", "INTEGER")
        ensure_column(conn, "llm_call_logs", "error_message", "TEXT")
        ensure_column(conn, "knowledge_documents", "title", "TEXT")
        ensure_column(conn, "knowledge_documents", "doc_type", "TEXT")
        ensure_column(conn, "knowledge_documents", "grade", "TEXT")
        ensure_column(conn, "knowledge_documents", "textbook", "TEXT")
        ensure_column(conn, "knowledge_documents", "volume", "TEXT")
        ensure_column(conn, "knowledge_documents", "unit", "TEXT")
        ensure_column(conn, "knowledge_documents", "lesson_type", "TEXT")
        ensure_column(conn, "knowledge_documents", "source_type", "TEXT")
        ensure_column(conn, "knowledge_documents", "file_name", "TEXT")
        ensure_column(conn, "knowledge_documents", "original_file_path", "TEXT")
        ensure_column(conn, "knowledge_documents", "text_file_path", "TEXT")
        ensure_column(conn, "knowledge_documents", "parsed_text", "TEXT")
        ensure_column(conn, "knowledge_documents", "summary", "TEXT")
        ensure_column(conn, "knowledge_documents", "word_count", "INTEGER DEFAULT 0")
        ensure_column(conn, "knowledge_documents", "tags", "TEXT")
        ensure_column(conn, "knowledge_documents", "status", "TEXT DEFAULT 'pending'")
        ensure_column(conn, "knowledge_documents", "error_message", "TEXT")
        ensure_column(conn, "knowledge_documents", "embedding_status", "TEXT DEFAULT 'not_indexed'")
        ensure_column(conn, "knowledge_documents", "chunk_count", "INTEGER DEFAULT 0")
        ensure_column(conn, "knowledge_documents", "vector_collection", "TEXT DEFAULT ''")

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ppt_slides_task_id
            ON ppt_slides(task_id, slide_index)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_ai_model_configs_default
            ON ai_model_configs(enabled, is_default)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_agent_model_bindings_agent_name
            ON agent_model_bindings(agent_name)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_llm_call_logs_task_id
            ON llm_call_logs(task_id, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_created_at
            ON knowledge_documents(created_at DESC, id DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_status
            ON knowledge_documents(status)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_knowledge_documents_doc_type
            ON knowledge_documents(doc_type)
            """
        )

        _seed_agent_bindings(conn)
        _apply_agent_binding_migrations(conn)
        conn.commit()


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _normalize_int(value, default=None, minimum=None, maximum=None):
    if value in (None, ""):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _normalize_float(value, default=None, minimum=None, maximum=None):
    if value in (None, ""):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _normalize_ai_model_row(row):
    if row is None:
        return None
    data = dict(row)
    data["provider"] = str(data.get("provider") or "mock").strip().lower()
    data["name"] = str(data.get("name") or "").strip()
    data["base_url"] = str(data.get("base_url") or "").strip()
    data["model_name"] = str(data.get("model_name") or "").strip()
    data["api_key"] = str(data.get("api_key") or "").strip()
    data["timeout"] = _normalize_int(data.get("timeout"), default=120, minimum=10, maximum=300)
    data["enabled"] = bool(data.get("enabled"))
    data["is_default"] = bool(data.get("is_default"))
    data["purpose"] = str(data.get("purpose") or "").strip()
    data["last_test_status"] = str(data.get("last_test_status") or "").strip()
    data["last_test_message"] = str(data.get("last_test_message") or "").strip()
    data["last_tested_at"] = str(data.get("last_tested_at") or "").strip()
    return data


def _normalize_agent_binding_row(row):
    if row is None:
        return None
    data = dict(row)
    defaults = AGENT_BINDING_DEFAULTS.get(data.get("agent_name"), AGENT_BINDING_DEFAULTS["lesson_design_agent"])
    data["agent_name"] = str(data.get("agent_name") or "").strip()
    data["mode"] = str(data.get("mode") or defaults["mode"]).strip().lower()
    if data["mode"] not in AGENT_BINDING_MODES:
        data["mode"] = defaults["mode"]
    data["primary_model_config_id"] = _normalize_int(data.get("primary_model_config_id"))
    data["fallback_model_config_id"] = _normalize_int(data.get("fallback_model_config_id"))
    data["timeout_override"] = _normalize_int(data.get("timeout_override"), minimum=10, maximum=300)
    data["temperature"] = _normalize_float(data.get("temperature"), default=defaults["temperature"], minimum=0, maximum=2)
    data["max_tokens"] = _normalize_int(data.get("max_tokens"), default=defaults["max_tokens"], minimum=128, maximum=8192)
    data["json_required"] = bool(data.get("json_required"))
    data["fallback_to_rule"] = bool(data.get("fallback_to_rule"))
    data["enabled"] = bool(data.get("enabled"))
    return data


def _normalize_llm_call_log_row(row):
    if row is None:
        return None
    data = dict(row)
    data["task_id"] = _normalize_int(data.get("task_id"))
    data["agent_name"] = str(data.get("agent_name") or "").strip()
    data["provider"] = str(data.get("provider") or "").strip()
    data["model_name"] = str(data.get("model_name") or "").strip()
    data["status"] = str(data.get("status") or "").strip()
    data["duration_ms"] = _normalize_int(data.get("duration_ms"), default=0, minimum=0)
    data["error_message"] = str(data.get("error_message") or "").strip()
    data["created_at"] = str(data.get("created_at") or "").strip()
    return data


def _normalize_knowledge_document_row(row):
    if row is None:
        return None
    data = dict(row)
    data["title"] = str(data.get("title") or "").strip()
    data["doc_type"] = str(data.get("doc_type") or "").strip()
    data["grade"] = str(data.get("grade") or "").strip()
    data["textbook"] = str(data.get("textbook") or "").strip()
    data["volume"] = str(data.get("volume") or "").strip()
    data["unit"] = str(data.get("unit") or "").strip()
    data["lesson_type"] = str(data.get("lesson_type") or "").strip()
    data["source_type"] = str(data.get("source_type") or "").strip()
    data["file_name"] = str(data.get("file_name") or "").strip()
    data["original_file_path"] = str(data.get("original_file_path") or "").strip()
    data["text_file_path"] = str(data.get("text_file_path") or "").strip()
    data["parsed_text"] = str(data.get("parsed_text") or "")
    data["summary"] = str(data.get("summary") or "").strip()
    data["word_count"] = _normalize_int(data.get("word_count"), default=0, minimum=0)
    data["tags"] = str(data.get("tags") or "").strip()
    data["status"] = str(data.get("status") or "pending").strip() or "pending"
    data["error_message"] = str(data.get("error_message") or "").strip()
    data["embedding_status"] = str(data.get("embedding_status") or "not_indexed").strip() or "not_indexed"
    data["chunk_count"] = _normalize_int(data.get("chunk_count"), default=0, minimum=0)
    data["vector_collection"] = str(data.get("vector_collection") or "").strip()
    data["created_at"] = str(data.get("created_at") or "").strip()
    data["updated_at"] = str(data.get("updated_at") or "").strip()
    return data


def list_ai_model_configs():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM ai_model_configs
            ORDER BY is_default DESC, enabled DESC, updated_at DESC, id DESC
            """
        ).fetchall()
    return [_normalize_ai_model_row(row) for row in rows]


def get_ai_model_config(config_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM ai_model_configs WHERE id=?",
            (config_id,),
        ).fetchone()
    return _normalize_ai_model_row(row)


def get_default_ai_model_config():
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM ai_model_configs
            WHERE enabled=1 AND is_default=1
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """
        ).fetchone()
    return _normalize_ai_model_row(row)


def create_ai_model_config(payload):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO ai_model_configs
            (name, provider, base_url, model_name, api_key, timeout, enabled, is_default, purpose, last_test_status, last_test_message, last_tested_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("name"),
                payload.get("provider"),
                payload.get("base_url"),
                payload.get("model_name"),
                payload.get("api_key"),
                payload.get("timeout"),
                1 if payload.get("enabled") else 0,
                1 if payload.get("is_default") else 0,
                payload.get("purpose"),
                payload.get("last_test_status"),
                payload.get("last_test_message"),
                payload.get("last_tested_at"),
                now(),
                now(),
            ),
        )
        config_id = cur.lastrowid
    return get_ai_model_config(config_id)


def update_ai_model_config(config_id, payload):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE ai_model_configs
            SET name=?, provider=?, base_url=?, model_name=?, api_key=?, timeout=?, enabled=?, is_default=?, purpose=?, updated_at=?
            WHERE id=?
            """,
            (
                payload.get("name"),
                payload.get("provider"),
                payload.get("base_url"),
                payload.get("model_name"),
                payload.get("api_key"),
                payload.get("timeout"),
                1 if payload.get("enabled") else 0,
                1 if payload.get("is_default") else 0,
                payload.get("purpose"),
                now(),
                config_id,
            ),
        )
    return get_ai_model_config(config_id)


def delete_ai_model_config(config_id):
    with get_db() as conn:
        conn.execute("DELETE FROM ai_model_configs WHERE id=?", (config_id,))


def set_default_ai_model_config(config_id):
    with get_db() as conn:
        conn.execute("UPDATE ai_model_configs SET is_default=0, updated_at=?", (now(),))
        conn.execute(
            """
            UPDATE ai_model_configs
            SET is_default=1, enabled=1, updated_at=?
            WHERE id=?
            """,
            (now(), config_id),
        )
    return get_ai_model_config(config_id)


def set_ai_model_enabled(config_id, enabled):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE ai_model_configs
            SET enabled=?, is_default=CASE WHEN ?=0 THEN 0 ELSE is_default END, updated_at=?
            WHERE id=?
            """,
            (1 if enabled else 0, 1 if enabled else 0, now(), config_id),
        )
    return get_ai_model_config(config_id)


def update_ai_model_test_result(config_id, status, message):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE ai_model_configs
            SET last_test_status=?, last_test_message=?, last_tested_at=?, updated_at=?
            WHERE id=?
            """,
            (status, message, now(), now(), config_id),
        )
    return get_ai_model_config(config_id)


def clear_ai_model_default_flag(config_id):
    with get_db() as conn:
        conn.execute(
            "UPDATE ai_model_configs SET is_default=0, updated_at=? WHERE id=?",
            (now(), config_id),
        )
    return get_ai_model_config(config_id)


def list_agent_model_bindings():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM agent_model_bindings
            ORDER BY id ASC
            """
        ).fetchall()
    bindings = [_normalize_agent_binding_row(row) for row in rows]
    order_map = {name: index for index, name in enumerate(AGENT_NAMES)}
    return sorted(bindings, key=lambda item: order_map.get(item["agent_name"], 999))


def get_agent_model_binding(agent_name):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM agent_model_bindings WHERE agent_name=?",
            (agent_name,),
        ).fetchone()
    return _normalize_agent_binding_row(row)


def update_agent_model_binding(agent_name, payload):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE agent_model_bindings
            SET mode=?, primary_model_config_id=?, fallback_model_config_id=?, timeout_override=?, temperature=?, max_tokens=?, json_required=?, fallback_to_rule=?, enabled=?, updated_at=?
            WHERE agent_name=?
            """,
            (
                payload.get("mode"),
                payload.get("primary_model_config_id"),
                payload.get("fallback_model_config_id"),
                payload.get("timeout_override"),
                payload.get("temperature"),
                payload.get("max_tokens"),
                1 if payload.get("json_required") else 0,
                1 if payload.get("fallback_to_rule") else 0,
                1 if payload.get("enabled") else 0,
                now(),
                agent_name,
            ),
        )
    return get_agent_model_binding(agent_name)


def create_llm_call_log(task_id, agent_name, provider, model_name, status, duration_ms, error_message=""):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO llm_call_logs
            (task_id, agent_name, provider, model_name, status, duration_ms, error_message, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                agent_name,
                provider,
                model_name,
                status,
                duration_ms,
                error_message,
                now(),
            ),
        )
        log_id = cur.lastrowid
        row = conn.execute("SELECT * FROM llm_call_logs WHERE id=?", (log_id,)).fetchone()
    return _normalize_llm_call_log_row(row)


def list_llm_call_logs(task_id, limit=40):
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM llm_call_logs
            WHERE task_id=?
            ORDER BY id DESC
            LIMIT ?
            """,
            (task_id, limit),
        ).fetchall()
    return [_normalize_llm_call_log_row(row) for row in rows]


def create_knowledge_document(payload):
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO knowledge_documents
            (title, doc_type, grade, textbook, volume, unit, lesson_type, source_type, file_name, original_file_path, text_file_path, parsed_text, summary, word_count, tags, status, error_message, embedding_status, chunk_count, vector_collection, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("title"),
                payload.get("doc_type"),
                payload.get("grade"),
                payload.get("textbook"),
                payload.get("volume"),
                payload.get("unit"),
                payload.get("lesson_type"),
                payload.get("source_type"),
                payload.get("file_name"),
                payload.get("original_file_path"),
                payload.get("text_file_path"),
                payload.get("parsed_text"),
                payload.get("summary"),
                payload.get("word_count") or 0,
                payload.get("tags"),
                payload.get("status") or "pending",
                payload.get("error_message") or "",
                payload.get("embedding_status") or "not_indexed",
                payload.get("chunk_count") or 0,
                payload.get("vector_collection") or "",
                now(),
                now(),
            ),
        )
        doc_id = cur.lastrowid
        row = conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (doc_id,)).fetchone()
    return _normalize_knowledge_document_row(row)


def update_knowledge_document(doc_id, payload):
    with get_db() as conn:
        conn.execute(
            """
            UPDATE knowledge_documents
            SET title=?, doc_type=?, grade=?, textbook=?, volume=?, unit=?, lesson_type=?, source_type=?, file_name=?, original_file_path=?, text_file_path=?, parsed_text=?, summary=?, word_count=?, tags=?, status=?, error_message=?, embedding_status=?, chunk_count=?, vector_collection=?, updated_at=?
            WHERE id=?
            """,
            (
                payload.get("title"),
                payload.get("doc_type"),
                payload.get("grade"),
                payload.get("textbook"),
                payload.get("volume"),
                payload.get("unit"),
                payload.get("lesson_type"),
                payload.get("source_type"),
                payload.get("file_name"),
                payload.get("original_file_path"),
                payload.get("text_file_path"),
                payload.get("parsed_text"),
                payload.get("summary"),
                payload.get("word_count") or 0,
                payload.get("tags"),
                payload.get("status") or "pending",
                payload.get("error_message") or "",
                payload.get("embedding_status") or "not_indexed",
                payload.get("chunk_count") or 0,
                payload.get("vector_collection") or "",
                now(),
                doc_id,
            ),
        )
        row = conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (doc_id,)).fetchone()
    return _normalize_knowledge_document_row(row)


def get_knowledge_document(doc_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (doc_id,)).fetchone()
    return _normalize_knowledge_document_row(row)


def delete_knowledge_document(doc_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM knowledge_documents WHERE id=?", (doc_id,)).fetchone()
        conn.execute("DELETE FROM knowledge_documents WHERE id=?", (doc_id,))
    return _normalize_knowledge_document_row(row)


def query_knowledge_documents(filters=None, limit=50):
    filters = filters or {}
    where = []
    params = []

    keyword = str(filters.get("keyword") or "").strip()
    if keyword:
        where.append("(title LIKE ? OR tags LIKE ? OR summary LIKE ? OR parsed_text LIKE ?)")
        token = f"%{keyword}%"
        params.extend([token, token, token, token])

    for field in ("doc_type", "grade", "textbook", "volume", "unit", "lesson_type", "status"):
        value = str(filters.get(field) or "").strip()
        if value:
            where.append(f"{field}=?")
            params.append(value)

    sql = "SELECT * FROM knowledge_documents"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
    params.append(max(1, int(limit or 50)))

    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_normalize_knowledge_document_row(row) for row in rows]
