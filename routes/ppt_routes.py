import json
from pathlib import Path
import uuid

from flask import Blueprint, Response, abort, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from models.database import (
    AGENT_BINDING_MODES,
    AI_MODEL_PROVIDERS,
    clear_ai_model_default_flag,
    create_ai_model_config,
    delete_ai_model_config,
    get_agent_model_binding,
    get_ai_model_config,
    get_db,
    list_ai_model_configs,
    list_agent_model_bindings,
    list_llm_call_logs,
    now,
    set_ai_model_enabled,
    set_default_ai_model_config,
    update_agent_model_binding,
    update_ai_model_config,
    update_ai_model_test_result,
)
from config import MANUSCRIPT_UPLOAD_DIR, MAX_MANUSCRIPT_FILE_SIZE
from services.document_parse_service import (
    DocumentParseError,
    SUPPORTED_MANUSCRIPT_EXTENSIONS,
    count_source_words,
    extract_text_from_file,
)
from services.agents import generate_rule_page_structure_detection
from services.docx_export_service import export_docx
from services.llm_service import (
    describe_runtime_model,
    generate_slides,
    generate_slides_from_manuscript,
    get_generation_trace,
    regenerate_slide,
    test_model_connection,
)
from services.ppt_render_service import export_pptx

ppt_bp = Blueprint("ppt", __name__)
LESSON_TYPE_OPTIONS = [
    "Reading",
    "Grammar",
    "Writing",
    "Listening and Speaking",
    "Revision",
]
MANUSCRIPT_LESSON_TYPE_OPTIONS = LESSON_TYPE_OPTIONS + ["Other"]
STUDENT_LEVEL_OPTIONS = ["基础薄弱", "中等", "较好"]
STYLE_OPTIONS = ["常规课", "公开课", "复习课"]
MANUSCRIPT_GENERATION_MODES = {
    "text": "manuscript_text",
    "file": "manuscript_file",
    "mixed": "manuscript_mixed",
}
MANUSCRIPT_STRATEGY_OPTIONS = (
    ("preserve_original_pages", "严格按原文页结构生成"),
    ("ai_restructure", "AI 优化重构生成"),
)
PRESERVE_COMPLETION_OPTIONS = (
    ("preserve_exact_pages", "仅按原文页数生成"),
    ("preserve_and_append_closure", "按原文生成，并自动补充 Summary / Homework / Blackboard Design"),
)
PRESERVE_POLISH_OPTIONS = (
    ("skip", "跳过英文润色，直接保留原文表述"),
    ("follow_agent_strategy", "按 Agent 策略执行英文润色"),
)

SLIDE_FIELDS = (
    "slide_index",
    "slide_type",
    "title",
    "visible_content",
    "teacher_notes",
    "teaching_purpose",
    "estimated_time",
    "interaction_type",
)

OPTIONAL_SLIDE_FIELDS = (
    "warning",
    "layout_plan",
    "image_suggestion",
    "key_sentence",
    "useful_expressions",
    "possible_answers",
    "chinese_hint",
)
AI_MODEL_STATUS_LABELS = {
    "available": "可用",
    "unavailable": "不可用",
    "untested": "未测试",
}
AGENT_MODE_LABELS = {
    "rule_only": "仅规则",
    "model_first": "主模型优先",
    "model_then_fallback_model": "主模型后备模型",
    "model_only": "仅模型",
    "disabled": "禁用",
}
LLM_LOG_STATUS_LABELS = {
    "success": "成功",
    "fallback_rule": "回退规则",
    "fallback_model": "备用模型成功",
    "failed": "失败",
    "skipped_rule_only": "规则执行",
}
AGENT_DISPLAY_NAMES = {
    "requirement_parser_agent": "Requirement Parser Agent",
    "lesson_design_agent": "Lesson Design Agent",
    "ppt_outline_agent": "PPT Outline Agent",
    "slide_content_agent": "Slide Content Agent",
    "language_polish_agent": "Language Polish Agent",
    "activity_review_agent": "Activity Review Agent",
    "layout_planner_agent": "Layout Planner Agent",
    "json_schema_checker": "JSON Schema Checker",
    "manuscript_analyzer_agent": "Manuscript Analyzer Agent",
    "lesson_structure_extractor_agent": "Lesson Structure Extractor Agent",
    "slide_splitter_agent": "Slide Splitter Agent",
    "content_compressor_agent": "Content Compressor Agent",
    "page_structure_detector_agent": "Page Structure Detector Agent",
    "original_page_parser_agent": "Original Page Parser Agent",
}
MANUSCRIPT_AGENT_NAMES = {
    "manuscript_analyzer_agent",
    "page_structure_detector_agent",
    "lesson_structure_extractor_agent",
    "original_page_parser_agent",
    "slide_splitter_agent",
    "content_compressor_agent",
}


@ppt_bp.app_errorhandler(413)
def manuscript_file_too_large(_error):
    flash("上传文件超过 20MB 限制，请缩小文件后重试。", "danger")
    return redirect(request.referrer or url_for("ppt.from_manuscript"))


def parse_visible_content(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def parse_short_text(value):
    return str(value or "").strip()


def build_slide_payload(source):
    payload = {field: source.get(field) for field in SLIDE_FIELDS}
    payload["slide_index"] = int(payload.get("slide_index") or 1)
    payload["slide_type"] = payload.get("slide_type") or "summary"
    payload["title"] = payload.get("title") or "Untitled Slide"
    payload["visible_content"] = parse_visible_content(payload.get("visible_content"))
    payload["teacher_notes"] = payload.get("teacher_notes") or ""
    payload["teaching_purpose"] = payload.get("teaching_purpose") or ""
    payload["estimated_time"] = payload.get("estimated_time") or ""
    payload["interaction_type"] = payload.get("interaction_type") or ""
    for field in OPTIONAL_SLIDE_FIELDS:
        if source.get(field) is not None:
            if field in {"useful_expressions", "possible_answers"}:
                payload[field] = parse_visible_content(source.get(field))
            elif field == "layout_plan":
                payload[field] = source.get(field) if isinstance(source.get(field), dict) else {}
            else:
                payload[field] = parse_short_text(source.get(field))
    return payload


def insert_slide(conn, task_id, slide):
    payload = build_slide_payload(slide)
    conn.execute(
        """
        INSERT INTO ppt_slides
        (task_id, slide_index, slide_type, title, visible_content_json, slide_json, teacher_notes, teaching_purpose, estimated_time, interaction_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            payload["slide_index"],
            payload["slide_type"],
            payload["title"],
            json.dumps(payload["visible_content"], ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
            payload["teacher_notes"],
            payload["teaching_purpose"],
            payload["estimated_time"],
            payload["interaction_type"],
            now(),
            now(),
        ),
    )


def replace_task_slides(conn, task_id, slides):
    conn.execute("DELETE FROM ppt_slides WHERE task_id=?", (task_id,))
    for slide in slides:
        insert_slide(conn, task_id, slide)


def update_task_timestamp(conn, task_id):
    conn.execute(
        "UPDATE lesson_tasks SET updated_at=? WHERE id=?",
        (now(), task_id),
    )


def update_slide(conn, slide_id, slide):
    payload = build_slide_payload(slide)
    conn.execute(
        """
        UPDATE ppt_slides
        SET slide_index=?, slide_type=?, title=?, visible_content_json=?, slide_json=?, teacher_notes=?, teaching_purpose=?, estimated_time=?, interaction_type=?, updated_at=?
        WHERE id=?
        """,
        (
            payload["slide_index"],
            payload["slide_type"],
            payload["title"],
            json.dumps(payload["visible_content"], ensure_ascii=False),
            json.dumps(payload, ensure_ascii=False),
            payload["teacher_notes"],
            payload["teaching_purpose"],
            payload["estimated_time"],
            payload["interaction_type"],
            now(),
            slide_id,
        ),
    )


def get_slide_by_id(slides, slide_id):
    if not slides:
        return None
    if slide_id is None:
        return slides[0]
    for slide in slides:
        if slide["id"] == slide_id:
            return slide
    return slides[0]


def load_task_and_slides(task_id):
    with get_db() as conn:
        task_row = conn.execute("SELECT * FROM lesson_tasks WHERE id=?", (task_id,)).fetchone()
        if task_row is None:
            abort(404)

        slide_rows = conn.execute(
            "SELECT * FROM ppt_slides WHERE task_id=? ORDER BY slide_index, id",
            (task_id,),
        ).fetchall()

    task = dict(task_row)
    slides = []
    for row in slide_rows:
        slide = dict(row)
        payload = None
        if slide.get("slide_json"):
            try:
                payload = json.loads(slide["slide_json"])
            except json.JSONDecodeError:
                payload = None
        if payload is None:
            payload = {
                "slide_index": slide.get("slide_index"),
                "slide_type": slide.get("slide_type"),
                "title": slide.get("title"),
                "visible_content": json.loads(slide.get("visible_content_json") or "[]"),
                "teacher_notes": slide.get("teacher_notes"),
                "teaching_purpose": slide.get("teaching_purpose"),
                "estimated_time": slide.get("estimated_time"),
                "interaction_type": slide.get("interaction_type"),
            }
        normalized = build_slide_payload(payload)
        normalized["id"] = slide["id"]
        normalized["task_id"] = slide["task_id"]
        slides.append(normalized)
    return task, slides


def build_slide_from_form(form, current_slide):
    return {
        "slide_index": current_slide["slide_index"],
        "slide_type": current_slide["slide_type"],
        "title": form.get("title"),
        "visible_content": parse_visible_content(form.get("visible_content")),
        "teacher_notes": form.get("teacher_notes"),
        "teaching_purpose": form.get("teaching_purpose"),
        "estimated_time": form.get("estimated_time"),
        "interaction_type": form.get("interaction_type"),
        "warning": current_slide.get("warning"),
        "layout_plan": current_slide.get("layout_plan"),
        "image_suggestion": form.get("image_suggestion") or current_slide.get("image_suggestion"),
        "key_sentence": form.get("key_sentence") or current_slide.get("key_sentence"),
        "useful_expressions": parse_visible_content(form.get("useful_expressions")) or current_slide.get("useful_expressions"),
        "possible_answers": parse_visible_content(form.get("possible_answers")) or current_slide.get("possible_answers"),
        "chinese_hint": form.get("chinese_hint") or current_slide.get("chinese_hint"),
    }


def generation_mode_label():
    trace = get_generation_trace()
    mode = trace.get("mode") or "mock"
    labels = {
        "mock": "mock",
        "ollama": "ollama",
        "fallback": "fallback",
    }
    return labels.get(mode, mode)


def mask_api_key(value):
    secret = str(value or "").strip()
    if not secret:
        return ""
    if len(secret) <= 8:
        return "****"
    return f"{secret[:3]}-****{secret[-4:]}"


def blank_ai_model_config():
    return {
        "id": None,
        "name": "",
        "provider": "ollama",
        "base_url": "",
        "model_name": "",
        "api_key": "",
        "timeout": 120,
        "enabled": True,
        "is_default": False,
        "purpose": "",
        "last_test_status": "",
        "last_test_message": "",
        "last_tested_at": "",
    }


def build_ai_model_payload(form, existing=None):
    existing = existing or {}
    provider = str(form.get("provider") or "mock").strip().lower()
    if provider not in AI_MODEL_PROVIDERS:
        provider = "mock"

    api_key = str(form.get("api_key") or "").strip()
    if not api_key and existing.get("api_key"):
        api_key = existing["api_key"]

    try:
        timeout = int(form.get("timeout") or existing.get("timeout") or 120)
    except (TypeError, ValueError):
        timeout = 120
    timeout = max(10, min(timeout, 300))

    return {
        "name": str(form.get("name") or "").strip() or f"{provider} config",
        "provider": provider,
        "base_url": str(form.get("base_url") or "").strip().rstrip("/"),
        "model_name": str(form.get("model_name") or "").strip(),
        "api_key": api_key,
        "timeout": timeout,
        "enabled": form.get("enabled") == "on",
        "is_default": form.get("is_default") == "on",
        "purpose": str(form.get("purpose") or "").strip(),
        "last_test_status": existing.get("last_test_status") or "",
        "last_test_message": existing.get("last_test_message") or "",
        "last_tested_at": existing.get("last_tested_at") or "",
    }


def resolve_ai_model_status(config):
    status = config.get("last_test_status") or ""
    if config.get("provider") == "mock" and not status:
        status = "available"
    if not status:
        status = "untested"
    return status


def agent_display_name(agent_name):
    return AGENT_DISPLAY_NAMES.get(agent_name, str(agent_name or "").replace("_", " ").title())


def model_option_label(config):
    if not config:
        return "—"
    provider = config.get("provider") or "mock"
    model_name = config.get("model_name") or provider
    return f"{config.get('name')} · {provider} · {model_name}"


def _optional_int(value, minimum=None, maximum=None):
    if value in (None, ""):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _optional_float(value, minimum=None, maximum=None):
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if minimum is not None:
        number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def build_agent_binding_payload(form, existing):
    mode = str(form.get("mode") or existing.get("mode") or "rule_only").strip().lower()
    if mode not in AGENT_BINDING_MODES:
        mode = existing.get("mode") or "rule_only"

    return {
        "mode": mode,
        "primary_model_config_id": _optional_int(form.get("primary_model_config_id")),
        "fallback_model_config_id": _optional_int(form.get("fallback_model_config_id")),
        "timeout_override": _optional_int(form.get("timeout_override"), minimum=10, maximum=300),
        "temperature": _optional_float(form.get("temperature"), minimum=0, maximum=2),
        "max_tokens": _optional_int(form.get("max_tokens"), minimum=128, maximum=8192),
        "json_required": form.get("json_required") == "on",
        "fallback_to_rule": form.get("fallback_to_rule") == "on",
        "enabled": form.get("enabled") == "on",
    }


def blank_manuscript_form():
    return {
        "course_title": "",
        "grade": "高一",
        "textbook": "人教版",
        "unit": "",
        "lesson_type": "Reading",
        "student_level": "中等",
        "duration": "45",
        "style": "常规课",
        "manuscript_generation_strategy": "ai_restructure",
        "manuscript_preserve_completion_mode": "preserve_exact_pages",
        "manuscript_preserve_polish_mode": "skip",
        "manuscript_text": "",
        "extra_requirements": "",
    }


def is_manuscript_task(task):
    return str((task or {}).get("generation_mode") or "").startswith("manuscript")


def parse_json_text(value, fallback=None):
    try:
        return json.loads(value) if value else fallback
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def build_manuscript_preview(task):
    analysis = parse_json_text(task.get("manuscript_analysis_json"), fallback={}) or {}
    preview = {
        "manuscript_type": str(analysis.get("manuscript_type") or "—").strip() or "—",
        "summary": str(analysis.get("summary") or task.get("manuscript_summary") or "—").strip() or "—",
        "detected_sections": list(analysis.get("detected_sections") or analysis.get("key_sections") or []),
        "missing_sections": list(analysis.get("missing_sections") or []),
        "recommended_generation_strategy": str(
            analysis.get("recommended_generation_strategy") or analysis.get("organization_suggestion") or "—"
        ).strip() or "—",
        "organization_suggestion": str(analysis.get("organization_suggestion") or "").strip(),
        "source_word_count": int(task.get("source_word_count") or 0),
        "content_density": str(analysis.get("content_density") or "").strip(),
        "manuscript_generation_strategy": str(task.get("manuscript_generation_strategy") or "ai_restructure").strip(),
        "manuscript_preserve_completion_mode": str(
            task.get("manuscript_preserve_completion_mode") or "preserve_exact_pages"
        ).strip(),
        "manuscript_preserve_polish_mode": str(
            task.get("manuscript_preserve_polish_mode") or "skip"
        ).strip(),
    }
    return preview, analysis


def persist_manuscript_result(conn, task_id, slides, result, fallback_lesson_type):
    manuscript_analysis = result.get("manuscript_analysis") or {}
    effective_strategy = str(
        result.get("lesson_request", {}).get("manuscript_generation_strategy")
        or "ai_restructure"
    ).strip()
    effective_lesson_type = fallback_lesson_type
    if effective_lesson_type == "Other":
        effective_lesson_type = manuscript_analysis.get("detected_lesson_type") or "Reading"

    replace_task_slides(conn, task_id, slides)
    conn.execute(
        """
        UPDATE lesson_tasks
        SET lesson_type=?, manuscript_generation_strategy=?, manuscript_summary=?, manuscript_analysis_json=?, updated_at=?
        WHERE id=?
        """,
        (
            effective_lesson_type,
            effective_strategy,
            manuscript_analysis.get("summary") or "",
            json.dumps(manuscript_analysis, ensure_ascii=False),
            now(),
            task_id,
        ),
    )


def _save_uploaded_manuscript(uploaded_file):
    MANUSCRIPT_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    original_name = secure_filename(uploaded_file.filename or "")
    suffix = Path(original_name).suffix.lower()
    if suffix not in SUPPORTED_MANUSCRIPT_EXTENSIONS:
        raise DocumentParseError(f"不支持的文件格式：{suffix or 'unknown'}")

    uploaded_file.stream.seek(0, 2)
    file_size = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)
    if file_size > MAX_MANUSCRIPT_FILE_SIZE:
        raise DocumentParseError("上传文件超过 20MB 限制。")

    target_name = f"{uuid.uuid4().hex}_{original_name or 'manuscript.txt'}"
    target_path = MANUSCRIPT_UPLOAD_DIR / target_name
    uploaded_file.save(target_path)
    return target_path, original_name


@ppt_bp.route("/")
def index():
    with get_db() as conn:
        stats = conn.execute(
            """
            SELECT COUNT(*) AS task_count,
                   COALESCE(SUM(duration), 0) AS total_minutes
            FROM lesson_tasks
            WHERE course_title NOT LIKE '[TEST]%'
            """
        ).fetchone()
        recent_tasks = conn.execute(
            """
            SELECT id, course_title, lesson_type, updated_at
            FROM lesson_tasks
            WHERE course_title NOT LIKE '[TEST]%'
            ORDER BY id DESC
            LIMIT 5
            """
        ).fetchall()
    return render_template("index.html", stats=stats, recent_tasks=recent_tasks)


@ppt_bp.route("/favicon.ico")
def favicon():
    return Response(status=204)


@ppt_bp.route("/ppt/new", methods=["GET", "POST"])
def new_task():
    if request.method == "POST":
        form = request.form.to_dict()
        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO lesson_tasks
                (course_title, grade, textbook, unit, lesson_type, duration, student_level, style, extra_requirements, generation_mode, manuscript_generation_strategy, manuscript_preserve_completion_mode, manuscript_preserve_polish_mode, manuscript_source_name, manuscript_raw_text, manuscript_summary, manuscript_analysis_json, source_word_count, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form.get("course_title"),
                    form.get("grade"),
                    form.get("textbook"),
                    form.get("unit"),
                    form.get("lesson_type"),
                    int(form.get("duration") or 45),
                    form.get("student_level"),
                    form.get("style"),
                    form.get("extra_requirements"),
                    "ai_generate",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    0,
                    "generated",
                    now(),
                    now(),
                ),
            )
            task_id = cur.lastrowid

        task = dict(form)
        task["id"] = task_id
        slides = generate_slides(task)
        if not slides:
            with get_db() as conn:
                conn.execute("DELETE FROM ppt_slides WHERE task_id=?", (task_id,))
                conn.execute("DELETE FROM lesson_tasks WHERE id=?", (task_id,))
            flash("课件生成失败：没有得到有效幻灯片，请检查模型配置后重试。", "danger")
            return redirect(url_for("ppt.new_task"))

        with get_db() as conn:
            replace_task_slides(conn, task_id, slides)

        flash(f"课件任务已创建，已生成结构化 slide 内容。当前生成方式: {generation_mode_label()}")
        return redirect(url_for("ppt.edit_task", task_id=task_id))
    return render_template(
        "new_task.html",
        lesson_type_options=LESSON_TYPE_OPTIONS,
        student_level_options=STUDENT_LEVEL_OPTIONS,
        style_options=STYLE_OPTIONS,
    )


@ppt_bp.route("/ppt/from-manuscript", methods=["GET", "POST"])
def from_manuscript():
    form_data = blank_manuscript_form()

    if request.method == "POST":
        form_data.update(request.form.to_dict())
        manuscript_text = str(request.form.get("manuscript_text") or "").strip()
        uploaded_file = request.files.get("manuscript_file")
        file_text = ""
        source_name = ""

        if not manuscript_text and (uploaded_file is None or not uploaded_file.filename):
            flash("请粘贴文案内容或上传一个文档文件。", "warning")
            return render_template(
                "from_manuscript.html",
                form_data=form_data,
                lesson_type_options=MANUSCRIPT_LESSON_TYPE_OPTIONS,
                student_level_options=STUDENT_LEVEL_OPTIONS,
                style_options=STYLE_OPTIONS,
                manuscript_strategy_options=MANUSCRIPT_STRATEGY_OPTIONS,
                preserve_completion_options=PRESERVE_COMPLETION_OPTIONS,
                preserve_polish_options=PRESERVE_POLISH_OPTIONS,
            )

        if uploaded_file and uploaded_file.filename:
            try:
                saved_path, source_name = _save_uploaded_manuscript(uploaded_file)
                file_text = extract_text_from_file(saved_path, source_name)
            except DocumentParseError:
                flash("文案解析失败，请检查文件格式或粘贴文本内容。", "danger")
                return render_template(
                    "from_manuscript.html",
                    form_data=form_data,
                    lesson_type_options=MANUSCRIPT_LESSON_TYPE_OPTIONS,
                    student_level_options=STUDENT_LEVEL_OPTIONS,
                    style_options=STYLE_OPTIONS,
                    manuscript_strategy_options=MANUSCRIPT_STRATEGY_OPTIONS,
                    preserve_completion_options=PRESERVE_COMPLETION_OPTIONS,
                    preserve_polish_options=PRESERVE_POLISH_OPTIONS,
                )

        combined_text = "\n\n".join(part for part in [file_text, manuscript_text] if str(part).strip()).strip()
        if not combined_text:
            flash("文案解析失败，请检查文件格式或粘贴文本内容。", "danger")
            return render_template(
                "from_manuscript.html",
                form_data=form_data,
                lesson_type_options=MANUSCRIPT_LESSON_TYPE_OPTIONS,
                student_level_options=STUDENT_LEVEL_OPTIONS,
                style_options=STYLE_OPTIONS,
                manuscript_strategy_options=MANUSCRIPT_STRATEGY_OPTIONS,
                preserve_completion_options=PRESERVE_COMPLETION_OPTIONS,
                preserve_polish_options=PRESERVE_POLISH_OPTIONS,
            )

        generation_mode = (
            MANUSCRIPT_GENERATION_MODES["mixed"]
            if file_text and manuscript_text
            else MANUSCRIPT_GENERATION_MODES["file"]
            if file_text
            else MANUSCRIPT_GENERATION_MODES["text"]
        )
        selected_strategy = str(form_data.get("manuscript_generation_strategy") or "ai_restructure").strip()
        if selected_strategy not in {value for value, _label in MANUSCRIPT_STRATEGY_OPTIONS}:
            selected_strategy = "ai_restructure"
        selected_completion_mode = str(
            form_data.get("manuscript_preserve_completion_mode") or "preserve_exact_pages"
        ).strip()
        if selected_completion_mode not in {value for value, _label in PRESERVE_COMPLETION_OPTIONS}:
            selected_completion_mode = "preserve_exact_pages"
        selected_polish_mode = str(
            form_data.get("manuscript_preserve_polish_mode") or "skip"
        ).strip()
        if selected_polish_mode not in {value for value, _label in PRESERVE_POLISH_OPTIONS}:
            selected_polish_mode = "skip"
        user_selected_strategy = str(request.form.get("manuscript_generation_strategy_user_selected") or "").strip() == "1"
        if not user_selected_strategy:
            auto_detection = generate_rule_page_structure_detection(combined_text)
            selected_strategy = auto_detection.get("recommended_strategy") or selected_strategy
        form_data["manuscript_generation_strategy"] = selected_strategy
        form_data["manuscript_preserve_completion_mode"] = selected_completion_mode
        form_data["manuscript_preserve_polish_mode"] = selected_polish_mode
        source_word_count = count_source_words(combined_text)
        if len("".join(combined_text.split())) < 100:
            flash("文案内容较短，系统将自动补充基础教学流程。", "warning")

        with get_db() as conn:
            cur = conn.execute(
                """
                INSERT INTO lesson_tasks
                (course_title, grade, textbook, unit, lesson_type, duration, student_level, style, extra_requirements, generation_mode, manuscript_generation_strategy, manuscript_preserve_completion_mode, manuscript_preserve_polish_mode, manuscript_source_name, manuscript_raw_text, manuscript_summary, manuscript_analysis_json, source_word_count, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    form_data.get("course_title") or "文案转 PPT 课件",
                    form_data.get("grade"),
                    form_data.get("textbook"),
                    form_data.get("unit"),
                    form_data.get("lesson_type"),
                    int(form_data.get("duration") or 45),
                    form_data.get("student_level"),
                    form_data.get("style"),
                    form_data.get("extra_requirements"),
                    generation_mode,
                    selected_strategy,
                    selected_completion_mode,
                    selected_polish_mode,
                    source_name,
                    combined_text,
                    "",
                    "",
                    source_word_count,
                    "generated",
                    now(),
                    now(),
                ),
            )
            task_id = cur.lastrowid

        task = dict(form_data)
        task["id"] = task_id
        task["generation_mode"] = generation_mode
        task["manuscript_generation_strategy"] = selected_strategy
        task["manuscript_preserve_completion_mode"] = selected_completion_mode
        task["manuscript_preserve_polish_mode"] = selected_polish_mode
        task["manuscript_source_name"] = source_name
        task["manuscript_raw_text"] = combined_text
        task["manuscript_analysis_json"] = ""
        task["source_word_count"] = source_word_count

        result = generate_slides_from_manuscript(task, combined_text)
        slides = result.get("ppt_json") or []
        if not slides:
            with get_db() as conn:
                conn.execute("DELETE FROM ppt_slides WHERE task_id=?", (task_id,))
                conn.execute("DELETE FROM lesson_tasks WHERE id=?", (task_id,))
            flash("文案转 PPT 失败：没有生成有效幻灯片。", "danger")
            return render_template(
                "from_manuscript.html",
                form_data=form_data,
                lesson_type_options=MANUSCRIPT_LESSON_TYPE_OPTIONS,
                student_level_options=STUDENT_LEVEL_OPTIONS,
                style_options=STYLE_OPTIONS,
                manuscript_strategy_options=MANUSCRIPT_STRATEGY_OPTIONS,
                preserve_completion_options=PRESERVE_COMPLETION_OPTIONS,
                preserve_polish_options=PRESERVE_POLISH_OPTIONS,
            )

        with get_db() as conn:
            persist_manuscript_result(conn, task_id, slides, result, form_data.get("lesson_type"))

        flash(f"文案已转换为结构化课件。当前生成方式: {generation_mode_label()}")
        return redirect(url_for("ppt.edit_task", task_id=task_id))

    return render_template(
        "from_manuscript.html",
        form_data=form_data,
        lesson_type_options=MANUSCRIPT_LESSON_TYPE_OPTIONS,
        student_level_options=STUDENT_LEVEL_OPTIONS,
        style_options=STYLE_OPTIONS,
        manuscript_strategy_options=MANUSCRIPT_STRATEGY_OPTIONS,
        preserve_completion_options=PRESERVE_COMPLETION_OPTIONS,
        preserve_polish_options=PRESERVE_POLISH_OPTIONS,
    )


@ppt_bp.route("/ppt/tasks")
def tasks():
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT lesson_tasks.*, COUNT(ppt_slides.id) AS slide_count
            FROM lesson_tasks
            LEFT JOIN ppt_slides ON ppt_slides.task_id = lesson_tasks.id
            WHERE lesson_tasks.course_title NOT LIKE '[TEST]%'
            GROUP BY lesson_tasks.id
            ORDER BY lesson_tasks.id DESC
            """
        ).fetchall()
    return render_template("tasks.html", tasks=rows)


@ppt_bp.route("/ppt/task/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    task, slides = load_task_and_slides(task_id)

    if request.method == "POST":
        action = request.form.get("action", "save")
        if action in {"regenerate_all", "reanalyze_manuscript"}:
            if is_manuscript_task(task):
                manuscript_text = str(task.get("manuscript_raw_text") or "").strip()
                if not manuscript_text:
                    flash("当前文案任务缺少原始文本，无法重新分析。", "danger")
                    return redirect(url_for("ppt.edit_task", task_id=task_id))

                result = generate_slides_from_manuscript(task, manuscript_text)
                regenerated_slides = result.get("ppt_json") or []
                if not regenerated_slides:
                    flash("文案重新分析失败：没有得到有效幻灯片，请检查文案内容后重试。", "danger")
                    return redirect(url_for("ppt.edit_task", task_id=task_id))

                with get_db() as conn:
                    persist_manuscript_result(
                        conn,
                        task_id,
                        regenerated_slides,
                        result,
                        task.get("lesson_type"),
                    )
                flash_text = "已重新分析文案并生成课件。" if action == "reanalyze_manuscript" else "已重新生成整套课件。"
                flash(f"{flash_text} 当前生成方式: {generation_mode_label()}")
                return redirect(url_for("ppt.edit_task", task_id=task_id))

            regenerated_slides = generate_slides(task)
            if not regenerated_slides:
                flash("整套课件重新生成失败：没有得到有效幻灯片，请检查模型或稍后重试。", "danger")
                return redirect(url_for("ppt.edit_task", task_id=task_id))

            with get_db() as conn:
                replace_task_slides(conn, task_id, regenerated_slides)
                update_task_timestamp(conn, task_id)
            flash(f"已重新生成整套课件。当前生成方式: {generation_mode_label()}")
            return redirect(url_for("ppt.edit_task", task_id=task_id))

        slide_id = request.form.get("slide_id", type=int)
        current_slide = get_slide_by_id(slides, slide_id)
        if current_slide is None:
            flash("当前课件没有有效幻灯片，请先重新生成整套课件。", "warning")
            return redirect(url_for("ppt.edit_task", task_id=task_id))

        if action == "regenerate":
            if is_manuscript_task(task):
                task["_all_slides"] = slides
            refreshed_slide = regenerate_slide(task, current_slide)
            with get_db() as conn:
                update_slide(conn, current_slide["id"], refreshed_slide)
                update_task_timestamp(conn, task_id)
            flash(f"已重新生成当前页面。当前生成方式: {generation_mode_label()}")
        else:
            with get_db() as conn:
                updated_slide = build_slide_from_form(request.form, current_slide)
                update_slide(conn, current_slide["id"], updated_slide)
                update_task_timestamp(conn, task_id)
                flash("已保存当前页面。")

        return redirect(url_for("ppt.edit_task", task_id=task_id, slide_id=current_slide["id"]))

    selected_slide = get_slide_by_id(slides, request.args.get("slide_id", type=int))
    slide_json_preview = json.dumps(slides, ensure_ascii=False, indent=2)
    manuscript_preview, manuscript_analysis = build_manuscript_preview(task)
    llm_call_logs = list(reversed(list_llm_call_logs(task_id, limit=60)))
    for log in llm_call_logs:
        log["agent_label"] = agent_display_name(log.get("agent_name"))
        log["status_label"] = LLM_LOG_STATUS_LABELS.get(log.get("status"), log.get("status") or "—")
        log["is_fallback"] = log.get("status") in {"fallback_rule", "fallback_model"}
        log["is_manuscript_agent"] = log.get("agent_name") in MANUSCRIPT_AGENT_NAMES
    return render_template(
        "edit_task.html",
        task=task,
        slides=slides,
        has_slides=bool(slides),
        is_manuscript_task=is_manuscript_task(task),
        manuscript_preview=manuscript_preview,
        manuscript_analysis=manuscript_analysis,
        selected_slide=selected_slide,
        slide_json_preview=slide_json_preview,
        llm_call_logs=llm_call_logs,
    )


@ppt_bp.route("/ppt/task/<int:task_id>/export_pptx")
def export_task_pptx(task_id):
    task, slides = load_task_and_slides(task_id)
    if not slides:
        flash("当前课件没有有效幻灯片，请先重新生成整套课件。", "warning")
        return redirect(url_for("ppt.edit_task", task_id=task_id))
    path = export_pptx(task, slides)
    return send_file(path, as_attachment=True)


@ppt_bp.route("/ppt/task/<int:task_id>/export_docx")
def export_task_docx(task_id):
    task, slides = load_task_and_slides(task_id)
    if not slides:
        flash("当前课件没有有效幻灯片，请先重新生成整套课件。", "warning")
        return redirect(url_for("ppt.edit_task", task_id=task_id))
    path = export_docx(task, slides)
    return send_file(path, as_attachment=True)


@ppt_bp.route("/settings/ai-models")
def ai_models_settings():
    configs = list_ai_model_configs()
    edit_id = request.args.get("edit_id", type=int)
    editing_config = get_ai_model_config(edit_id) if edit_id else None
    editing_config = editing_config or blank_ai_model_config()
    runtime_model = describe_runtime_model()

    for config in configs:
        config["api_key_masked"] = mask_api_key(config.get("api_key"))
        config["status"] = resolve_ai_model_status(config)
        config["status_label"] = AI_MODEL_STATUS_LABELS.get(config["status"], "未测试")

    editing_config["api_key_masked"] = mask_api_key(editing_config.get("api_key"))

    return render_template(
        "ai_models.html",
        configs=configs,
        editing_config=editing_config,
        runtime_model=runtime_model,
        provider_options=AI_MODEL_PROVIDERS,
    )


@ppt_bp.route("/settings/agent-bindings")
def agent_bindings_settings():
    bindings = list_agent_model_bindings()
    model_configs = list_ai_model_configs()
    model_map = {config["id"]: config for config in model_configs}

    for binding in bindings:
        binding["agent_label"] = agent_display_name(binding.get("agent_name"))
        binding["mode_label"] = AGENT_MODE_LABELS.get(binding.get("mode"), binding.get("mode"))
        binding["primary_model_label"] = (
            model_option_label(model_map.get(binding.get("primary_model_config_id")))
            if binding.get("primary_model_config_id")
            else "跟随系统默认模型"
        )
        binding["fallback_model_label"] = (
            model_option_label(model_map.get(binding.get("fallback_model_config_id")))
            if binding.get("fallback_model_config_id")
            else "无备用模型"
        )

    return render_template(
        "agent_bindings.html",
        bindings=bindings,
        model_configs=model_configs,
        mode_options=AGENT_BINDING_MODES,
        mode_labels=AGENT_MODE_LABELS,
    )


@ppt_bp.route("/settings/agent-bindings/<agent_name>/update", methods=["POST"])
def update_agent_binding_settings(agent_name):
    existing = get_agent_model_binding(agent_name)
    if existing is None:
        abort(404)

    payload = build_agent_binding_payload(request.form, existing)
    updated = update_agent_model_binding(agent_name, payload)
    flash(f"已更新 Agent 策略：{agent_display_name(updated['agent_name'])}")
    return redirect(url_for("ppt.agent_bindings_settings"))


@ppt_bp.route("/settings/ai-models/create", methods=["POST"])
def create_ai_model():
    payload = build_ai_model_payload(request.form)
    created = create_ai_model_config(payload)
    if payload.get("is_default"):
        created = set_default_ai_model_config(created["id"])
    flash(f"已新增模型配置：{created['name']}")
    return redirect(url_for("ppt.ai_models_settings", edit_id=created["id"]))


@ppt_bp.route("/settings/ai-models/<int:config_id>/update", methods=["POST"])
def update_ai_model(config_id):
    existing = get_ai_model_config(config_id)
    if existing is None:
        abort(404)
    payload = build_ai_model_payload(request.form, existing=existing)
    updated = update_ai_model_config(config_id, payload)
    if payload.get("is_default"):
        updated = set_default_ai_model_config(config_id)
    elif existing.get("is_default") and not payload.get("is_default"):
        updated = clear_ai_model_default_flag(config_id)
    flash(f"已更新模型配置：{updated['name']}")
    return redirect(url_for("ppt.ai_models_settings", edit_id=config_id))


@ppt_bp.route("/settings/ai-models/<int:config_id>/delete", methods=["POST"])
def delete_ai_model(config_id):
    existing = get_ai_model_config(config_id)
    if existing is None:
        abort(404)
    delete_ai_model_config(config_id)
    flash(f"已删除模型配置：{existing['name']}")
    return redirect(url_for("ppt.ai_models_settings"))


@ppt_bp.route("/settings/ai-models/<int:config_id>/default", methods=["POST"])
def set_default_ai_model(config_id):
    config = get_ai_model_config(config_id)
    if config is None:
        abort(404)
    updated = set_default_ai_model_config(config_id)
    flash(f"已设置默认模型：{updated['name']}")
    return redirect(url_for("ppt.ai_models_settings", edit_id=config_id))


@ppt_bp.route("/settings/ai-models/<int:config_id>/toggle", methods=["POST"])
def toggle_ai_model(config_id):
    config = get_ai_model_config(config_id)
    if config is None:
        abort(404)
    updated = set_ai_model_enabled(config_id, not config.get("enabled"))
    state_label = "启用" if updated.get("enabled") else "禁用"
    flash(f"已{state_label}模型配置：{updated['name']}")
    return redirect(url_for("ppt.ai_models_settings", edit_id=config_id))


@ppt_bp.route("/settings/ai-models/<int:config_id>/test", methods=["POST"])
def test_ai_model(config_id):
    config = get_ai_model_config(config_id)
    if config is None:
        abort(404)
    result = test_model_connection(config)
    update_ai_model_test_result(config_id, result["status"], result["message"])
    flash(f"连接测试结果：{result['message']}")
    return redirect(url_for("ppt.ai_models_settings", edit_id=config_id))
