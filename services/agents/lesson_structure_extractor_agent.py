"""Lesson structure extractor agent.

Current stage: hybrid Ollama + rule-based fallback.
Future replacement: this extractor can be backed by stronger models while
keeping the same structured output for manuscript-based generation.
"""

import json
import re

from services.llm_service import call_agent_json, trim_knowledge_context_for_prompt
from services.knowledge_retrieval_service import format_knowledge_context_for_prompt
from services.mock_ai_service import normalize_lesson_type


SECTION_KEYWORDS = {
    "learning_objectives": ["教学目标", "learning objectives", "objectives"],
    "key_points": ["教学重点", "key points", "重点"],
    "difficult_points": ["教学难点", "difficult points", "难点"],
    "lead_in": ["导入", "lead-in", "warming up", "warm-up"],
    "prediction": ["prediction", "预测"],
    "fast_reading": ["fast reading", "skimming", "略读"],
    "careful_reading": ["careful reading", "scan", "细读"],
    "vocabulary_focus": ["词汇", "vocabulary", "phrases"],
    "language_points": ["language points", "句型", "表达", "useful language"],
    "grammar_rule": ["grammar rule", "语法规则", "rule", "sentence pattern"],
    "guided_practice": ["guided practice", "操练", "practice", "drill"],
    "writing_task": ["writing task", "写作任务", "写作要求"],
    "structure_analysis": ["structure analysis", "结构分析", "outline"],
    "useful_expressions": ["useful expressions", "亮点表达", "sentence starters"],
    "group_discussion": ["discussion", "讨论", "pair work", "group work", "activity"],
    "summary": ["summary", "课堂小结", "总结", "reflection"],
    "homework": ["homework", "作业"],
    "blackboard_design": ["board", "blackboard", "板书"],
}

STEP_LIBRARY = {
    "reading": [
        ("Lead-in", "4 minutes", "Teacher-student interaction"),
        ("Prediction", "4 minutes", "Pair work"),
        ("Fast Reading", "6 minutes", "Individual work"),
        ("Careful Reading", "8 minutes", "Teacher-student interaction"),
        ("Vocabulary Focus", "5 minutes", "Teacher-student interaction"),
        ("Language Points", "5 minutes", "Teacher-student interaction"),
        ("Discussion", "5 minutes", "Group discussion"),
        ("Summary", "3 minutes", "Teacher-student interaction"),
    ],
    "grammar": [
        ("Lead-in", "4 minutes", "Teacher-student interaction"),
        ("Observe and Discover", "5 minutes", "Teacher-student interaction"),
        ("Grammar Rule", "5 minutes", "Teacher guidance"),
        ("Guided Practice", "6 minutes", "Individual work"),
        ("Controlled Practice", "6 minutes", "Pair work"),
        ("Communicative Practice", "6 minutes", "Pair work"),
        ("Summary", "3 minutes", "Teacher-student interaction"),
    ],
    "writing": [
        ("Lead-in", "4 minutes", "Teacher-student interaction"),
        ("Writing Task", "4 minutes", "Teacher-student interaction"),
        ("Structure Analysis", "5 minutes", "Teacher guidance"),
        ("Useful Expressions", "5 minutes", "Teacher-student interaction"),
        ("Guided Writing", "8 minutes", "Individual work"),
        ("Peer Review", "5 minutes", "Pair work"),
        ("Summary", "3 minutes", "Teacher-student interaction"),
    ],
    "listening_speaking": [
        ("Lead-in", "4 minutes", "Teacher-student interaction"),
        ("Pre-listening", "4 minutes", "Teacher-student interaction"),
        ("While-listening", "7 minutes", "Individual work"),
        ("Post-listening", "5 minutes", "Teacher-student interaction"),
        ("Speaking Task", "6 minutes", "Pair work"),
        ("Pair Work", "5 minutes", "Pair work"),
        ("Summary", "3 minutes", "Teacher-student interaction"),
    ],
    "revision": [
        ("Lead-in", "4 minutes", "Teacher-student interaction"),
        ("Key Vocabulary Review", "5 minutes", "Teacher-student interaction"),
        ("Key Grammar Review", "5 minutes", "Teacher guidance"),
        ("Exercise Practice", "7 minutes", "Individual work"),
        ("Error Analysis", "5 minutes", "Teacher-student interaction"),
        ("Consolidation", "6 minutes", "Pair work"),
        ("Summary", "3 minutes", "Teacher-student interaction"),
    ],
}

STEP_SOURCE_KEYS = {
    "Lead-in": ["lead_in"],
    "Prediction": ["prediction"],
    "Fast Reading": ["fast_reading"],
    "Careful Reading": ["careful_reading"],
    "Vocabulary Focus": ["vocabulary_focus"],
    "Language Points": ["language_points", "vocabulary_focus"],
    "Discussion": ["group_discussion"],
    "Observe and Discover": ["grammar_rule", "language_points"],
    "Grammar Rule": ["grammar_rule"],
    "Guided Practice": ["guided_practice"],
    "Controlled Practice": ["guided_practice"],
    "Communicative Practice": ["group_discussion", "guided_practice"],
    "Writing Task": ["writing_task"],
    "Structure Analysis": ["structure_analysis", "writing_task"],
    "Useful Expressions": ["useful_expressions", "language_points", "vocabulary_focus"],
    "Guided Writing": ["writing_task"],
    "Peer Review": ["group_discussion"],
    "Pre-listening": ["lead_in"],
    "While-listening": ["fast_reading", "careful_reading"],
    "Post-listening": ["group_discussion", "summary"],
    "Speaking Task": ["group_discussion"],
    "Pair Work": ["group_discussion"],
    "Key Vocabulary Review": ["vocabulary_focus"],
    "Key Grammar Review": ["grammar_rule"],
    "Exercise Practice": ["guided_practice"],
    "Error Analysis": ["group_discussion", "guided_practice"],
    "Consolidation": ["summary", "group_discussion"],
    "Summary": ["summary"],
}


def _paragraphs(text):
    return [block.strip() for block in re.split(r"\n{2,}", str(text or "")) if block.strip()]


def _normalize_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _is_heading(paragraph):
    paragraph = str(paragraph or "").strip()
    if not paragraph:
        return False
    if len(paragraph) <= 30 and not paragraph.endswith((".", "?", "!", "。", "？", "！", "：", ":")):
        return True
    return False


def _short_excerpt(text, limit=220):
    cleaned = _normalize_spaces(text)
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[:limit].rstrip()}..."


def _split_blocks_to_points(blocks, fallback, limit=4):
    items = []
    for block in blocks:
        for piece in re.split(r"[\n;；]|(?<=[。.!?])\s+", str(block)):
            cleaned = piece.strip(" -•\t")
            if cleaned:
                items.append(_short_excerpt(cleaned, limit=90))
    return items[:limit] or list(fallback)


def _find_section_content(manuscript_text, keywords):
    paragraphs = _paragraphs(manuscript_text)
    if not paragraphs:
        return []

    matched = []
    for index, paragraph in enumerate(paragraphs):
        lower_paragraph = paragraph.lower()
        if any(keyword.lower() in lower_paragraph for keyword in keywords):
            follower_blocks = []
            for follower in paragraphs[index + 1:index + 4]:
                if _is_heading(follower):
                    break
                follower_blocks.append(follower)
            matched.extend(follower_blocks or [paragraph])
    return matched


def _collect_section_map(manuscript_text):
    return {
        name: _find_section_content(manuscript_text, keywords)
        for name, keywords in SECTION_KEYWORDS.items()
    }


def _default_objectives(main_topic, lesson_type):
    defaults = {
        "reading": [
            f"Understand the main idea and key details about {main_topic}.",
            "Use text evidence to answer reading questions.",
            "Complete one short reading-based output task.",
        ],
        "grammar": [
            "Notice the target grammar form and usage in context.",
            "Summarize the grammar rule with examples.",
            "Use the target language in short practice and communication.",
        ],
        "writing": [
            "Understand the writing task, purpose, and audience.",
            "Use a clear structure and useful expressions to draft.",
            "Improve writing through peer feedback and revision.",
        ],
        "listening_speaking": [
            "Catch key information from the input material.",
            "Use useful expressions to respond and interact.",
            "Transform input into short speaking output.",
        ],
        "revision": [
            "Review key vocabulary and grammar efficiently.",
            "Correct common mistakes with clear reasons.",
            "Apply reviewed content in a short consolidation task.",
        ],
    }
    return defaults.get(lesson_type, defaults["reading"])


def _default_key_points(main_topic, lesson_type):
    defaults = {
        "reading": [
            f"Understand the text around {main_topic}.",
            "Locate supporting details quickly.",
            "Use reading input in discussion.",
        ],
        "grammar": [
            "Observe the grammar pattern in context.",
            "Clarify form, meaning, and use.",
            "Practice accurate use in short tasks.",
        ],
        "writing": [
            "Clarify writing structure and support.",
            "Use practical expressions and transitions.",
            "Develop ideas with a simple scaffold.",
        ],
        "listening_speaking": [
            "Listen for gist and detail.",
            "Use key expressions in speaking tasks.",
            "Encourage visible student participation.",
        ],
        "revision": [
            "Review high-frequency language points.",
            "Fix common errors through examples.",
            "Consolidate knowledge in mixed practice.",
        ],
    }
    return defaults.get(lesson_type, defaults["reading"])


def _default_difficult_points(lesson_type):
    defaults = {
        "reading": [
            "Move from comprehension to evidence-based answers.",
            "Use key expressions naturally in discussion.",
            "Support deeper thinking with text details.",
        ],
        "grammar": [
            "Explain and apply the rule clearly.",
            "Avoid common confusion or misuse.",
            "Transfer grammar knowledge into output.",
        ],
        "writing": [
            "Organize ideas logically.",
            "Use appropriate sentence patterns and links.",
            "Move from scaffold to independent drafting.",
        ],
        "listening_speaking": [
            "Catch key points without translating every word.",
            "Turn input into spoken output.",
            "Maintain confidence in pair interaction.",
        ],
        "revision": [
            "Retrieve language quickly and accurately.",
            "Explain correction reasons clearly.",
            "Connect reviewed content to new tasks.",
        ],
    }
    return defaults.get(lesson_type, defaults["reading"])


def _guess_from_paragraphs(paragraphs, prompt):
    prompt_tokens = set(re.findall(r"[a-z]+", prompt.lower()))
    best = ""
    best_score = -1
    for paragraph in paragraphs:
        tokens = set(re.findall(r"[a-z]+", paragraph.lower()))
        score = len(tokens & prompt_tokens)
        if score > best_score:
            best_score = score
            best = paragraph
    return best


def _step_content(step_name, section_map, paragraphs, lesson_request, main_topic):
    source_keys = STEP_SOURCE_KEYS.get(step_name, [])
    blocks = []
    for source_key in source_keys:
        blocks.extend(section_map.get(source_key, []))
    if blocks:
        return _short_excerpt(" ".join(blocks), limit=260)

    guessed = _guess_from_paragraphs(paragraphs, step_name)
    if guessed:
        return _short_excerpt(guessed, limit=260)

    topic = lesson_request.get("topic") or lesson_request.get("course_title") or main_topic
    fallback_lines = {
        "Prediction": f"Invite students to predict key ideas about {topic} from title cues or topic hints.",
        "Fast Reading": f"Guide students to skim the material about {topic} for gist and structure.",
        "Careful Reading": "Focus on important details, evidence, and key questions from the text.",
        "Vocabulary Focus": "Highlight useful words, phrases, and sentence chunks needed for understanding.",
        "Language Points": "Explain one or two useful language points with simple examples.",
        "Discussion": "Use one meaningful discussion question to connect text understanding with personal response.",
        "Grammar Rule": "Extract the grammar rule from examples and make the use clear.",
        "Writing Task": "Clarify the writing purpose, audience, and expected output.",
        "Structure Analysis": "Show how the writing should be organized into clear parts.",
        "Useful Expressions": "Provide sentence starters, linking words, and useful expressions.",
    }
    return fallback_lines.get(step_name, f"Guide students through {step_name.lower()} with content linked to {topic}.")


def _merge_required_steps(lesson_type, section_map, paragraphs, lesson_request, main_topic):
    steps = []
    for step_name, estimated_time, interaction_type in STEP_LIBRARY.get(lesson_type, STEP_LIBRARY["reading"]):
        steps.append(
            {
                "step_name": step_name,
                "content": _step_content(step_name, section_map, paragraphs, lesson_request, main_topic),
                "estimated_time": estimated_time,
                "interaction_type": interaction_type,
            }
        )
    return steps


def _blackboard_design(section_map, main_topic):
    board_blocks = section_map.get("blackboard_design", [])
    if board_blocks:
        return _short_excerpt(" ".join(board_blocks), limit=180)
    return f"Theme: {main_topic}; Objectives; Key language; Core task; Homework."


def _build_rule_structure(lesson_request, manuscript_text, manuscript_analysis):
    lesson_type = normalize_lesson_type(
        manuscript_analysis.get("detected_lesson_type") or lesson_request.get("lesson_type")
    )
    main_topic = manuscript_analysis.get("main_topic") or lesson_request.get("topic") or "the lesson topic"
    section_map = _collect_section_map(manuscript_text)
    paragraphs = _paragraphs(manuscript_text)

    learning_objectives = _split_blocks_to_points(
        section_map.get("learning_objectives", []),
        _default_objectives(main_topic, lesson_type),
        limit=4,
    )
    key_points = _split_blocks_to_points(
        section_map.get("key_points", []),
        _default_key_points(main_topic, lesson_type),
        limit=4,
    )
    difficult_points = _split_blocks_to_points(
        section_map.get("difficult_points", []),
        _default_difficult_points(lesson_type),
        limit=4,
    )
    homework = _split_blocks_to_points(
        section_map.get("homework", []),
        ["Review the key language from the lesson.", "Finish the follow-up task after class."],
        limit=3,
    )

    steps = _merge_required_steps(lesson_type, section_map, paragraphs, lesson_request, main_topic)

    return {
        "learning_objectives": learning_objectives,
        "key_points": key_points,
        "difficult_points": difficult_points,
        "teaching_steps": steps,
        "homework": homework,
        "blackboard_design": _blackboard_design(section_map, main_topic),
    }


def generate_rule_lesson_structure(lesson_request, manuscript_text, manuscript_analysis):
    """Return the local rule-based lesson structure extracted from manuscript text."""

    return _build_rule_structure(lesson_request, manuscript_text, manuscript_analysis)


def _normalize_string_list(value, fallback, limit=4):
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item or "").strip()]
        if cleaned:
            return cleaned[:limit]
    return list(fallback)


def _normalize_teaching_steps(value, fallback):
    if not isinstance(value, list):
        return fallback
    normalized = []
    for index, fallback_step in enumerate(fallback):
        candidate = value[index] if index < len(value) and isinstance(value[index], dict) else {}
        normalized.append(
            {
                "step_name": str(candidate.get("step_name") or fallback_step["step_name"]).strip(),
                "content": str(candidate.get("content") or fallback_step["content"]).strip(),
                "estimated_time": str(candidate.get("estimated_time") or fallback_step["estimated_time"]).strip(),
                "interaction_type": str(
                    candidate.get("interaction_type") or fallback_step["interaction_type"]
                ).strip(),
            }
        )
    return normalized


def _normalize_structure(payload, fallback):
    payload = payload if isinstance(payload, dict) else {}
    return {
        "learning_objectives": _normalize_string_list(
            payload.get("learning_objectives"),
            fallback["learning_objectives"],
        ),
        "key_points": _normalize_string_list(payload.get("key_points"), fallback["key_points"]),
        "difficult_points": _normalize_string_list(
            payload.get("difficult_points"),
            fallback["difficult_points"],
        ),
        "teaching_steps": _normalize_teaching_steps(payload.get("teaching_steps"), fallback["teaching_steps"]),
        "homework": _normalize_string_list(payload.get("homework"), fallback["homework"], limit=3),
        "blackboard_design": str(payload.get("blackboard_design") or fallback["blackboard_design"]).strip(),
    }


def _knowledge_context_block(knowledge_context):
    if not knowledge_context:
        return ""
    return "\n\n" + trim_knowledge_context_for_prompt(format_knowledge_context_for_prompt(knowledge_context), max_chars=4000)


def _structure_prompts(lesson_request, manuscript_text, manuscript_analysis, fallback, knowledge_context=None):
    system_prompt = """
You extract senior high school English lesson structure from manuscripts.
Return JSON only.
"""
    user_prompt = f"""
Extract a usable lesson structure for PPT generation.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Manuscript analysis:
{json.dumps(manuscript_analysis, ensure_ascii=False, indent=2)}

Manuscript:
{manuscript_text[:6000]}

Fallback structure:
{json.dumps(fallback, ensure_ascii=False, indent=2)}

{_knowledge_context_block(knowledge_context)}

Return one JSON object with exactly these keys:
- learning_objectives
- key_points
- difficult_points
- teaching_steps
- homework
- blackboard_design

Each item in teaching_steps must include:
- step_name
- content
- estimated_time
- interaction_type

Requirements:
- Recognize learning objectives, key points, difficult points, lead-in, reading or grammar or writing tasks, classroom activity, summary, homework, and blackboard design where possible.
- If the manuscript misses some steps, complete them according to the lesson_type.
- Keep each step content practical for a real senior high school English class.
"""
    return system_prompt.strip(), user_prompt.strip()


def extract_lesson_structure(lesson_request, manuscript_text, manuscript_analysis, knowledge_context=None):
    """Extract a teaching structure from the manuscript text."""

    fallback = _build_rule_structure(lesson_request, manuscript_text, manuscript_analysis)
    system_prompt, user_prompt = _structure_prompts(
        lesson_request,
        manuscript_text,
        manuscript_analysis,
        fallback,
        knowledge_context=knowledge_context,
    )
    payload = call_agent_json(
        "lesson_structure_extractor_agent",
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Extract lesson structure from manuscript.",
        },
        fallback_fn=lambda: fallback,
    )
    return _normalize_structure(payload, fallback)
