"""Language polish agent.

Current stage: hybrid local Ollama + rule-based fallback.
Future replacement: use a stronger model to polish classroom English while
keeping content age-appropriate for Chinese senior high school learners.
"""

import json
import re

from services.agents.json_schema_checker import check_schema
from services.llm_service import call_agent_json
from services.knowledge_retrieval_service import format_knowledge_context_for_prompt


TITLE_MAP = {
    "lead-in": "Lead-in",
    "pre-listening": "Pre-listening",
    "while-listening": "While-listening",
    "post-listening": "Post-listening",
}

INTERACTION_MAP = {
    "teacher-student interaction": "Teacher-student interaction",
    "pair work": "Pair work",
    "group discussion": "Group discussion",
    "group work": "Group discussion",
    "individual work": "Individual work",
}

LINE_REPLACEMENTS = {
    "Task: ": "Task: ",
    "Work in groups and prepare two key ideas.": "Work in groups and prepare two strong ideas.",
    "Read quickly for the main idea.": "Skim the text for the main idea.",
    "Read again for key details.": "Read again and look for key details.",
    "Check the answers with your partner.": "Check your answers with your partner.",
}


def _squeeze_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _sentence_case(text):
    chars = list(text)
    for index, char in enumerate(chars):
        if char.isalpha():
            chars[index] = char.upper()
            break
    return "".join(chars)


def _normalize_title(text):
    text = _squeeze_spaces(text)
    if not text:
        return "Untitled Slide"
    normalized = TITLE_MAP.get(text.lower())
    if normalized:
        return normalized
    if " " in text:
        return " ".join(word.capitalize() if word.isalpha() else word for word in text.split())
    return text


def _naturalize_line(text):
    text = _sentence_case(_squeeze_spaces(text))
    if not text:
        return text
    text = LINE_REPLACEMENTS.get(text, text)
    text = text.replace("students can now", "students can")
    text = text.replace("Share one idea with your partner before whole-class feedback.", "Share one idea with your partner before class feedback.")
    text = text.replace("Task: Finish or improve", "Task: Improve")
    if "->" in text or text.endswith((".", "?", "!", ":")):
        return text
    if re.search(r"[\u4e00-\u9fff]", text) or "|" in text:
        return text
    if text.startswith("Task:"):
        return text
    if len(text.split()) <= 4:
        return text
    return f"{text}."


def _polish_teacher_notes(text):
    text = _sentence_case(_squeeze_spaces(text))
    if not text:
        return "Give clear instructions and keep the class pace steady."
    text = text.replace("students feel secure", "students feel confident")
    text = text.replace("Move quickly from answer checking into meaning making", "Move from answer checking to meaning making")
    if not text.endswith((".", "?", "!")):
        text = f"{text}."
    return text


def _normalize_interaction(text):
    text = _squeeze_spaces(text)
    if not text:
        return "Teacher-student interaction"
    return INTERACTION_MAP.get(text.lower(), text)


def _rule_polish_language(slides, lesson_request=None):
    is_single_slide = isinstance(slides, dict)
    slide_list = [slides] if is_single_slide else slides
    polished_slides = []
    preserve_titles = str((lesson_request or {}).get("manuscript_generation_strategy") or "").strip() == "preserve_original_pages"

    for slide in slide_list:
        polished = dict(slide)
        polished["title"] = _squeeze_spaces(polished.get("title")) if preserve_titles else _normalize_title(polished.get("title"))
        polished["visible_content"] = [
            _naturalize_line(item)
            for item in polished.get("visible_content", [])
            if _squeeze_spaces(item)
        ][:4]
        polished["teacher_notes"] = _polish_teacher_notes(polished.get("teacher_notes"))
        polished["teaching_purpose"] = _naturalize_line(polished.get("teaching_purpose"))
        polished["interaction_type"] = _normalize_interaction(polished.get("interaction_type"))
        polished["image_suggestion"] = _squeeze_spaces(polished.get("image_suggestion"))
        polished["key_sentence"] = _naturalize_line(polished.get("key_sentence"))
        polished["useful_expressions"] = [
            _naturalize_line(item)
            for item in polished.get("useful_expressions", [])
            if _squeeze_spaces(item)
        ][:4]
        polished["possible_answers"] = [
            _naturalize_line(item)
            for item in polished.get("possible_answers", [])
            if _squeeze_spaces(item)
        ][:4]
        polished["chinese_hint"] = _squeeze_spaces(polished.get("chinese_hint"))
        if polished.get("warning"):
            polished["warning"] = _naturalize_line(polished.get("warning"))
        polished_slides.append(polished)

    return polished_slides[0] if is_single_slide else polished_slides


def _normalize_polished_slide(candidate, fallback):
    candidate = candidate if isinstance(candidate, dict) else {}
    try:
        slide_index = int(candidate.get("slide_index"))
    except (TypeError, ValueError):
        slide_index = int(fallback["slide_index"])
    normalized = {
        "slide_index": slide_index,
        "slide_type": str(candidate.get("slide_type") or fallback["slide_type"]).strip(),
        "title": str(candidate.get("title") or fallback["title"]).strip(),
        "visible_content": candidate.get("visible_content") or fallback.get("visible_content", []),
        "teacher_notes": str(candidate.get("teacher_notes") or fallback["teacher_notes"]).strip(),
        "teaching_purpose": str(
            candidate.get("teaching_purpose") or fallback["teaching_purpose"]
        ).strip(),
        "estimated_time": str(candidate.get("estimated_time") or fallback["estimated_time"]).strip(),
        "interaction_type": str(
            candidate.get("interaction_type") or fallback["interaction_type"]
        ).strip(),
        "image_suggestion": str(
            candidate.get("image_suggestion") or fallback.get("image_suggestion") or ""
        ).strip(),
        "key_sentence": str(candidate.get("key_sentence") or fallback.get("key_sentence") or "").strip(),
        "useful_expressions": candidate.get("useful_expressions") or fallback.get("useful_expressions", []),
        "possible_answers": candidate.get("possible_answers") or fallback.get("possible_answers", []),
        "chinese_hint": str(candidate.get("chinese_hint") or fallback.get("chinese_hint") or "").strip(),
    }
    if fallback.get("warning"):
        normalized["warning"] = str(candidate.get("warning") or fallback["warning"]).strip()
    return check_schema(normalized)


def _normalize_polished_collection(payload, fallback):
    candidate_slides = payload.get("slides") if isinstance(payload, dict) else payload
    if not isinstance(candidate_slides, list):
        return fallback

    normalized = []
    for index, fallback_slide in enumerate(fallback):
        candidate = candidate_slides[index] if index < len(candidate_slides) else {}
        normalized.append(_normalize_polished_slide(candidate, fallback_slide))
    return check_schema(normalized)


def _normalize_single_polished(payload, fallback):
    if isinstance(payload, dict) and isinstance(payload.get("slide"), dict):
        payload = payload["slide"]
    return _normalize_polished_slide(payload, fallback)


def _knowledge_context_block(knowledge_context):
    if not knowledge_context:
        return ""
    return "\n\n" + format_knowledge_context_for_prompt(knowledge_context)


def _preserve_mode_note(lesson_request):
    if str((lesson_request or {}).get("manuscript_generation_strategy") or "").strip() == "preserve_original_pages":
        return "\n\nPreserve mode note: keep the original page titles and slide order unchanged. Use knowledge only for teacher_notes or useful_expressions, and do not rewrite the page structure."
    return ""


def _polish_prompts(slides, lesson_request, knowledge_context=None):
    system_prompt = """
You are a senior high school English classroom editor.
Return JSON only.
Polish English naturally, keep it concise, and keep the teaching meaning unchanged.
"""
    user_prompt = f"""
Polish the classroom English in these slides.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Slides to polish:
{json.dumps(slides, ensure_ascii=False, indent=2)}

{_knowledge_context_block(knowledge_context)}{_preserve_mode_note(lesson_request)}

Return one JSON object with a "slides" array.
Each slide must keep these fields:
- slide_index
- slide_type
- title
- visible_content
- teacher_notes
- teaching_purpose
- estimated_time
- interaction_type
- image_suggestion
- key_sentence
- useful_expressions
- possible_answers
- chinese_hint

Requirements:
- Keep slide count and slide order unchanged.
- visible_content should stay short and easy to project.
- teacher_notes should sound natural for real classroom use.
- Do not add markdown or explanations.
"""
    return system_prompt.strip(), user_prompt.strip()


def _single_polish_prompts(slide, lesson_request, knowledge_context=None):
    system_prompt = """
You are a senior high school English classroom editor.
Return JSON only.
Polish English naturally, keep it concise, and keep the teaching meaning unchanged.
"""
    user_prompt = f"""
Polish this classroom slide.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Slide to polish:
{json.dumps(slide, ensure_ascii=False, indent=2)}

{_knowledge_context_block(knowledge_context)}{_preserve_mode_note(lesson_request)}

Return one JSON object with a "slide" object.
Keep these fields:
- slide_index
- slide_type
- title
- visible_content
- teacher_notes
- teaching_purpose
- estimated_time
- interaction_type
- image_suggestion
- key_sentence
- useful_expressions
- possible_answers
- chinese_hint

Requirements:
- Keep the same teaching purpose and interaction type.
- Keep visible content short and natural.
- Do not add markdown or explanations.
"""
    return system_prompt.strip(), user_prompt.strip()


def polish_language(slides, lesson_request, knowledge_context=None):
    """Polish classroom English with Ollama first and rule-based fallback."""

    fallback = _rule_polish_language(slides, lesson_request)
    if isinstance(slides, dict):
        system_prompt, user_prompt = _single_polish_prompts(slides, lesson_request, knowledge_context=knowledge_context)
        payload = call_agent_json(
            "language_polish_agent",
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "task_id": lesson_request.get("task_id"),
                "stage_note": "language_polish_single",
            },
            fallback_fn=lambda: fallback,
        )
        return _rule_polish_language(_normalize_single_polished(payload, fallback), lesson_request)

    polished = []
    chunk_size = 4
    for start in range(0, len(slides), chunk_size):
        slide_chunk = slides[start:start + chunk_size]
        fallback_chunk = fallback[start:start + chunk_size]
        stage = f"language_polish_batch_{start // chunk_size + 1}"
        system_prompt, user_prompt = _polish_prompts(slide_chunk, lesson_request, knowledge_context=knowledge_context)
        payload = call_agent_json(
            "language_polish_agent",
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "task_id": lesson_request.get("task_id"),
                "stage_note": stage,
            },
            fallback_fn=lambda chunk=fallback_chunk: chunk,
        )
        polished.extend(_rule_polish_language(_normalize_polished_collection(payload, fallback_chunk), lesson_request))
    return polished
