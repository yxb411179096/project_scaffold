"""Slide splitter agent for manuscript-based generation.

Current stage: hybrid Ollama + rule-based fallback.
Future replacement: a stronger model can perform richer slide planning while
keeping the same slide schema and the same fallback behavior.
"""

import json
import re

from services.llm_service import call_agent_json
from services.mock_ai_service import normalize_lesson_type


SLIDE_PURPOSE = {
    "cover": "Open the lesson and present the theme.",
    "objectives": "Clarify what students should learn in this lesson.",
    "lead_in": "Activate background knowledge and build interest.",
    "prediction": "Guide students to predict topic and content before deeper input.",
    "fast_reading": "Check gist and text structure quickly.",
    "careful_reading": "Guide students to locate details and evidence.",
    "vocabulary_focus": "Highlight useful words, phrases, and chunks.",
    "language_points": "Explain useful language points or sentence patterns.",
    "observe_discover": "Lead students to notice grammar in context.",
    "grammar_rule": "Make the target grammar rule visible and usable.",
    "guided_practice": "Provide scaffolded language practice.",
    "controlled_practice": "Strengthen accuracy through focused practice.",
    "communicative_practice": "Turn practice into meaningful communication.",
    "writing_task": "Clarify writing purpose, task, and output.",
    "structure_analysis": "Help students see the writing structure clearly.",
    "useful_expressions": "Provide useful expressions and sentence support.",
    "guided_writing": "Support drafting with prompts and scaffolds.",
    "peer_review": "Use peer feedback to improve output.",
    "pre_listening": "Prepare students for the listening task.",
    "while_listening": "Focus on gist and detail while listening.",
    "post_listening": "Connect listening input with reflection and output.",
    "speaking_task": "Turn input into speaking practice.",
    "pair_work": "Increase participation through pair interaction.",
    "key_vocabulary_review": "Review key vocabulary efficiently.",
    "key_grammar_review": "Review core grammar knowledge.",
    "exercise_practice": "Consolidate learning through short exercises.",
    "error_analysis": "Analyze and correct common mistakes.",
    "consolidation": "Link reviewed content into an integrated task.",
    "group_discussion": "Encourage student output and deeper thinking.",
    "summary": "Review key learning and close the lesson.",
    "homework": "Assign a clear follow-up task after class.",
    "blackboard_design": "Preserve the board design or classroom logic.",
}

STEP_TO_SLIDE_TYPE = {
    "Lead-in": "lead_in",
    "Prediction": "prediction",
    "Fast Reading": "fast_reading",
    "Careful Reading": "careful_reading",
    "Vocabulary Focus": "vocabulary_focus",
    "Language Points": "language_points",
    "Discussion": "group_discussion",
    "Observe and Discover": "observe_discover",
    "Grammar Rule": "grammar_rule",
    "Guided Practice": "guided_practice",
    "Controlled Practice": "controlled_practice",
    "Communicative Practice": "communicative_practice",
    "Writing Task": "writing_task",
    "Structure Analysis": "structure_analysis",
    "Useful Expressions": "useful_expressions",
    "Guided Writing": "guided_writing",
    "Peer Review": "peer_review",
    "Pre-listening": "pre_listening",
    "While-listening": "while_listening",
    "Post-listening": "post_listening",
    "Speaking Task": "speaking_task",
    "Pair Work": "pair_work",
    "Key Vocabulary Review": "key_vocabulary_review",
    "Key Grammar Review": "key_grammar_review",
    "Exercise Practice": "exercise_practice",
    "Error Analysis": "error_analysis",
    "Consolidation": "consolidation",
    "Summary": "summary",
}

LESSON_BLUEPRINTS = {
    "reading": [
        ("cover", "Cover", "Teacher-student interaction", "2 minutes", None),
        ("objectives", "Learning Objectives", "Teacher-student interaction", "3 minutes", None),
        ("lead_in", "Lead-in", "Teacher-student interaction", "4 minutes", "Lead-in"),
        ("prediction", "Prediction", "Pair work", "4 minutes", "Prediction"),
        ("fast_reading", "Fast Reading", "Individual work", "6 minutes", "Fast Reading"),
        ("careful_reading", "Careful Reading", "Teacher-student interaction", "8 minutes", "Careful Reading"),
        ("vocabulary_focus", "Vocabulary Focus", "Teacher-student interaction", "5 minutes", "Vocabulary Focus"),
        ("language_points", "Language Points", "Teacher-student interaction", "5 minutes", "Language Points"),
        ("group_discussion", "Discussion", "Group discussion", "5 minutes", "Discussion"),
        ("summary", "Summary", "Teacher-student interaction", "3 minutes", "Summary"),
        ("homework", "Homework", "Teacher-student interaction", "2 minutes", None),
    ],
    "grammar": [
        ("cover", "Cover", "Teacher-student interaction", "2 minutes", None),
        ("objectives", "Learning Objectives", "Teacher-student interaction", "3 minutes", None),
        ("lead_in", "Lead-in", "Teacher-student interaction", "4 minutes", "Lead-in"),
        ("observe_discover", "Observe and Discover", "Teacher-student interaction", "5 minutes", "Observe and Discover"),
        ("grammar_rule", "Grammar Rule", "Teacher guidance", "5 minutes", "Grammar Rule"),
        ("guided_practice", "Guided Practice", "Individual work", "6 minutes", "Guided Practice"),
        ("controlled_practice", "Controlled Practice", "Pair work", "6 minutes", "Controlled Practice"),
        ("communicative_practice", "Communicative Practice", "Pair work", "6 minutes", "Communicative Practice"),
        ("summary", "Summary", "Teacher-student interaction", "3 minutes", "Summary"),
        ("homework", "Homework", "Teacher-student interaction", "2 minutes", None),
    ],
    "writing": [
        ("cover", "Cover", "Teacher-student interaction", "2 minutes", None),
        ("objectives", "Learning Objectives", "Teacher-student interaction", "3 minutes", None),
        ("lead_in", "Lead-in", "Teacher-student interaction", "4 minutes", "Lead-in"),
        ("writing_task", "Writing Task", "Teacher-student interaction", "4 minutes", "Writing Task"),
        ("structure_analysis", "Structure Analysis", "Teacher guidance", "5 minutes", "Structure Analysis"),
        ("useful_expressions", "Useful Expressions", "Teacher-student interaction", "5 minutes", "Useful Expressions"),
        ("guided_writing", "Guided Writing", "Individual work", "8 minutes", "Guided Writing"),
        ("peer_review", "Peer Review", "Pair work", "5 minutes", "Peer Review"),
        ("summary", "Summary", "Teacher-student interaction", "3 minutes", "Summary"),
        ("homework", "Homework", "Teacher-student interaction", "2 minutes", None),
    ],
    "listening_speaking": [
        ("cover", "Cover", "Teacher-student interaction", "2 minutes", None),
        ("objectives", "Learning Objectives", "Teacher-student interaction", "3 minutes", None),
        ("lead_in", "Lead-in", "Teacher-student interaction", "4 minutes", "Lead-in"),
        ("pre_listening", "Pre-listening", "Teacher-student interaction", "4 minutes", "Pre-listening"),
        ("while_listening", "While-listening", "Individual work", "7 minutes", "While-listening"),
        ("post_listening", "Post-listening", "Teacher-student interaction", "5 minutes", "Post-listening"),
        ("speaking_task", "Speaking Task", "Pair work", "6 minutes", "Speaking Task"),
        ("pair_work", "Pair Work", "Pair work", "5 minutes", "Pair Work"),
        ("summary", "Summary", "Teacher-student interaction", "3 minutes", "Summary"),
        ("homework", "Homework", "Teacher-student interaction", "2 minutes", None),
    ],
    "revision": [
        ("cover", "Cover", "Teacher-student interaction", "2 minutes", None),
        ("objectives", "Learning Objectives", "Teacher-student interaction", "3 minutes", None),
        ("key_vocabulary_review", "Key Vocabulary Review", "Teacher-student interaction", "5 minutes", "Key Vocabulary Review"),
        ("key_grammar_review", "Key Grammar Review", "Teacher guidance", "5 minutes", "Key Grammar Review"),
        ("exercise_practice", "Exercise Practice", "Individual work", "7 minutes", "Exercise Practice"),
        ("error_analysis", "Error Analysis", "Teacher-student interaction", "5 minutes", "Error Analysis"),
        ("consolidation", "Consolidation", "Pair work", "6 minutes", "Consolidation"),
        ("summary", "Summary", "Teacher-student interaction", "3 minutes", "Summary"),
        ("homework", "Homework", "Teacher-student interaction", "2 minutes", None),
    ],
}

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


def _normalize_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _split_points(text, limit=5):
    points = []
    for part in re.split(r"[\n;；]|(?<=[。.!?])\s+", str(text or "")):
        cleaned = part.strip(" -•\t")
        if cleaned:
            points.append(cleaned)
    return points[:limit]


def _limit_line(text):
    cleaned = _normalize_spaces(text)
    if len(cleaned) <= 96:
        return cleaned
    return f"{cleaned[:96].rstrip()}..."


def _step_map(lesson_structure):
    mapped = {}
    for step in lesson_structure.get("teaching_steps", []):
        step_name = str(step.get("step_name") or "").strip()
        if step_name:
            mapped[step_name] = step
    return mapped


def _task_line(line, index):
    if line.lower().startswith(("task:", "question:", "instruction:")):
        return line
    prefixes = ["Task", "Question", "Instruction", "Check"]
    return f"{prefixes[min(index, len(prefixes) - 1)]}: {line}"


def _content_from_step(slide_type, step, lesson_request, lesson_structure, manuscript_analysis):
    content = str(step.get("content") or "").strip()
    points = [_limit_line(item) for item in _split_points(content, limit=5)]
    if points:
        if slide_type in TASK_SLIDE_TYPES:
            return [_task_line(item, index) for index, item in enumerate(points[:4])]
        return points[:5]

    topic = manuscript_analysis.get("main_topic") or lesson_request.get("course_title") or "the lesson topic"
    defaults = {
        "lead_in": [f"Question: What comes to your mind when you hear {topic}?", "Share one quick idea with your partner."],
        "prediction": ["Look at the title or key words.", "Question: What may the text be about?", "Give one reason for your prediction."],
        "fast_reading": ["Task: Read quickly and find the main idea.", "Task: Match each part with its key point."],
        "careful_reading": ["Task: Read again and find supporting details.", "Question: Which sentence gives the best evidence?"],
        "vocabulary_focus": ["Keyword: highlight useful words", "Example: use one word in a sentence"],
        "language_points": ["Rule: notice one useful pattern", "Example: apply the pattern in context"],
        "group_discussion": [f"Question: What can we learn from {topic}?", "Instruction: discuss and share one idea."],
        "grammar_rule": ["Observe the examples carefully.", "Summarize the grammar rule in one sentence.", "Try one sentence of your own."],
        "writing_task": ["Task: understand the writing goal.", "Question: Who is the audience?", "Instruction: plan before writing."],
        "structure_analysis": ["Identify the opening, body, and ending.", "Notice how ideas are connected."],
        "useful_expressions": ["Collect 3 useful expressions.", "Choose 1 expression for your own task."],
        "guided_writing": ["Task: follow the writing scaffold.", "Instruction: finish one short paragraph first."],
    }
    return defaults.get(slide_type, [f"Task: complete the {slide_type.replace('_', ' ')} step."])


def _teacher_notes(slide_type, step, lesson_structure, manuscript_analysis):
    content = _normalize_spaces(step.get("content") or "")
    if content:
        return content
    if slide_type == "objectives":
        return "Explain the learning objectives in student-friendly language and connect them with today's tasks."
    if slide_type == "summary":
        return "Lead students to restate the key takeaways and one useful strategy from the lesson."
    if slide_type == "homework":
        return "Clarify the homework product, deadline, and success criteria."
    return manuscript_analysis.get("organization_suggestion") or "Use this slide to guide the class step by step."


def _cover_slide(lesson_request, manuscript_analysis):
    return {
        "slide_type": "cover",
        "title": lesson_request.get("course_title") or manuscript_analysis.get("main_topic") or "Lesson Title",
        "visible_content": [
            lesson_request.get("unit") or "Unit Overview",
            manuscript_analysis.get("detected_lesson_type") or lesson_request.get("lesson_type") or "Lesson Type",
            f"{lesson_request.get('grade') or '高一'} | {lesson_request.get('textbook') or '人教版'}",
        ],
        "teacher_notes": manuscript_analysis.get("summary") or "Introduce the lesson and present the topic clearly.",
        "teaching_purpose": SLIDE_PURPOSE["cover"],
        "estimated_time": "2 minutes",
        "interaction_type": "Teacher-student interaction",
    }


def _objectives_slide(lesson_structure):
    return {
        "slide_type": "objectives",
        "title": "Learning Objectives",
        "visible_content": list(lesson_structure.get("learning_objectives", []))[:4],
        "teacher_notes": "Read the objectives aloud and explain how students will reach them in the lesson.",
        "teaching_purpose": SLIDE_PURPOSE["objectives"],
        "estimated_time": "3 minutes",
        "interaction_type": "Teacher-student interaction",
    }


def _summary_slide(manuscript_analysis, lesson_structure):
    topic = manuscript_analysis.get("main_topic") or "today's topic"
    key_points = list(lesson_structure.get("key_points", []))[:2]
    visible_content = key_points + [
        f"Review one key idea about {topic}.",
        "Say one useful strategy or expression from the lesson.",
    ]
    return {
        "slide_type": "summary",
        "title": "Summary",
        "visible_content": visible_content[:4],
        "teacher_notes": "Use this slide to wrap up key learning and invite one or two short student responses.",
        "teaching_purpose": SLIDE_PURPOSE["summary"],
        "estimated_time": "3 minutes",
        "interaction_type": "Teacher-student interaction",
    }


def _homework_slide(lesson_structure):
    homework = list(lesson_structure.get("homework", []))[:3] or [
        "Review the key language from the lesson.",
        "Finish the follow-up practice after class.",
    ]
    return {
        "slide_type": "homework",
        "title": "Homework",
        "visible_content": homework,
        "teacher_notes": "Explain the expected homework output and remind students of the main focus.",
        "teaching_purpose": SLIDE_PURPOSE["homework"],
        "estimated_time": "2 minutes",
        "interaction_type": "Teacher-student interaction",
    }


def _blackboard_slide(lesson_structure):
    board = str(lesson_structure.get("blackboard_design") or "").strip()
    items = _split_points(board, limit=5) or ["Theme", "Objectives", "Key language", "Core task"]
    return {
        "slide_type": "blackboard_design",
        "title": "Blackboard Design",
        "visible_content": items,
        "teacher_notes": board or "Summarize the board structure for the lesson.",
        "teaching_purpose": SLIDE_PURPOSE["blackboard_design"],
        "estimated_time": "1 minute",
        "interaction_type": "Teacher guidance",
    }


def _step_slide(blueprint_item, step_lookup, lesson_request, manuscript_analysis, lesson_structure):
    slide_type, title, interaction_type, estimated_time, step_name = blueprint_item
    step = step_lookup.get(step_name or "") or {}
    return {
        "slide_type": slide_type,
        "title": title,
        "visible_content": _content_from_step(
            slide_type,
            step,
            lesson_request,
            lesson_structure,
            manuscript_analysis,
        )[:5],
        "teacher_notes": _teacher_notes(slide_type, step, lesson_structure, manuscript_analysis),
        "teaching_purpose": SLIDE_PURPOSE.get(slide_type, "Support a clear classroom step."),
        "estimated_time": str(step.get("estimated_time") or estimated_time).replace("min", "minutes"),
        "interaction_type": str(step.get("interaction_type") or interaction_type).strip(),
    }


def _reindex(slides):
    for index, slide in enumerate(slides, start=1):
        slide["slide_index"] = index
    return slides


def _build_rule_slides(lesson_request, manuscript_analysis, lesson_structure):
    lesson_type = normalize_lesson_type(
        manuscript_analysis.get("detected_lesson_type") or lesson_request.get("lesson_type")
    )
    blueprint = LESSON_BLUEPRINTS.get(lesson_type, LESSON_BLUEPRINTS["reading"])
    step_lookup = _step_map(lesson_structure)

    slides = []
    for item in blueprint:
        slide_type = item[0]
        if slide_type == "cover":
            slides.append(_cover_slide(lesson_request, manuscript_analysis))
        elif slide_type == "objectives":
            slides.append(_objectives_slide(lesson_structure))
        elif slide_type == "summary":
            slides.append(_summary_slide(manuscript_analysis, lesson_structure))
        elif slide_type == "homework":
            slides.append(_homework_slide(lesson_structure))
        else:
            slides.append(
                _step_slide(item, step_lookup, lesson_request, manuscript_analysis, lesson_structure)
            )

    slides.append(_blackboard_slide(lesson_structure))
    return _reindex(slides)


def generate_rule_slides_from_manuscript(lesson_request, manuscript_analysis, lesson_structure):
    """Return the local rule-based slide deck built from manuscript structure."""

    return _build_rule_slides(lesson_request, manuscript_analysis, lesson_structure)


def _normalize_visible_content(value, fallback):
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item or "").strip()]
        if cleaned:
            return cleaned[:5]
    return list(fallback)


def _normalize_slides(payload, fallback):
    candidate_slides = payload.get("slides") if isinstance(payload, dict) else payload
    if not isinstance(candidate_slides, list):
        return fallback

    normalized = []
    for index, fallback_slide in enumerate(fallback, start=1):
        candidate = (
            candidate_slides[index - 1]
            if index - 1 < len(candidate_slides) and isinstance(candidate_slides[index - 1], dict)
            else {}
        )
        normalized.append(
            {
                "slide_index": index,
                "slide_type": str(candidate.get("slide_type") or fallback_slide["slide_type"]).strip(),
                "title": str(candidate.get("title") or fallback_slide["title"]).strip(),
                "visible_content": _normalize_visible_content(
                    candidate.get("visible_content"),
                    fallback_slide["visible_content"],
                ),
                "teacher_notes": str(candidate.get("teacher_notes") or fallback_slide["teacher_notes"]).strip(),
                "teaching_purpose": str(
                    candidate.get("teaching_purpose") or fallback_slide["teaching_purpose"]
                ).strip(),
                "estimated_time": str(candidate.get("estimated_time") or fallback_slide["estimated_time"]).strip(),
                "interaction_type": str(
                    candidate.get("interaction_type") or fallback_slide["interaction_type"]
                ).strip(),
            }
        )
    return normalized


def _splitter_prompts(lesson_request, manuscript_analysis, lesson_structure, fallback):
    system_prompt = """
You convert English lesson manuscripts into concise PPT slides.
Return JSON only.
"""
    lesson_type = manuscript_analysis.get("detected_lesson_type") or lesson_request.get("lesson_type") or "Reading"
    user_prompt = f"""
Split the manuscript-based lesson into PPT slides.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Manuscript analysis:
{json.dumps(manuscript_analysis, ensure_ascii=False, indent=2)}

Lesson structure:
{json.dumps(lesson_structure, ensure_ascii=False, indent=2)}

Fallback slide draft:
{json.dumps(fallback, ensure_ascii=False, indent=2)}

Return one JSON object with a "slides" array.
Each slide must include:
- slide_index
- slide_type
- title
- visible_content
- teacher_notes
- teaching_purpose
- estimated_time
- interaction_type

Requirements:
- visible_content must stay concise and contain at most 5 items.
- Do not place full manuscript paragraphs on the slide.
- Put long explanations into teacher_notes.
- The deck must include cover, objectives, summary, and homework.
- Respect the lesson_type and use realistic senior high school English teaching flow for {lesson_type}.
"""
    return system_prompt.strip(), user_prompt.strip()


def split_manuscript_into_slides(lesson_request, manuscript_analysis, lesson_structure):
    """Split manuscript structure into PPT-ready slide JSON."""

    fallback = _build_rule_slides(lesson_request, manuscript_analysis, lesson_structure)
    system_prompt, user_prompt = _splitter_prompts(
        lesson_request,
        manuscript_analysis,
        lesson_structure,
        fallback,
    )
    payload = call_agent_json(
        "slide_splitter_agent",
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Split manuscript structure into slides.",
        },
        fallback_fn=lambda: {"slides": fallback},
    )
    return _normalize_slides(payload, fallback)


def regenerate_manuscript_slide(
    lesson_request,
    manuscript_text,
    manuscript_analysis,
    lesson_structure,
    current_slide,
    neighbor_context=None,
):
    """Regenerate one manuscript slide with manuscript text and nearby slide context."""

    fallback_slides = _build_rule_slides(lesson_request, manuscript_analysis, lesson_structure)
    target_index = int(current_slide.get("slide_index") or 1)
    fallback_slide = fallback_slides[min(max(target_index - 1, 0), len(fallback_slides) - 1)]
    neighbor_context = neighbor_context or {}

    system_prompt = """
You regenerate one PPT slide from a senior high school English manuscript.
Return JSON only.
"""
    user_prompt = f"""
Regenerate one manuscript-based slide.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Manuscript analysis:
{json.dumps(manuscript_analysis, ensure_ascii=False, indent=2)}

Lesson structure:
{json.dumps(lesson_structure, ensure_ascii=False, indent=2)}

Current slide:
{json.dumps(current_slide, ensure_ascii=False, indent=2)}

Nearby slide context:
{json.dumps(neighbor_context, ensure_ascii=False, indent=2)}

Relevant manuscript excerpt:
{manuscript_text[:2600]}

Fallback slide:
{json.dumps(fallback_slide, ensure_ascii=False, indent=2)}

Return one JSON object with exactly these keys:
- slide_index
- slide_type
- title
- visible_content
- teacher_notes
- teaching_purpose
- estimated_time
- interaction_type

Requirements:
- Keep slide_type aligned with the current page.
- visible_content must be concise and contain at most 5 items.
- Use the manuscript and nearby slide context to avoid repetition and preserve lesson flow.
- Put detailed explanation into teacher_notes, not visible_content.
"""

    payload = call_agent_json(
        "slide_splitter_agent",
        {
            "system_prompt": system_prompt.strip(),
            "user_prompt": user_prompt.strip(),
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Regenerate one manuscript slide with manuscript and neighboring slide context.",
        },
        fallback_fn=lambda: fallback_slide,
    )
    normalized = _normalize_slides({"slides": [payload]}, [fallback_slide])[0]
    normalized["slide_index"] = target_index
    normalized["slide_type"] = current_slide.get("slide_type") or normalized["slide_type"]
    return normalized
