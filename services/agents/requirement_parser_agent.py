"""Requirement parser agent.

Current stage: mock / rule-based implementation.
Future replacement: this file can call a real LLM to normalize noisy user
input into a stable lesson request schema.
"""


def _clean_text(value):
    return str(value or "").strip()


def _safe_duration(value, default=45):
    try:
        duration = int(value)
    except (TypeError, ValueError):
        duration = default
    return max(20, min(duration, 120))


def _safe_bool(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "checked"}


def _safe_top_k(value, default=5):
    try:
        top_k = int(value)
    except (TypeError, ValueError):
        top_k = default
    return max(1, min(top_k, 10))


def parse_requirement(form_data):
    """Convert raw form or task data into a standard lesson_request dict."""

    topic = (
        _clean_text(form_data.get("topic"))
        or _clean_text(form_data.get("course_title"))
        or "Senior English Lesson"
    )

    lesson_request = {
        "task_id": form_data.get("task_id") or form_data.get("id"),
        "grade": _clean_text(form_data.get("grade")) or "高一",
        "textbook": _clean_text(form_data.get("textbook")) or "人教版",
        "unit": _clean_text(form_data.get("unit")) or "Unit 1",
        "topic": topic,
        # Keep an alias for compatibility with the current template-based mock service.
        "course_title": topic,
        "lesson_type": _clean_text(form_data.get("lesson_type")) or "Reading",
        "duration": _safe_duration(form_data.get("duration"), default=45),
        "student_level": _clean_text(form_data.get("student_level")) or "中等",
        "style": _clean_text(form_data.get("style")) or "常规课",
        "extra_requirements": _clean_text(form_data.get("extra_requirements")),
        "manuscript_generation_strategy": _clean_text(form_data.get("manuscript_generation_strategy")) or "ai_restructure",
        "manuscript_preserve_completion_mode": _clean_text(
            form_data.get("manuscript_preserve_completion_mode")
        ) or "preserve_exact_pages",
        "manuscript_preserve_polish_mode": _clean_text(
            form_data.get("manuscript_preserve_polish_mode")
        ) or "skip",
        "use_knowledge_base": _safe_bool(form_data.get("use_knowledge_base")),
        "knowledge_query": _clean_text(form_data.get("knowledge_query")),
        "knowledge_top_k": _safe_top_k(form_data.get("knowledge_top_k"), default=5),
        "knowledge_context_json": _clean_text(form_data.get("knowledge_context_json")),
    }
    return lesson_request
