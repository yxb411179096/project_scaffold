"""Page structure detector agent.

Current stage: hybrid Ollama + rule-based fallback.
Future replacement: this detector can be backed by a stronger model while
keeping the same output schema for strategy selection.
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

PAGE_LIKE_HEADINGS = {
    "封面",
    "学习目标",
    "导入",
    "prediction",
    "fast reading",
    "careful reading",
    "vocabulary",
    "language points",
    "discussion",
    "summary",
    "homework",
    "blackboard",
    "grammar rule",
    "writing task",
    "useful expressions",
}


def _normalize_lines(manuscript_text):
    return [line.strip() for line in str(manuscript_text or "").splitlines() if line.strip()]


def _detect_markers(manuscript_text):
    detected = []
    for line in _normalize_lines(manuscript_text):
        for pattern in PAGE_MARKER_PATTERNS:
            match = pattern.match(line)
            if match:
                marker = match.group(1).strip()
                remainder = match.group(2).strip()
                detected.append(f"{marker} {remainder}".strip())
                break
        else:
            heading_match = HEADING_PATTERN.match(line)
            if heading_match:
                title = heading_match.group(2).strip()
                if any(keyword in title.lower() for keyword in PAGE_LIKE_HEADINGS):
                    detected.append(line)
    return detected


def _build_rule_detection(manuscript_text):
    markers = _detect_markers(manuscript_text)
    has_page_structure = len(markers) >= 2
    recommended_strategy = "preserve_original_pages" if has_page_structure else "ai_restructure"
    return {
        "has_page_structure": has_page_structure,
        "page_count_detected": len(markers),
        "detected_page_markers": markers[:20],
        "recommended_strategy": recommended_strategy,
    }


def generate_rule_page_structure_detection(manuscript_text):
    """Return the local rule-based page structure detection result."""

    return _build_rule_detection(manuscript_text)


def _normalize_detection(payload, fallback):
    payload = payload if isinstance(payload, dict) else {}
    recommended_strategy = str(
        payload.get("recommended_strategy") or fallback["recommended_strategy"]
    ).strip()
    if recommended_strategy not in {"preserve_original_pages", "ai_restructure"}:
        recommended_strategy = fallback["recommended_strategy"]
    markers = payload.get("detected_page_markers")
    if isinstance(markers, list):
        markers = [str(item).strip() for item in markers if str(item or "").strip()][:20]
    else:
        markers = fallback["detected_page_markers"]
    try:
        page_count = int(payload.get("page_count_detected"))
    except (TypeError, ValueError):
        page_count = fallback["page_count_detected"]
    return {
        "has_page_structure": bool(payload.get("has_page_structure")) if payload.get("has_page_structure") is not None else fallback["has_page_structure"],
        "page_count_detected": max(page_count, len(markers)),
        "detected_page_markers": markers,
        "recommended_strategy": recommended_strategy,
    }


def _detector_prompts(lesson_request, manuscript_text, fallback):
    system_prompt = """
You detect whether a manuscript already contains explicit PPT page structure.
Return JSON only.
"""
    user_prompt = f"""
Check whether this manuscript already contains explicit page-by-page PPT structure.

Lesson request:
{json.dumps(lesson_request, ensure_ascii=False, indent=2)}

Manuscript:
{manuscript_text[:5000]}

Fallback detection:
{json.dumps(fallback, ensure_ascii=False, indent=2)}

Return one JSON object with exactly these keys:
- has_page_structure
- page_count_detected
- detected_page_markers
- recommended_strategy

Requirements:
- Detect markers like 第1页, 第 1 页, Page 1, Slide 1, 幻灯片1, and heading-like page sections such as 一、封面.
- recommended_strategy must be either preserve_original_pages or ai_restructure.
"""
    return system_prompt.strip(), user_prompt.strip()


def detect_page_structure(lesson_request, manuscript_text):
    """Detect whether a manuscript already includes explicit page structure."""

    fallback = _build_rule_detection(manuscript_text)
    system_prompt, user_prompt = _detector_prompts(lesson_request, manuscript_text, fallback)
    payload = call_agent_json(
        "page_structure_detector_agent",
        {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt,
            "task_id": lesson_request.get("task_id"),
            "stage_note": "Detect whether the manuscript already has explicit page structure.",
        },
        fallback_fn=lambda: fallback,
    )
    return _normalize_detection(payload, fallback)
