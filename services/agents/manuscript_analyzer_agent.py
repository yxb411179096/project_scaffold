"""Manuscript analyzer agent.

Current stage: hybrid Ollama + rule-based fallback.
Future replacement: this agent can be upgraded to stronger hosted or local
models without changing the output schema or the manuscript pipeline.
"""

import json
import re

from services.llm_service import call_agent_json, trim_knowledge_context_for_prompt
from services.knowledge_retrieval_service import format_knowledge_context_for_prompt
from services.mock_ai_service import normalize_lesson_type


LESSON_TYPE_KEYWORDS = {
    "Reading": ["reading", "read", "课文", "阅读", "skim", "scan", "main idea", "prediction"],
    "Grammar": ["grammar", "语法", "rule", "tense", "sentence pattern", "observe and discover"],
    "Writing": ["writing", "写作", "draft", "composition", "peer review", "useful expressions"],
    "Listening and Speaking": ["listening", "speaking", "听说", "listen", "pair work", "dialogue"],
    "Revision": ["revision", "review", "复习", "exercise practice", "error analysis"],
}

MANUSCRIPT_TYPE_KEYWORDS = {
    "说课稿": ["说课稿", "teaching philosophy", "design concept", "学情分析", "教材分析"],
    "教案": ["教学目标", "teaching objectives", "教学过程", "导入", "summary", "homework"],
    "讲稿": ["teacher notes", "good morning everyone", "today we are going to", "板书", "讲解"],
    "课文": ["passage", "text", "paragraph", "课文", "article", "author", "title"],
    "练习材料": ["choose the best answer", "fill in the blanks", "练习", "multiple choice", "error correction"],
}

SECTION_SIGNATURES = {
    "Learning Objectives": ["教学目标", "learning objectives", "objectives"],
    "Key Points": ["教学重点", "key points", "重点"],
    "Difficult Points": ["教学难点", "difficult points", "难点"],
    "Lead-in": ["导入", "lead-in", "warming up", "warm-up"],
    "Prediction": ["prediction", "预测"],
    "Fast Reading": ["fast reading", "skimming", "略读"],
    "Careful Reading": ["careful reading", "scan", "细读"],
    "Vocabulary Focus": ["词汇", "vocabulary", "phrase bank"],
    "Grammar Rule": ["grammar rule", "语法规则", "rule"],
    "Writing Task": ["writing task", "写作任务", "写作要求"],
    "Classroom Activity": ["activity", "task", "discussion", "pair work", "group work", "practice", "练习"],
    "Summary": ["summary", "课堂小结", "总结", "reflection"],
    "Homework": ["homework", "作业"],
    "Blackboard Design": ["blackboard", "board plan", "板书"],
}

EXPECTED_SECTIONS = {
    "reading": [
        "Learning Objectives",
        "Lead-in",
        "Prediction",
        "Fast Reading",
        "Careful Reading",
        "Vocabulary Focus",
        "Summary",
        "Homework",
    ],
    "grammar": [
        "Learning Objectives",
        "Lead-in",
        "Grammar Rule",
        "Classroom Activity",
        "Summary",
        "Homework",
    ],
    "writing": [
        "Learning Objectives",
        "Lead-in",
        "Writing Task",
        "Classroom Activity",
        "Summary",
        "Homework",
    ],
    "listening_speaking": [
        "Learning Objectives",
        "Lead-in",
        "Classroom Activity",
        "Summary",
        "Homework",
    ],
    "revision": [
        "Learning Objectives",
        "Key Points",
        "Grammar Rule",
        "Classroom Activity",
        "Summary",
        "Homework",
    ],
}


def _paragraphs(manuscript_text):
    return [block.strip() for block in re.split(r"\n{2,}", str(manuscript_text or "")) if block.strip()]


def _normalize_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _word_count(text):
    english_tokens = re.findall(r"[A-Za-z0-9']+", str(text or ""))
    chinese_tokens = re.findall(r"[\u4e00-\u9fff]", str(text or ""))
    return len(english_tokens) + len(chinese_tokens)


def _count_matches(text, keywords):
    lower_text = str(text or "").lower()
    return sum(1 for keyword in keywords if keyword.lower() in lower_text)


def _detect_manuscript_type(manuscript_text):
    scores = {
        manuscript_type: _count_matches(manuscript_text, keywords)
        for manuscript_type, keywords in MANUSCRIPT_TYPE_KEYWORDS.items()
    }
    best_type = max(scores, key=scores.get) if scores else "综合材料"
    return best_type if scores.get(best_type, 0) > 0 else "综合材料"


def _detect_lesson_type(lesson_request, manuscript_text):
    requested = str(lesson_request.get("lesson_type") or "").strip()
    if requested and requested != "Other":
        return requested

    lower_text = str(manuscript_text or "").lower()
    scored = {
        lesson_type: sum(2 if keyword.lower() in lower_text else 0 for keyword in keywords)
        for lesson_type, keywords in LESSON_TYPE_KEYWORDS.items()
    }
    best_type = max(scored, key=scored.get) if scored else "Reading"
    return best_type if scored.get(best_type, 0) > 0 else "Reading"


def _main_topic(lesson_request, manuscript_text):
    topic = str(lesson_request.get("topic") or lesson_request.get("course_title") or "").strip()
    if topic:
        return topic

    for paragraph in _paragraphs(manuscript_text):
        cleaned = _normalize_spaces(paragraph)
        if len(cleaned) <= 80 and not cleaned.endswith((".", "?", "!", "。", "？", "！")):
            return cleaned
    paragraphs = _paragraphs(manuscript_text)
    return paragraphs[0][:80] if paragraphs else "Senior English Lesson"


def _detect_sections(manuscript_text, lesson_type):
    lower_text = str(manuscript_text or "").lower()
    detected = []
    for section_name, keywords in SECTION_SIGNATURES.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            detected.append(section_name)

    detected = detected[:10]
    expected = EXPECTED_SECTIONS.get(normalize_lesson_type(lesson_type), EXPECTED_SECTIONS["reading"])
    missing = [section for section in expected if section not in detected]

    if not detected:
        detected = ["Topic Overview", "Core Teaching Content", "Summary"]
    return detected, missing[:8]


def _content_density(manuscript_text):
    paragraphs = _paragraphs(manuscript_text)
    if not paragraphs:
        return "light"
    total_words = _word_count(manuscript_text)
    average = total_words / max(len(paragraphs), 1)
    if total_words >= 1400 or average >= 85:
        return "dense"
    if total_words >= 650 or average >= 45:
        return "moderate"
    return "light"


def _summary(manuscript_text):
    paragraphs = _paragraphs(manuscript_text)
    if not paragraphs:
        return "The manuscript provides classroom content that can be reorganized into a lesson deck."
    source = _normalize_spaces(" ".join(paragraphs[:2]))
    return source[:220] + ("..." if len(source) > 220 else "")


def _organization_suggestion(detected_sections, missing_sections, density):
    if len(detected_sections) <= 3 or len(missing_sections) >= 4:
        return "原文结构较松散，建议按“导入-输入-任务-输出-总结-作业”重组，并把长段解释移入 teacher_notes。"
    if density == "dense":
        return "原文信息密度较高，建议优先抽取关键词、问题链和课堂任务，避免整段文字上屏。"
    return "原文结构较完整，可保留主要教学环节，并压缩为任务卡与关键词呈现。"


def _recommended_strategy(lesson_type, density, missing_sections):
    lesson_key = normalize_lesson_type(lesson_type)
    action = "优先抽取标题、关键词和任务指令，再压缩为 PPT 页面。"
    if density == "dense":
        action = "先抽取关键信息与课堂任务，再把长段解释移入 teacher_notes。"
    elif len(missing_sections) >= 3:
        action = "按标准课堂流程重建页面，再补齐缺失教学环节。"

    focus = {
        "reading": "重点形成预测、略读、细读、词汇和讨论页面。",
        "grammar": "重点形成观察、规则、操练和交际练习页面。",
        "writing": "重点形成写作任务、结构分析、表达支架和同伴互评页面。",
        "listening_speaking": "重点形成听前、听中、听后和口语输出页面。",
        "revision": "重点形成词汇复习、语法复习、练习和错因分析页面。",
    }.get(lesson_key, "重点形成清晰的课堂流程与任务页面。")
    return f"{action}{focus}"


def _suggested_slide_count(manuscript_text, detected_lesson_type, density):
    base = {
        "Reading": 11,
        "Grammar": 10,
        "Writing": 10,
        "Listening and Speaking": 10,
        "Revision": 9,
    }.get(detected_lesson_type, 10)
    if density == "dense":
        base += 1
    if _word_count(manuscript_text) < 220:
        base -= 1
    return max(8, min(base, 15))


def _build_rule_analysis(lesson_request, manuscript_text):
    detected_lesson_type = _detect_lesson_type(lesson_request, manuscript_text)
    detected_sections, missing_sections = _detect_sections(manuscript_text, detected_lesson_type)
    density = _content_density(manuscript_text)
    return {
        "manuscript_type": _detect_manuscript_type(manuscript_text),
        "main_topic": _main_topic(lesson_request, manuscript_text),
        "detected_lesson_type": detected_lesson_type,
        "detected_sections": detected_sections,
        "missing_sections": missing_sections,
        "content_density": density,
        "recommended_generation_strategy": _recommended_strategy(
            detected_lesson_type,
            density,
            missing_sections,
        ),
        "organization_suggestion": _organization_suggestion(
            detected_sections,
            missing_sections,
            density,
        ),
        "key_sections": list(detected_sections),
        "summary": _summary(manuscript_text),
        "suggested_slide_count": _suggested_slide_count(
            manuscript_text,
            detected_lesson_type,
            density,
        ),
    }


def generate_rule_manuscript_analysis(lesson_request, manuscript_text):
    """Return the local rule-based manuscript analysis."""

    return _build_rule_analysis(lesson_request, manuscript_text)


def _normalize_string_list(value, fallback, limit=10):
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item or "").strip()]
        if cleaned:
            return cleaned[:limit]
    return list(fallback)


def _normalize_analysis(payload, fallback):
    payload = payload if isinstance(payload, dict) else {}
    detected_lesson_type = str(
        payload.get("detected_lesson_type") or fallback["detected_lesson_type"]
    ).strip()
    if normalize_lesson_type(detected_lesson_type) == "reading" and detected_lesson_type not in {
        "Reading",
        "Grammar",
        "Writing",
        "Listening and Speaking",
        "Revision",
        "Other",
    }:
        detected_lesson_type = fallback["detected_lesson_type"]

    try:
        suggested_slide_count = int(payload.get("suggested_slide_count"))
    except (TypeError, ValueError):
        suggested_slide_count = fallback["suggested_slide_count"]
    suggested_slide_count = max(8, min(suggested_slide_count, 16))

    content_density = str(payload.get("content_density") or fallback["content_density"]).strip().lower()
    if content_density not in {"light", "moderate", "dense"}:
        content_density = fallback["content_density"]

    detected_sections = _normalize_string_list(
        payload.get("detected_sections") or payload.get("key_sections"),
        fallback["detected_sections"],
    )
    missing_sections = _normalize_string_list(
        payload.get("missing_sections"),
        fallback["missing_sections"],
    )

    return {
        "manuscript_type": str(payload.get("manuscript_type") or fallback["manuscript_type"]).strip(),
        "main_topic": str(payload.get("main_topic") or fallback["main_topic"]).strip(),
        "detected_lesson_type": detected_lesson_type,
        "detected_sections": detected_sections,
        "missing_sections": missing_sections,
        "content_density": content_density,
        "recommended_generation_strategy": str(
            payload.get("recommended_generation_strategy")
            or fallback["recommended_generation_strategy"]
        ).strip(),
        "organization_suggestion": str(
            payload.get("organization_suggestion") or fallback["organization_suggestion"]
        ).strip(),
        "key_sections": list(detected_sections),
        "summary": str(payload.get("summary") or fallback["summary"]).strip(),
        "suggested_slide_count": suggested_slide_count,
    }


def _knowledge_context_block(knowledge_context):
    if not knowledge_context:
        return ""
    return "\n\n" + trim_knowledge_context_for_prompt(format_knowledge_context_for_prompt(knowledge_context), max_chars=4000)


def _analysis_prompts(lesson_request, manuscript_text, fallback, knowledge_context=None):
    system_prompt = """
You analyze senior high school English manuscripts and turn them into structured metadata.
Return JSON only.
"""
    user_prompt = f"""
Analyze this manuscript for PPT generation.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Manuscript:
{manuscript_text[:5000]}

Fallback analysis:
{json.dumps(fallback, ensure_ascii=False, indent=2)}

{_knowledge_context_block(knowledge_context)}

Return one JSON object with exactly these keys:
- manuscript_type
- main_topic
- detected_lesson_type
- detected_sections
- missing_sections
- content_density
- recommended_generation_strategy
- organization_suggestion
- summary
- suggested_slide_count

Requirements:
- Keep detected_lesson_type within: Reading, Grammar, Writing, Listening and Speaking, Revision, Other.
- detected_sections and missing_sections should be concise arrays.
- content_density must be one of: light, moderate, dense.
- recommended_generation_strategy should describe how to turn the manuscript into teaching slides.
- If the manuscript structure is messy, organization_suggestion should tell the teacher how the system will reorganize it.
"""
    return system_prompt.strip(), user_prompt.strip()


def analyze_manuscript(lesson_request, manuscript_text, knowledge_context=None):
    """Analyze a manuscript and return structural metadata."""

    fallback = _build_rule_analysis(lesson_request, manuscript_text)
    system_prompt, user_prompt = _analysis_prompts(
        lesson_request,
        manuscript_text,
        fallback,
        knowledge_context=knowledge_context,
    )
    payload = call_agent_json(
        "manuscript_analyzer_agent",
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Analyze manuscript type and high-level structure.",
        },
        fallback_fn=lambda: fallback,
    )
    return _normalize_analysis(payload, fallback)
