"""PPT outline planning agent.

Current stage: hybrid local Ollama + rule-based fallback.
Future replacement: this outline planner can ask an LLM to choose slide
structure and pacing while preserving the same outline schema and fallback.
"""

import json

from services.llm_service import call_agent_json
from services.knowledge_retrieval_service import format_knowledge_context_for_prompt
from services.mock_ai_service import normalize_lesson_type


OUTLINE_TEMPLATES = {
    "reading": [
        ("cover", "Cover", "Open the lesson with a clear topic frame.", "2 minutes"),
        ("objectives", "Learning Objectives", "Show what students should achieve by the end of class.", "3 minutes"),
        ("lead_in", "Lead-in", "Activate students' background knowledge and interest.", "4 minutes"),
        ("prediction", "Prediction", "Guide students to predict content before reading.", "4 minutes"),
        ("fast_reading", "Fast Reading", "Help students read for the main idea.", "5 minutes"),
        ("careful_reading", "Careful Reading", "Lead students to find details and evidence.", "7 minutes"),
        ("vocabulary_focus", "Vocabulary Focus", "Support comprehension with useful words and phrases.", "4 minutes"),
        ("language_points", "Language Points", "Highlight reusable sentence patterns and language points.", "4 minutes"),
        ("group_discussion", "Group Discussion", "Turn reading input into classroom discussion output.", "5 minutes"),
        ("summary", "Summary", "Review the key learning of the lesson.", "3 minutes"),
        ("homework", "Homework", "Assign focused follow-up work after class.", "2 minutes"),
        ("blackboard_design", "Blackboard Design", "Present a concise board plan for the lesson.", "1 minute"),
    ],
    "grammar": [
        ("cover", "Cover", "Open the lesson with the grammar topic and context.", "2 minutes"),
        ("objectives", "Learning Objectives", "Clarify grammar learning goals for the class.", "3 minutes"),
        ("observe_discover", "Observe and Discover", "Lead students to notice grammar patterns from examples.", "4 minutes"),
        ("grammar_rule", "Grammar Rule", "Summarize the grammar form, meaning, and use.", "4 minutes"),
        ("guided_practice", "Guided Practice", "Support first attempts with sentence frames or hints.", "5 minutes"),
        ("controlled_practice", "Controlled Practice", "Strengthen grammar accuracy through focused practice.", "5 minutes"),
        ("communicative_practice", "Communicative Practice", "Move grammar into meaningful classroom communication.", "6 minutes"),
        ("error_correction", "Error Correction", "Help students notice and fix common mistakes.", "4 minutes"),
        ("summary", "Summary", "Review the grammar target and its classroom use.", "3 minutes"),
        ("homework", "Homework", "Extend grammar use after class.", "2 minutes"),
    ],
    "writing": [
        ("cover", "Cover", "Open the writing lesson and frame the final product.", "2 minutes"),
        ("objectives", "Learning Objectives", "State what students will learn and produce.", "3 minutes"),
        ("lead_in", "Lead-in", "Activate ideas before the writing task begins.", "4 minutes"),
        ("writing_task", "Writing Task", "Clarify the task, audience, and purpose.", "4 minutes"),
        ("structure_analysis", "Structure Analysis", "Help students see how to organize the writing.", "4 minutes"),
        ("useful_expressions", "Useful Expressions", "Provide sentence starters and linking language.", "4 minutes"),
        ("sample_analysis", "Sample Analysis", "Use a model to show what good writing looks like.", "4 minutes"),
        ("guided_writing", "Guided Writing", "Support drafting with structured classroom steps.", "7 minutes"),
        ("peer_review", "Peer Review", "Encourage peer feedback and revision awareness.", "4 minutes"),
        ("summary", "Summary", "Consolidate writing strategies from the lesson.", "3 minutes"),
        ("homework", "Homework", "Assign revision or extension writing after class.", "2 minutes"),
    ],
    "listening_speaking": [
        ("cover", "Cover", "Open the lesson with the listening and speaking theme.", "2 minutes"),
        ("objectives", "Learning Objectives", "Clarify listening and speaking goals for the class.", "3 minutes"),
        ("lead_in", "Lead-in", "Build interest and activate topic knowledge.", "4 minutes"),
        ("pre_listening", "Pre-listening", "Prepare students with key context and prediction.", "4 minutes"),
        ("while_listening", "While-listening", "Guide students through gist and detail listening tasks.", "6 minutes"),
        ("post_listening", "Post-listening", "Check understanding and connect input to output.", "5 minutes"),
        ("speaking_task", "Speaking Task", "Turn listening input into spoken classroom performance.", "6 minutes"),
        ("pair_work", "Pair Work", "Increase student talk through guided pair interaction.", "4 minutes"),
        ("summary", "Summary", "Review useful listening and speaking strategies.", "3 minutes"),
        ("homework", "Homework", "Assign focused listening or speaking follow-up work.", "2 minutes"),
    ],
    "revision": [
        ("cover", "Cover", "Open the revision lesson with a clear unit focus.", "2 minutes"),
        ("objectives", "Learning Objectives", "Clarify the revision targets for the period.", "3 minutes"),
        ("key_vocabulary_review", "Key Vocabulary Review", "Retrieve high-frequency words and phrases.", "4 minutes"),
        ("key_grammar_review", "Key Grammar Review", "Refresh the core grammar of the unit.", "4 minutes"),
        ("exercise_practice", "Exercise Practice", "Use guided exercises to check understanding.", "5 minutes"),
        ("error_analysis", "Error Analysis", "Review typical mistakes and how to avoid them.", "4 minutes"),
        ("consolidation", "Consolidation", "Help students organize and apply reviewed knowledge.", "5 minutes"),
        ("summary", "Summary", "Review the main revision outcomes of the lesson.", "3 minutes"),
        ("homework", "Homework", "Assign targeted revision after class.", "2 minutes"),
    ],
}


def _build_rule_ppt_outline(lesson_request, teaching_design):
    lesson_key = normalize_lesson_type(lesson_request.get("lesson_type"))
    template = OUTLINE_TEMPLATES.get(lesson_key, OUTLINE_TEMPLATES["reading"])

    outline = []
    for slide_index, (slide_type, title, purpose, estimated_time) in enumerate(template, start=1):
        teaching_purpose = purpose
        if slide_type == "objectives":
            teaching_purpose = "Present the measurable objectives from the teaching design."
        elif slide_type == "summary":
            teaching_purpose = teaching_design.get("lesson_flow_summary") or purpose

        outline.append(
            {
                "slide_index": slide_index,
                "slide_type": slide_type,
                "title": title,
                "teaching_purpose": teaching_purpose,
                "estimated_time": estimated_time,
            }
        )

    return outline


def generate_rule_ppt_outline(lesson_request, teaching_design):
    """Return the local rule-based PPT outline without any model call."""

    return _build_rule_ppt_outline(lesson_request, teaching_design)


def _normalize_time(value, fallback):
    text = str(value or "").strip()
    return text or fallback


def _normalize_outline(payload, fallback):
    if isinstance(payload, dict):
        candidate_slides = payload.get("slides")
    else:
        candidate_slides = payload

    if not isinstance(candidate_slides, list):
        return fallback

    normalized = []
    for index, fallback_slide in enumerate(fallback):
        candidate = candidate_slides[index] if index < len(candidate_slides) and isinstance(candidate_slides[index], dict) else {}
        normalized.append(
            {
                "slide_index": fallback_slide["slide_index"],
                "slide_type": fallback_slide["slide_type"],
                "title": str(candidate.get("title") or fallback_slide["title"]).strip(),
                "teaching_purpose": str(
                    candidate.get("teaching_purpose") or fallback_slide["teaching_purpose"]
                ).strip(),
                "estimated_time": _normalize_time(
                    candidate.get("estimated_time"),
                    fallback_slide["estimated_time"],
                ),
            }
        )

    return normalized


def _knowledge_context_block(knowledge_context):
    if not knowledge_context:
        return ""
    return "\n\n" + format_knowledge_context_for_prompt(knowledge_context)


def _outline_prompts(lesson_request, teaching_design, fallback, knowledge_context=None):
    system_prompt = """
You are a senior high school English PPT lesson planner.
Return JSON only.
Write slide titles and teaching purposes in concise classroom English.
"""
    user_prompt = f"""
Plan the PPT outline for this lesson.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Teaching design:
{json.dumps(teaching_design, ensure_ascii=False, indent=2)}

Required slide structure and order:
{json.dumps(fallback, ensure_ascii=False, indent=2)}

{_knowledge_context_block(knowledge_context)}

Return one JSON object with a "slides" array.
Each slide must include:
- slide_index
- slide_type
- title
- teaching_purpose
- estimated_time

Requirements:
- Keep the same number of slides and the same slide_type order as the required structure.
- Improve title wording and teaching purpose wording where helpful.
- Keep each estimated_time concise, such as "3 minutes".
- Do not add markdown or explanations.
"""
    return system_prompt.strip(), user_prompt.strip()


def generate_ppt_outline(lesson_request, teaching_design, knowledge_context=None):
    """Generate a lesson-type-specific slide outline."""

    fallback = _build_rule_ppt_outline(lesson_request, teaching_design)
    knowledge_context = knowledge_context or lesson_request.get("knowledge_context")
    system_prompt, user_prompt = _outline_prompts(
        lesson_request,
        teaching_design,
        fallback,
        knowledge_context=knowledge_context,
    )
    payload = call_agent_json(
        "ppt_outline_agent",
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Plan the PPT outline.",
        },
        fallback_fn=lambda: fallback,
    )
    return _normalize_outline(payload, fallback)
