"""Schema checker for final PPT JSON.

Current stage: mock / rule-based implementation.
Future replacement: a stricter schema validator can be added without changing
the calling code in the generation pipeline.
"""

REQUIRED_FIELDS = (
    "slide_index",
    "slide_type",
    "title",
    "visible_content",
    "teacher_notes",
    "teaching_purpose",
    "estimated_time",
    "interaction_type",
)

OPTIONAL_FIELDS = (
    "warning",
    "layout_plan",
    "image_suggestion",
    "key_sentence",
    "useful_expressions",
    "possible_answers",
    "chinese_hint",
)


def _normalize_visible_content(value):
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if not value:
        return []
    return [str(value).strip()]


def _normalize_estimated_time(value):
    text = str(value or "").strip()
    return text or "3 minutes"


def _normalize_short_text(value):
    return str(value or "").strip()


def _normalize_optional_value(field, value):
    if field in {"useful_expressions", "possible_answers"}:
        return _normalize_visible_content(value)
    if field == "layout_plan":
        return value if isinstance(value, dict) else {}
    return _normalize_short_text(value)


def _normalize_slide(slide, fallback_index):
    slide = dict(slide or {})
    normalized = {field: slide.get(field) for field in REQUIRED_FIELDS}

    normalized["slide_index"] = int(normalized.get("slide_index") or fallback_index)
    normalized["slide_type"] = str(normalized.get("slide_type") or "summary").strip()
    normalized["title"] = str(normalized.get("title") or f"Slide {normalized['slide_index']}").strip()
    normalized["visible_content"] = _normalize_visible_content(normalized.get("visible_content"))
    normalized["teacher_notes"] = str(normalized.get("teacher_notes") or "").strip()
    normalized["teaching_purpose"] = str(normalized.get("teaching_purpose") or "").strip()
    normalized["estimated_time"] = _normalize_estimated_time(normalized.get("estimated_time"))
    normalized["interaction_type"] = str(normalized.get("interaction_type") or "Teacher guidance").strip()
    for field in OPTIONAL_FIELDS:
        if slide.get(field) is not None:
            normalized[field] = _normalize_optional_value(field, slide.get(field))

    return normalized


def check_schema(ppt_json):
    """Fill missing slide fields so export services never receive bad schema."""

    is_single_slide = isinstance(ppt_json, dict)
    slides = [ppt_json] if is_single_slide else list(ppt_json or [])
    normalized_slides = [
        _normalize_slide(slide, fallback_index=index)
        for index, slide in enumerate(slides, start=1)
    ]
    return normalized_slides[0] if is_single_slide else normalized_slides
