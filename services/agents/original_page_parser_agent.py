"""Original page parser agent.

Current stage: hybrid Ollama + rule-based fallback.
Future replacement: this parser can be upgraded to stronger models without
changing the slide schema used by preserve-original-pages mode.
"""

import json
import re

from services.llm_service import call_agent_json


PAGE_MARKER_PATTERNS = [
    re.compile(r"^\s*(第\s*\d+\s*页)\s*[:：.\-]?\s*(.*)$", re.IGNORECASE),
    re.compile(r"^\s*(page\s*\d+)\s*[:：.\-]?\s*(.*)$", re.IGNORECASE),
    re.compile(r"^\s*(slide\s*\d+)\s*[:：.\-]?\s*(.*)$", re.IGNORECASE),
    re.compile(r"^\s*(幻灯片\s*\d+)\s*[:：.\-]?\s*(.*)$", re.IGNORECASE),
]
HEADING_PATTERN = re.compile(r"^\s*([一二三四五六七八九十]+)[、.．]\s*(.+)$")

FIELD_PATTERNS = {
    "teacher_notes": [
        re.compile(r"^\s*(teacher'?s guide|teacher notes|teacher guide|教师提示|授课提示)\s*[:：]\s*(.*)$", re.IGNORECASE),
    ],
    "image_suggestion": [
        re.compile(r"^\s*(image suggestion|picture suggestion|visual suggestion|图片建议)\s*[:：]\s*(.*)$", re.IGNORECASE),
    ],
    "key_sentence": [
        re.compile(r"^\s*(key sentence|核心句|重点句)\s*[:：]\s*(.*)$", re.IGNORECASE),
    ],
    "useful_expressions": [
        re.compile(r"^\s*(useful expressions|expression bank|亮点表达|常用表达)\s*[:：]\s*(.*)$", re.IGNORECASE),
    ],
    "possible_answers": [
        re.compile(r"^\s*(possible answers|possible answer|reference answers|参考答案)\s*[:：]\s*(.*)$", re.IGNORECASE),
    ],
    "chinese_hint": [
        re.compile(r"^\s*(chinese hint|中文提示|中文引导|中文备注)\s*[:：]\s*(.*)$", re.IGNORECASE),
    ],
}

TITLE_KEYWORDS = {
    "cover": ["cover", "封面"],
    "objectives": ["learning objectives", "objectives", "学习目标"],
    "lead_in": ["lead-in", "lead in", "导入", "warm-up"],
    "warm_up": ["warm up", "warm-up", "热身"],
    "pre_reading": ["pre-reading", "pre reading", "读前"],
    "prediction": ["prediction", "预测"],
    "fast_reading": ["fast reading", "略读", "skim"],
    "careful_reading": ["careful reading", "细读", "scan"],
    "vocabulary_focus": ["vocabulary", "词汇"],
    "language_points": ["language points", "句型", "表达", "key sentence"],
    "group_discussion": ["discussion", "output", "share", "讨论"],
    "grammar_rule": ["grammar rule", "语法规则", "grammar"],
    "writing_task": ["writing task", "写作任务"],
    "useful_expressions": ["useful expressions", "expression bank", "常用表达", "亮点表达"],
    "summary": ["summary", "总结"],
    "homework": ["homework", "作业"],
    "blackboard_design": ["blackboard", "board", "板书"],
}


def _normalize_spaces(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _split_items(text):
    items = []
    for part in re.split(r"[\n;；]|(?<=[。.!?])\s+", str(text or "")):
        cleaned = part.strip(" -•\t")
        if cleaned:
            items.append(cleaned)
    return items


def _is_orphan_number_marker(text):
    value = _normalize_spaces(text)
    return bool(re.match(r"^(?:\d+|[A-Za-z])[.)、．]$", value))


def _merge_numbered_objective_lines(lines):
    merged = []
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = _normalize_spaces(line)
        if (
            _is_orphan_number_marker(stripped)
            and index + 1 < len(lines)
        ):
            next_line = lines[index + 1]
            next_field, _ = _extract_field(next_line)
            next_stripped = _normalize_spaces(next_line)
            if next_stripped and not next_field and not _marker_match(next_stripped)[0]:
                merged.append(f"{stripped} {next_stripped}")
                index += 2
                continue
        merged.append(line)
        index += 1
    return merged


def _marker_match(line):
    for pattern in PAGE_MARKER_PATTERNS:
        match = pattern.match(line)
        if match:
            return match.group(1).strip(), match.group(2).strip()
    heading_match = HEADING_PATTERN.match(line)
    if heading_match:
        return heading_match.group(1).strip(), heading_match.group(2).strip()
    return None, None


def _split_page_blocks(manuscript_text):
    blocks = []
    current = None
    for raw_line in str(manuscript_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            if current is not None:
                current["lines"].append("")
            continue
        marker, remainder = _marker_match(line)
        if marker:
            if current:
                blocks.append(current)
            current = {
                "marker": marker,
                "title_hint": remainder,
                "lines": [],
            }
            if remainder:
                current["lines"].append(remainder)
            continue
        if current is None:
            current = {"marker": "", "title_hint": "", "lines": []}
        current["lines"].append(line)
    if current:
        blocks.append(current)
    if len(blocks) >= 2 and not blocks[0].get("marker") and blocks[1].get("marker"):
        prefix_lines = [line for line in blocks[0].get("lines", []) if line.strip()]
        blocks[1]["lines"] = prefix_lines + blocks[1].get("lines", [])
        blocks = blocks[1:]
    return blocks


def _extract_field(line):
    for field_name, patterns in FIELD_PATTERNS.items():
        for pattern in patterns:
            match = pattern.match(line)
            if match:
                return field_name, match.group(2).strip()
    return None, None


def _infer_slide_type(title, lines):
    title_lower = _normalize_spaces(title).lower()
    joined = " ".join(_normalize_spaces(line).lower() for line in lines if line)
    combined = f"{title_lower} {joined}"
    for slide_type, keywords in TITLE_KEYWORDS.items():
        if any(keyword in combined for keyword in keywords):
            return slide_type
    return "task_design"


def _page_title(block):
    title_hint = _normalize_spaces(block.get("title_hint"))
    if title_hint:
        return title_hint
    lines = [line for line in block.get("lines", []) if line.strip()]
    if lines:
        first = _normalize_spaces(lines[0])
        if len(first) <= 80 and not any(_extract_field(first)):
            return first
    marker = _normalize_spaces(block.get("marker"))
    return marker or "Content Page"


def _build_slide_from_block(block, lesson_request, index):
    title = _page_title(block)
    visible_content = []
    teacher_notes_parts = []
    useful_expressions = []
    possible_answers = []
    key_sentence = ""
    image_suggestion = ""
    chinese_hint = ""
    marker = _normalize_spaces(block.get("marker"))

    lines = [line for line in block.get("lines", []) if line.strip()]
    if lines and _normalize_spaces(lines[0]) == title:
        lines = lines[1:]
    lines = _merge_numbered_objective_lines(lines)

    current_multiline_field = None
    for line in lines:
        field_name, value = _extract_field(line)
        if field_name:
            current_multiline_field = field_name
        elif current_multiline_field and line.startswith(("-", "•", "*")):
            value = line.strip(" -*•\t")
            field_name = current_multiline_field
        else:
            current_multiline_field = None

        if field_name == "teacher_notes":
            if value:
                teacher_notes_parts.append(value)
            continue
        if field_name == "image_suggestion":
            if value:
                image_suggestion = value
            continue
        if field_name == "key_sentence":
            if value:
                key_sentence = value
            continue
        if field_name == "useful_expressions":
            useful_expressions.extend(_split_items(value))
            continue
        if field_name == "possible_answers":
            possible_answers.extend(_split_items(value))
            continue
        if field_name == "chinese_hint":
            if value:
                chinese_hint = value
            continue
        visible_content.extend(_split_items(line))

    if marker:
        teacher_notes_parts.insert(0, f"Source page marker: {marker}.")

    visible_content = [
        item
        for item in visible_content
        if item and item != title and not _is_orphan_number_marker(item)
    ][:5]
    useful_expressions = useful_expressions[:5]
    possible_answers = possible_answers[:5]

    if not visible_content and key_sentence:
        visible_content.append(key_sentence)
    if not visible_content and useful_expressions:
        visible_content.extend(useful_expressions[:3])

    slide_type = _infer_slide_type(title, lines)
    if slide_type == "useful_expressions" and not useful_expressions:
        useful_expressions = visible_content[:4]

    teaching_purpose = f"Preserve and present the original manuscript page: {title}."
    interaction_type = "Teacher-student interaction"
    if slide_type in {"group_discussion", "pair_work"}:
        interaction_type = "Group discussion" if slide_type == "group_discussion" else "Pair work"

    return {
        "slide_index": index,
        "slide_type": slide_type,
        "title": title,
        "visible_content": visible_content or ["Present the original page content clearly."],
        "teacher_notes": _normalize_spaces(" ".join(teacher_notes_parts)) or "Preserve the original teacher guidance from the manuscript.",
        "teaching_purpose": teaching_purpose,
        "estimated_time": "3 minutes",
        "interaction_type": interaction_type,
        "image_suggestion": image_suggestion,
        "key_sentence": key_sentence,
        "useful_expressions": useful_expressions,
        "possible_answers": possible_answers,
        "chinese_hint": chinese_hint,
    }


def _build_rule_slides(lesson_request, manuscript_text):
    blocks = _split_page_blocks(manuscript_text)
    slides = []
    for index, block in enumerate(blocks, start=1):
        slides.append(_build_slide_from_block(block, lesson_request, index))
    return slides


def generate_rule_original_page_slides(lesson_request, manuscript_text):
    """Return the local rule-based preserve-pages slide deck."""

    return _build_rule_slides(lesson_request, manuscript_text)


def _normalize_list(value, fallback):
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
                "visible_content": _normalize_list(candidate.get("visible_content"), fallback_slide["visible_content"]),
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
                "useful_expressions": _normalize_list(
                    candidate.get("useful_expressions"),
                    fallback_slide.get("useful_expressions", []),
                ),
                "possible_answers": _normalize_list(
                    candidate.get("possible_answers"),
                    fallback_slide.get("possible_answers", []),
                ),
                "chinese_hint": str(candidate.get("chinese_hint") or fallback_slide.get("chinese_hint") or "").strip(),
            }
        )
    return normalized


def _parser_prompts(lesson_request, manuscript_text, page_structure, fallback):
    system_prompt = """
You parse an already page-structured English teaching manuscript into PPT slide JSON.
Return JSON only.
"""
    user_prompt = f"""
Parse this manuscript by preserving its original page structure.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Detected page structure:
{json.dumps(page_structure, ensure_ascii=False, indent=2)}

Manuscript:
{manuscript_text[:7000]}

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
- image_suggestion
- key_sentence
- useful_expressions
- possible_answers
- chinese_hint

Requirements:
- Preserve the original page order and titles as much as possible.
- Keep Key Sentence, Useful Expressions, Teacher's Guide, image suggestions, and possible answers when they are clearly provided.
- Do not rewrite a clearly written page title.
- Put detailed explanation into teacher_notes.
"""
    return system_prompt.strip(), user_prompt.strip()


def parse_original_pages(lesson_request, manuscript_text, page_structure):
    """Parse manuscript pages while preserving original page structure."""

    fallback = _build_rule_slides(lesson_request, manuscript_text)
    system_prompt, user_prompt = _parser_prompts(
        lesson_request,
        manuscript_text,
        page_structure,
        fallback,
    )
    payload = call_agent_json(
        "original_page_parser_agent",
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Parse the original manuscript page structure into slides.",
        },
        fallback_fn=lambda: {"slides": fallback},
    )
    return _normalize_slides(payload, fallback)
