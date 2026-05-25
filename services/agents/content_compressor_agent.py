"""Content compressor agent for manuscript-based slide decks.

Current stage: hybrid Ollama + rule-based fallback.
Future replacement: a stronger model can perform finer instructional
compression while preserving the same slide schema and fallback behavior.
"""

import json
import re

from services.llm_service import call_agent_json, trim_knowledge_context_for_prompt
from services.knowledge_retrieval_service import format_knowledge_context_for_prompt
from services.mock_ai_service import normalize_lesson_type


TASK_SLIDE_TYPES = {
    "lead_in",
    "prediction",
    "group_discussion",
    "guided_practice",
    "controlled_practice",
    "communicative_practice",
    "guided_writing",
    "peer_review",
    "pair_work",
    "speaking_task",
    "exercise_practice",
    "writing_task",
}

KNOWLEDGE_SLIDE_TYPES = {
    "vocabulary_focus",
    "language_points",
    "grammar_rule",
    "useful_expressions",
    "structure_analysis",
    "observe_discover",
    "key_vocabulary_review",
    "key_grammar_review",
}


def _word_count(text):
    return len(re.findall(r"[A-Za-z0-9']+", str(text or "")))


def _contains_chinese(text):
    return bool(re.search(r"[\u4e00-\u9fff]", str(text or "")))


def _normalize_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_orphan_number_marker(text):
    return bool(re.match(r"^(?:\d+|[A-Za-z])[.)、．]$", _normalize_spaces(text)))


def _limit_line(text):
    text = _normalize_spaces(text)
    if not text:
        return ""
    pieces = re.split(r"[;；]|(?<=[。.!?])\s+", text)
    candidate = pieces[0].strip() if pieces else text
    if _contains_chinese(candidate) and len(candidate) > 40:
        candidate = candidate[:40].rstrip("，,;； ") + "..."
    elif _word_count(candidate) > 25:
        words = re.findall(r"[A-Za-z0-9']+|[^\s]", candidate)
        candidate = " ".join(words[:25]).strip() + "..."
    return candidate


def _dedupe(items, limit=5):
    seen = set()
    result = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
        if len(result) >= limit:
            break
    return result


def _task_labels(slide_type, lesson_type):
    lesson_key = normalize_lesson_type(lesson_type)
    if lesson_key == "reading":
        return ["Question", "Task", "Evidence", "Share"]
    if lesson_key == "writing":
        return ["Task", "Structure", "Support", "Write"]
    if lesson_key == "grammar":
        return ["Observe", "Rule", "Practice", "Check"]
    return ["Task", "Question", "Instruction", "Check"]


def _knowledge_labels(slide_type, lesson_type):
    lesson_key = normalize_lesson_type(lesson_type)
    if lesson_key == "writing":
        return ["Expression", "Structure", "Example", "Use"]
    if lesson_key == "grammar":
        return ["Example", "Rule", "Pattern", "Practice"]
    if lesson_key == "reading":
        return ["Keyword", "Clue", "Example", "Use"]
    return ["Keyword", "Example", "Rule", "Practice"]


def _fit_visible_content(items, slide_type, lesson_type, preserve_mode=False):
    compressed = []
    for item in items:
        line = _limit_line(item)
        if line and not _is_orphan_number_marker(line):
            compressed.append(line)
    compressed = _dedupe(compressed, limit=5)
    if not compressed:
        return []

    if preserve_mode:
        return compressed[:5]

    if slide_type in TASK_SLIDE_TYPES:
        labels = _task_labels(slide_type, lesson_type)
        normalized = []
        for index, item in enumerate(compressed[:4]):
            if item.lower().startswith(("task:", "question:", "instruction:", "observe:", "rule:", "practice:", "evidence:", "share:", "write:")):
                normalized.append(item)
            else:
                normalized.append(f"{labels[min(index, len(labels) - 1)]}: {item}")
        return normalized

    if slide_type in KNOWLEDGE_SLIDE_TYPES:
        labels = _knowledge_labels(slide_type, lesson_type)
        normalized = []
        for index, item in enumerate(compressed[:4]):
            if ":" in item[:18]:
                normalized.append(item)
            else:
                normalized.append(f"{labels[min(index, len(labels) - 1)]}: {item}")
        return normalized

    return compressed[:5]


def _append_source_detail(notes, long_items):
    if not long_items:
        return notes
    source_detail = " ".join(_normalize_spaces(item) for item in long_items[:2]).strip()
    if not source_detail:
        return notes
    if notes:
        return f"{notes} Source detail: {source_detail}".strip()
    return f"Source detail: {source_detail}"


def _compress_slide_rule(slide, lesson_request):
    compressed = dict(slide)
    lesson_type = lesson_request.get("lesson_type") or "Reading"
    preserve_mode = str(lesson_request.get("manuscript_generation_strategy") or "").strip() == "preserve_original_pages"
    original_content = list(compressed.get("visible_content", []) or [])
    original_notes = _normalize_spaces(compressed.get("teacher_notes") or "")

    compressed["visible_content"] = _fit_visible_content(
        original_content,
        compressed.get("slide_type"),
        lesson_type,
        preserve_mode=preserve_mode,
    )
    if not compressed["visible_content"]:
        fallback_source = [
            compressed.get("teaching_purpose") or "",
            compressed.get("title") or "",
            "Complete the classroom task.",
        ]
        compressed["visible_content"] = _fit_visible_content(
            fallback_source,
            compressed.get("slide_type"),
            lesson_type,
            preserve_mode=preserve_mode,
        )

    long_items = []
    for item in original_content:
        normalized = _normalize_spaces(item)
        limited = _limit_line(normalized)
        if limited and limited != normalized:
            long_items.append(normalized)

    if compressed.get("slide_type") in {"summary", "homework"}:
        compressed["visible_content"] = compressed["visible_content"][:3]

    compressed["teacher_notes"] = _append_source_detail(original_notes, long_items)
    compressed["image_suggestion"] = _normalize_spaces(compressed.get("image_suggestion") or "")
    compressed["key_sentence"] = _normalize_spaces(compressed.get("key_sentence") or "")
    compressed["useful_expressions"] = _fit_visible_content(
        list(compressed.get("useful_expressions", []) or []),
        "useful_expressions",
        lesson_type,
        preserve_mode=preserve_mode,
    )
    compressed["possible_answers"] = _dedupe(
        [
            normalized
            for item in list(compressed.get("possible_answers", []) or [])
            for normalized in [_limit_line(item)]
            if normalized and not _is_orphan_number_marker(normalized)
        ],
        limit=4,
    )
    compressed["chinese_hint"] = _limit_line(compressed.get("chinese_hint") or "")
    return compressed


def _compress_slides_rule(slides, lesson_request):
    is_single = isinstance(slides, dict)
    slide_list = [slides] if is_single else list(slides or [])
    compressed_slides = [_compress_slide_rule(slide, lesson_request) for slide in slide_list]
    return compressed_slides[0] if is_single else compressed_slides


def generate_rule_compressed_slides(slides, lesson_request=None):
    """Return the local rule-based compressed slide deck."""

    lesson_request = lesson_request or {"lesson_type": "Reading"}
    return _compress_slides_rule(slides, lesson_request)


def _normalize_visible_content(value, fallback):
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item or "").strip()]
        if cleaned:
            return cleaned[:5]
    return list(fallback)


def _normalize_slides(payload, fallback):
    candidate_slides = payload.get("slides") if isinstance(payload, dict) else payload
    if isinstance(fallback, dict):
        fallback_list = [fallback]
        single = True
    else:
        fallback_list = list(fallback or [])
        single = False

    if not isinstance(candidate_slides, list):
        return fallback if single else fallback_list

    normalized = []
    for index, fallback_slide in enumerate(fallback_list):
        candidate = candidate_slides[index] if index < len(candidate_slides) and isinstance(candidate_slides[index], dict) else {}
        normalized.append(
            {
                "slide_index": fallback_slide["slide_index"],
                "slide_type": str(candidate.get("slide_type") or fallback_slide["slide_type"]).strip(),
                "title": str(candidate.get("title") or fallback_slide["title"]).strip(),
                "visible_content": _normalize_visible_content(
                    candidate.get("visible_content"),
                    fallback_slide.get("visible_content", []),
                ),
                "teacher_notes": str(candidate.get("teacher_notes") or fallback_slide["teacher_notes"]).strip(),
                "teaching_purpose": str(
                    candidate.get("teaching_purpose") or fallback_slide["teaching_purpose"]
                ).strip(),
                "estimated_time": str(candidate.get("estimated_time") or fallback_slide["estimated_time"]).strip(),
                "interaction_type": str(
                    candidate.get("interaction_type") or fallback_slide["interaction_type"]
                ).strip(),
                "image_suggestion": str(
                    candidate.get("image_suggestion") or fallback_slide.get("image_suggestion") or ""
                ).strip(),
                "key_sentence": str(candidate.get("key_sentence") or fallback_slide.get("key_sentence") or "").strip(),
                "useful_expressions": _normalize_visible_content(
                    candidate.get("useful_expressions"),
                    fallback_slide.get("useful_expressions", []),
                ),
                "possible_answers": _normalize_visible_content(
                    candidate.get("possible_answers"),
                    fallback_slide.get("possible_answers", []),
                ),
                "chinese_hint": str(candidate.get("chinese_hint") or fallback_slide.get("chinese_hint") or "").strip(),
            }
        )
    return normalized[0] if single else normalized


def _knowledge_context_block(knowledge_context):
    if not knowledge_context:
        return ""
    return "\n\n" + trim_knowledge_context_for_prompt(format_knowledge_context_for_prompt(knowledge_context), max_chars=4000)


def _compressor_prompts(slides, lesson_request, fallback, knowledge_context=None):
    system_prompt = """
You compress lesson manuscript content into concise PPT slide wording.
Return JSON only.
"""
    user_prompt = f"""
Compress the slide content for PPT display.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Input slides:
{json.dumps(slides, ensure_ascii=False, indent=2)}

Fallback compressed slides:
{json.dumps(fallback, ensure_ascii=False, indent=2)}

{_knowledge_context_block(knowledge_context)}

Return one JSON object with a "slides" array.

Requirements:
- Keep visible_content concise.
- Each visible_content item should stay under about 25 English words or 40 Chinese characters.
- visible_content must contain at most 5 items per slide.
- Put detailed explanations in teacher_notes, not on the slide itself.
- For reading slides, prefer question / task / keyword wording.
- For writing slides, prefer structure / expression / scaffold wording.
- For grammar slides, prefer example / rule / practice wording.
"""
    return system_prompt.strip(), user_prompt.strip()


def compress_slide_content(slides, lesson_request, knowledge_context=None):
    """Compress manuscript-derived slide content for PPT display."""

    fallback = _compress_slides_rule(slides, lesson_request)
    system_prompt, user_prompt = _compressor_prompts(
        slides,
        lesson_request,
        fallback,
        knowledge_context=knowledge_context,
    )
    payload = call_agent_json(
        "content_compressor_agent",
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Compress manuscript slide content for PPT display.",
        },
        fallback_fn=lambda: {"slides": fallback} if isinstance(fallback, list) else {"slides": [fallback]},
    )
    return _normalize_slides(payload, fallback)
