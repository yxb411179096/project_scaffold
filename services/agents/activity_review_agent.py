"""Activity review agent.

Current stage: mock / rule-based implementation.
Future replacement: a real model can review activity pacing, classroom
interaction, and executability using the same slide schema.
"""

import re

from services.mock_ai_service import normalize_lesson_type


NON_INTERACTIVE_TYPES = {
    "Teacher explanation",
    "Teacher guidance",
    "Teacher presentation",
}

LEAD_IN_TYPES = {"lead_in"}
INPUT_TYPES = {
    "prediction",
    "fast_reading",
    "careful_reading",
    "vocabulary_focus",
    "language_points",
    "observe_discover",
    "grammar_rule",
    "pre_listening",
    "while_listening",
    "key_vocabulary_review",
    "key_grammar_review",
    "sample_analysis",
    "useful_expressions",
    "structure_analysis",
}
OUTPUT_TYPES = {
    "group_discussion",
    "communicative_practice",
    "guided_writing",
    "peer_review",
    "speaking_task",
    "pair_work",
    "exercise_practice",
    "consolidation",
}
SUMMARY_TYPES = {"summary"}
HOMEWORK_TYPES = {"homework"}


def _parse_minutes(value):
    match = re.search(r"(\d+)", str(value or ""))
    return int(match.group(1)) if match else 3


def _format_minutes(minutes):
    suffix = "minute" if minutes == 1 else "minutes"
    return f"{minutes} {suffix}"


def _append_note_once(text, extra_note):
    text = str(text or "").strip()
    if extra_note in text:
        return text
    return f"{text} {extra_note}".strip()


def _build_support_slide(slide_index, slide_type, title, purpose, content, teacher_notes, interaction_type, warning):
    return {
        "slide_index": slide_index,
        "slide_type": slide_type,
        "title": title,
        "visible_content": content,
        "teacher_notes": teacher_notes,
        "teaching_purpose": purpose,
        "estimated_time": "2 minutes",
        "interaction_type": interaction_type,
        "warning": warning,
    }


def _reindex_slides(slides):
    for index, slide in enumerate(slides, start=1):
        slide["slide_index"] = index
    return slides


def _ensure_lesson_components(slides, lesson_request):
    lesson_key = normalize_lesson_type(lesson_request.get("lesson_type"))
    warnings = []
    topic = lesson_request.get("topic") or "today's topic"

    if not any(slide.get("slide_type") in LEAD_IN_TYPES for slide in slides):
        insert_at = 2 if len(slides) >= 2 else len(slides)
        slides.insert(
            insert_at,
            _build_support_slide(
                0,
                "lead_in",
                "Lead-in",
                "Warm up the class and activate prior knowledge.",
                [
                    f"Think about {topic}.",
                    "Share one quick idea with a partner.",
                    "Task: Be ready to report one idea.",
                ],
                "Use this short warm-up to make sure the lesson has a clear lead-in stage.",
                "Pair work",
                "Added a lead-in slide automatically because the lesson opening was missing.",
            ),
        )
        warnings.append("lead-in added")

    if not any(slide.get("slide_type") in INPUT_TYPES for slide in slides):
        insert_at = min(4, len(slides))
        slides.insert(
            insert_at,
            _build_support_slide(
                0,
                "language_points" if lesson_key == "reading" else "useful_expressions",
                "Language Input",
                "Provide a short input stage before students produce language.",
                [
                    "Notice the key example or expression.",
                    "Say what it means and how to use it.",
                    "Task: Use it in one short sentence.",
                ],
                "This support slide was added to guarantee a visible language input stage.",
                "Teacher-student interaction",
                "Added a language input slide automatically because the lesson lacked clear input.",
            ),
        )
        warnings.append("input added")

    if not any(slide.get("slide_type") in OUTPUT_TYPES for slide in slides):
        summary_index = next((idx for idx, slide in enumerate(slides) if slide.get("slide_type") in SUMMARY_TYPES), len(slides))
        slides.insert(
            summary_index,
            _build_support_slide(
                0,
                "pair_work",
                "Quick Output",
                "Add a short student output stage before the summary.",
                [
                    "Work with a partner.",
                    "Use today's language to answer the guiding question.",
                    "Task: Share one final idea with the class.",
                ],
                "This short output slide was added to make sure students produce language before the lesson ends.",
                "Pair work",
                "Added an output slide automatically because the lesson lacked language output.",
            ),
        )
        warnings.append("output added")

    if not any(slide.get("slide_type") in SUMMARY_TYPES for slide in slides):
        slides.append(
            _build_support_slide(
                0,
                "summary",
                "Summary",
                "Review the lesson before class ends.",
                [
                    "Review the key language and task.",
                    "Say one thing you can do now.",
                ],
                "This summary slide was added to give the lesson a clear closing stage.",
                "Teacher-student interaction",
                "Added a summary slide automatically because the lesson lacked a closing stage.",
            )
        )
        warnings.append("summary added")

    if not any(slide.get("slide_type") in HOMEWORK_TYPES for slide in slides):
        slides.append(
            _build_support_slide(
                0,
                "homework",
                "Homework",
                "Assign a short after-class follow-up task.",
                [
                    "Review today's key language.",
                    "Finish the follow-up task after class.",
                ],
                "This homework slide was added so the lesson ends with a clear after-class task.",
                "Teacher-student interaction",
                "Added a homework slide automatically because the lesson lacked follow-up work.",
            )
        )
        warnings.append("homework added")

    if not any(slide.get("interaction_type") not in NON_INTERACTIVE_TYPES for slide in slides):
        target_slide = next((slide for slide in slides if slide.get("slide_type") in {"lead_in", "pair_work", "group_discussion"}), None)
        if target_slide is None and slides:
            target_slide = slides[min(2, len(slides) - 1)]
        if target_slide is not None:
            target_slide["interaction_type"] = "Pair work"
            target_slide["teacher_notes"] = _append_note_once(
                target_slide.get("teacher_notes"),
                "Add a short pair exchange so students have visible classroom participation.",
            )
            target_slide["warning"] = "Interaction was strengthened automatically because student activity was weak."
            warnings.append("interaction strengthened")

    return _reindex_slides(slides), warnings


def _reduce_total_duration(slides, duration_limit):
    total_minutes = sum(_parse_minutes(slide.get("estimated_time")) for slide in slides)
    if total_minutes <= duration_limit:
        return slides

    while total_minutes > duration_limit:
        adjusted = False
        for slide in sorted(slides, key=lambda item: _parse_minutes(item.get("estimated_time")), reverse=True):
            minutes = _parse_minutes(slide.get("estimated_time"))
            minimum = 1 if slide.get("slide_type") in {"cover", "homework", "blackboard_design"} else 2
            if minutes > minimum:
                minutes -= 1
                slide["estimated_time"] = _format_minutes(minutes)
                slide["teacher_notes"] = _append_note_once(
                    slide.get("teacher_notes"),
                    "Keep the pace tight so the lesson fits the class period.",
                )
                total_minutes -= 1
                adjusted = True
                if total_minutes <= duration_limit:
                    break
        if not adjusted:
            break

    if total_minutes > duration_limit and slides:
        slides[-1]["warning"] = "The full lesson still feels tight for the available class time."
    return slides


def review_activities(slides, lesson_request):
    """Review pacing, activity balance, and classroom executability."""

    duration_limit = int(lesson_request.get("duration") or 45)
    reviewed_slides = [dict(slide) for slide in slides]
    reviewed_slides, _warnings = _ensure_lesson_components(reviewed_slides, lesson_request)
    reviewed_slides = _reduce_total_duration(reviewed_slides, duration_limit)
    return reviewed_slides
