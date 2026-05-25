"""Pipeline service for manuscript-to-PPT generation.

This pipeline keeps the original AI-generate flow untouched and provides a
separate route for turning user manuscripts into structured, editable slide
JSON.
"""

import json

from services.agents import (
    analyze_manuscript,
    check_schema,
    compress_slide_content,
    detect_page_structure,
    extract_lesson_structure,
    generate_rule_compressed_slides,
    generate_rule_lesson_structure,
    generate_rule_manuscript_analysis,
    generate_rule_original_page_slides,
    generate_rule_page_structure_detection,
    generate_rule_slides_from_manuscript,
    parse_original_pages,
    parse_requirement,
    plan_layout_for_slide,
    plan_layouts,
    polish_language,
    regenerate_manuscript_slide,
    review_activities,
    split_manuscript_into_slides,
)
from services.knowledge_retrieval_service import load_knowledge_context, retrieve_knowledge_context
from services.llm_service import record_fallback, record_rule_only_agent
from services.pipeline_service import ensure_non_empty_slides


VALID_MANUSCRIPT_STRATEGIES = {"preserve_original_pages", "ai_restructure"}
VALID_PRESERVE_COMPLETION_MODES = {"preserve_exact_pages", "preserve_and_append_closure"}


def _has_non_empty_slides(ppt_json):
    return isinstance(ppt_json, list) and len(ppt_json) > 0


def _resolve_strategy(raw_task, page_structure):
    requested = str((raw_task or {}).get("manuscript_generation_strategy") or "").strip()
    if requested in VALID_MANUSCRIPT_STRATEGIES:
        return requested
    return page_structure.get("recommended_strategy") or "ai_restructure"


def _record_common_rule_stage(agent_name, lesson_request, detail):
    record_rule_only_agent(agent_name, lesson_request.get("task_id"), detail)


def _resolve_knowledge_context(lesson_request, manuscript_text=None):
    if not lesson_request.get("use_knowledge_base"):
        return None

    existing = load_knowledge_context(
        lesson_request.get("knowledge_context_json") or lesson_request.get("knowledge_context")
    )
    if existing:
        lesson_request["knowledge_context_json"] = json.dumps(existing, ensure_ascii=False)
        lesson_request["knowledge_query"] = existing.get("query") or lesson_request.get("knowledge_query") or ""
        lesson_request["knowledge_top_k"] = existing.get("top_k") or lesson_request.get("knowledge_top_k") or 5
        if not existing.get("failed") and int(existing.get("result_count") or 0) > 0:
            lesson_request["knowledge_context"] = existing
            return existing
        record_fallback("knowledge_retrieval", existing.get("error") or "未找到已索引资料。")
        lesson_request.pop("knowledge_context", None)
        return existing

    context = retrieve_knowledge_context(
        lesson_request,
        query=lesson_request.get("knowledge_query"),
        top_k=lesson_request.get("knowledge_top_k") or 5,
        manuscript_text=manuscript_text,
    )
    lesson_request["knowledge_context_json"] = json.dumps(context, ensure_ascii=False)
    lesson_request["knowledge_query"] = context.get("query") or lesson_request.get("knowledge_query") or ""
    lesson_request["knowledge_top_k"] = context.get("top_k") or lesson_request.get("knowledge_top_k") or 5
    if not context.get("failed") and int(context.get("result_count") or 0) > 0:
        lesson_request["knowledge_context"] = context
    else:
        record_fallback("knowledge_retrieval", context.get("error") or "未找到已索引资料。")
        lesson_request.pop("knowledge_context", None)
    return context


def _preserve_completion_mode(lesson_request):
    mode = str(lesson_request.get("manuscript_preserve_completion_mode") or "preserve_exact_pages").strip()
    return mode if mode in VALID_PRESERVE_COMPLETION_MODES else "preserve_exact_pages"


def _preserve_polish_mode(lesson_request):
    mode = str(lesson_request.get("manuscript_preserve_polish_mode") or "skip").strip()
    return mode if mode in {"skip", "follow_agent_strategy"} else "skip"


def _build_preserve_analysis(lesson_request, manuscript_text, page_structure, slides):
    base_analysis = generate_rule_manuscript_analysis(lesson_request, manuscript_text)
    detected_sections = [slide.get("title") for slide in slides[:8] if slide.get("title")]
    merged = dict(base_analysis)
    merged.update(page_structure)
    merged["detected_sections"] = detected_sections or page_structure.get("detected_page_markers", [])
    merged["missing_sections"] = []
    merged["recommended_generation_strategy"] = (
        "保留原文页结构，优先继承原始页标题、关键句、图片建议和表达卡片，再做轻量压缩与版式优化。"
    )
    merged["organization_suggestion"] = "已按原文页结构生成；如需重新组织课堂流程，可切换为 AI 优化重构生成。"
    merged["summary"] = base_analysis.get("summary") or "The manuscript already contains explicit PPT page structure."
    merged["has_page_structure"] = page_structure.get("has_page_structure", False)
    merged["page_count_detected"] = page_structure.get("page_count_detected", len(slides))
    merged["detected_page_markers"] = page_structure.get("detected_page_markers", [])
    return merged


def _append_preserve_closure_slides(slides, lesson_request, manuscript_text, manuscript_analysis):
    if _preserve_completion_mode(lesson_request) != "preserve_and_append_closure":
        return slides

    lesson_structure = generate_rule_lesson_structure(
        lesson_request,
        manuscript_text,
        manuscript_analysis,
    )
    topic = manuscript_analysis.get("main_topic") or lesson_request.get("course_title") or "today's topic"
    augmented = list(slides)
    augmented.extend(
        [
            {
                "slide_index": len(augmented) + 1,
                "slide_type": "summary",
                "title": "Summary",
                "visible_content": list(lesson_structure.get("key_points", []))[:3] or [f"Review the key idea of {topic}.", "Share one takeaway from today."],
                "teacher_notes": "Use this closing slide to summarize key learning after the original manuscript pages.",
                "teaching_purpose": "Close the preserved lesson pages with a short summary.",
                "estimated_time": "2 minutes",
                "interaction_type": "Teacher-student interaction",
            },
            {
                "slide_index": len(augmented) + 2,
                "slide_type": "homework",
                "title": "Homework",
                "visible_content": list(lesson_structure.get("homework", []))[:3] or ["Review the key language from the lesson.", "Finish the follow-up task after class."],
                "teacher_notes": "Clarify the after-class task and expected output.",
                "teaching_purpose": "Append a clear after-class task to the preserved manuscript deck.",
                "estimated_time": "1 minute",
                "interaction_type": "Teacher-student interaction",
            },
            {
                "slide_index": len(augmented) + 3,
                "slide_type": "blackboard_design",
                "title": "Blackboard Design",
                "visible_content": [item for item in str(lesson_structure.get("blackboard_design") or "").split(";") if item.strip()][:4] or ["Theme", "Key language", "Core task", "Homework"],
                "teacher_notes": str(lesson_structure.get("blackboard_design") or "Theme; Key language; Core task; Homework").strip(),
                "teaching_purpose": "Append a board plan after the preserved manuscript pages.",
                "estimated_time": "1 minute",
                "interaction_type": "Teacher guidance",
            },
        ]
    )
    for index, slide in enumerate(augmented, start=1):
        slide["slide_index"] = index
    return augmented


def _finalize_preserve_slides(ppt_json, lesson_request, knowledge_context=None):
    if _preserve_polish_mode(lesson_request) == "follow_agent_strategy":
        ppt_json = polish_language(ppt_json, lesson_request, knowledge_context=knowledge_context)
    else:
        _record_common_rule_stage(
            "language_polish_agent",
            lesson_request,
            "Skipped preserve-mode language polish to keep original wording and improve speed.",
        )
    ppt_json = plan_layouts(ppt_json, lesson_request)
    _record_common_rule_stage(
        "layout_planner_agent",
        lesson_request,
        "Planned layouts for preserve-original-pages slides.",
    )
    ppt_json = check_schema(ppt_json)
    _record_common_rule_stage(
        "json_schema_checker",
        lesson_request,
        "Validated preserve-original-pages slide schema.",
    )
    return ppt_json


def _finalize_restructure_slides(ppt_json, lesson_request, knowledge_context=None):
    ppt_json = polish_language(ppt_json, lesson_request, knowledge_context=knowledge_context)
    ppt_json = review_activities(ppt_json, lesson_request)
    _record_common_rule_stage(
        "activity_review_agent",
        lesson_request,
        "Reviewed manuscript-based activity coverage and pacing.",
    )
    ppt_json = plan_layouts(ppt_json, lesson_request)
    _record_common_rule_stage(
        "layout_planner_agent",
        lesson_request,
        "Planned layouts for manuscript-based slides.",
    )
    ppt_json = check_schema(ppt_json)
    _record_common_rule_stage(
        "json_schema_checker",
        lesson_request,
        "Validated manuscript-based slide schema.",
    )
    return ppt_json


def _run_preserve_pipeline(lesson_request, manuscript_text, page_structure, use_rule_only=False):
    rule_slides = generate_rule_original_page_slides(lesson_request, manuscript_text)
    _record_common_rule_stage(
        "original_page_parser_agent",
        lesson_request,
        "Parsed manuscript pages with local rule-based preserve-page logic.",
    )
    manuscript_analysis = _build_preserve_analysis(
        lesson_request,
        manuscript_text,
        page_structure,
        rule_slides,
    )
    knowledge_context = _resolve_knowledge_context(lesson_request, manuscript_text)
    if str(lesson_request.get("lesson_type") or "").strip() == "Other":
        lesson_request["lesson_type"] = manuscript_analysis.get("detected_lesson_type") or "Reading"

    ppt_json = rule_slides
    ppt_json = _append_preserve_closure_slides(
        ppt_json,
        lesson_request,
        manuscript_text,
        manuscript_analysis,
    )
    ppt_json = generate_rule_compressed_slides(ppt_json, lesson_request)
    _record_common_rule_stage(
        "content_compressor_agent",
        lesson_request,
        "Compressed preserve-mode pages with local rule-based logic.",
    )
    ppt_json = _finalize_preserve_slides(ppt_json, lesson_request, knowledge_context=knowledge_context)
    return {
        "lesson_request": lesson_request,
        "manuscript_analysis": manuscript_analysis,
        "lesson_structure": {"teaching_steps": []},
        "page_structure": page_structure,
        "ppt_json": ppt_json,
    }


def _run_restructure_pipeline(lesson_request, manuscript_text, use_rule_only=False):
    knowledge_context = _resolve_knowledge_context(lesson_request, manuscript_text)
    if use_rule_only:
        manuscript_analysis = generate_rule_manuscript_analysis(lesson_request, manuscript_text)
    else:
        manuscript_analysis = analyze_manuscript(lesson_request, manuscript_text, knowledge_context=knowledge_context)
    if str(lesson_request.get("lesson_type") or "").strip() == "Other":
        lesson_request["lesson_type"] = manuscript_analysis.get("detected_lesson_type") or "Reading"

    if use_rule_only:
        lesson_structure = generate_rule_lesson_structure(lesson_request, manuscript_text, manuscript_analysis)
        ppt_json = generate_rule_slides_from_manuscript(
            lesson_request,
            manuscript_analysis,
            lesson_structure,
        )
        ppt_json = generate_rule_compressed_slides(ppt_json, lesson_request)
    else:
        lesson_structure = extract_lesson_structure(
            lesson_request,
            manuscript_text,
            manuscript_analysis,
            knowledge_context=knowledge_context,
        )
        ppt_json = split_manuscript_into_slides(
            lesson_request,
            manuscript_analysis,
            lesson_structure,
            knowledge_context=knowledge_context,
        )
        ppt_json = compress_slide_content(ppt_json, lesson_request, knowledge_context=knowledge_context)

    ppt_json = _finalize_restructure_slides(ppt_json, lesson_request, knowledge_context=knowledge_context)
    return {
        "lesson_request": lesson_request,
        "manuscript_analysis": manuscript_analysis,
        "lesson_structure": lesson_structure,
        "page_structure": {},
        "ppt_json": ppt_json,
    }


def build_rule_based_manuscript_result(raw_task, manuscript_text):
    """Build a full local rule-based manuscript deck as the last fallback."""

    lesson_request = parse_requirement(raw_task)
    _record_common_rule_stage(
        "requirement_parser_agent",
        lesson_request,
        "Normalized lesson request for manuscript pipeline.",
    )
    page_structure = generate_rule_page_structure_detection(manuscript_text)
    strategy = _resolve_strategy(raw_task, page_structure)
    lesson_request["manuscript_generation_strategy"] = strategy

    if strategy == "preserve_original_pages":
        result = _run_preserve_pipeline(
            lesson_request,
            manuscript_text,
            page_structure,
            use_rule_only=True,
        )
    else:
        result = _run_restructure_pipeline(
            lesson_request,
            manuscript_text,
            use_rule_only=True,
        )

    result["ppt_json"] = ensure_non_empty_manuscript_slides(
        result["ppt_json"],
        lesson_request,
        manuscript_text,
        strategy=strategy,
        manuscript_analysis=result.get("manuscript_analysis"),
        lesson_structure=result.get("lesson_structure"),
        page_structure=page_structure,
    )
    return result


def ensure_non_empty_manuscript_slides(
    ppt_json,
    lesson_request,
    manuscript_text,
    strategy="ai_restructure",
    manuscript_analysis=None,
    lesson_structure=None,
    page_structure=None,
):
    """Guarantee that manuscript conversion never returns an empty deck."""

    if _has_non_empty_slides(ppt_json):
        return ppt_json

    record_fallback(
        "manuscript_ensure_non_empty",
        "Manuscript pipeline returned empty slides. Rebuilding with rule-based manuscript logic.",
    )
    page_structure = page_structure or generate_rule_page_structure_detection(manuscript_text)

    if strategy == "preserve_original_pages":
        rebuilt = generate_rule_original_page_slides(lesson_request, manuscript_text)
        rebuilt = _append_preserve_closure_slides(
            rebuilt,
            lesson_request,
            manuscript_text,
            manuscript_analysis or generate_rule_manuscript_analysis(lesson_request, manuscript_text),
        )
        rebuilt = generate_rule_compressed_slides(rebuilt, lesson_request)
        rebuilt = _finalize_preserve_slides(rebuilt, lesson_request)
        if _has_non_empty_slides(rebuilt):
            return rebuilt
        strategy = "ai_restructure"

    manuscript_analysis = manuscript_analysis or generate_rule_manuscript_analysis(lesson_request, manuscript_text)
    lesson_structure = lesson_structure or generate_rule_lesson_structure(
        lesson_request,
        manuscript_text,
        manuscript_analysis,
    )
    rebuilt = generate_rule_slides_from_manuscript(
        lesson_request,
        manuscript_analysis,
        lesson_structure,
    )
    rebuilt = generate_rule_compressed_slides(rebuilt, lesson_request)
    rebuilt = _finalize_restructure_slides(rebuilt, lesson_request)
    if _has_non_empty_slides(rebuilt):
        return rebuilt
    return ensure_non_empty_slides([], lesson_request)


def run_manuscript_pipeline(raw_task, manuscript_text):
    """Run the manuscript-to-PPT pipeline and return full pipeline artifacts."""

    lesson_request = parse_requirement(raw_task)
    _record_common_rule_stage(
        "requirement_parser_agent",
        lesson_request,
        "Normalized lesson request for manuscript pipeline.",
    )
    page_structure = generate_rule_page_structure_detection(manuscript_text)
    _record_common_rule_stage(
        "page_structure_detector_agent",
        lesson_request,
        "Detected page markers with local rule-based logic for preserve-mode routing.",
    )
    strategy = _resolve_strategy(raw_task, page_structure)
    lesson_request["manuscript_generation_strategy"] = strategy

    if strategy == "preserve_original_pages":
        result = _run_preserve_pipeline(
            lesson_request,
            manuscript_text,
            page_structure,
            use_rule_only=False,
        )
    else:
        result = _run_restructure_pipeline(
            lesson_request,
            manuscript_text,
            use_rule_only=False,
        )

    result["ppt_json"] = ensure_non_empty_manuscript_slides(
        result["ppt_json"],
        lesson_request,
        manuscript_text,
        strategy=strategy,
        manuscript_analysis=result.get("manuscript_analysis"),
        lesson_structure=result.get("lesson_structure"),
        page_structure=page_structure,
    )
    return result


def generate_ppt_json_from_manuscript(raw_task, manuscript_text):
    """Return final manuscript-based PPT JSON only."""

    return run_manuscript_pipeline(raw_task, manuscript_text)["ppt_json"]


def _neighbor_slide_context(slides, target_index):
    if not slides:
        return {}

    current_position = min(max(target_index - 1, 0), len(slides) - 1)
    context = {"previous_slide": None, "current_slide": None, "next_slide": None}
    labels = {
        current_position - 1: "previous_slide",
        current_position: "current_slide",
        current_position + 1: "next_slide",
    }
    for index, label in labels.items():
        if 0 <= index < len(slides):
            slide = slides[index]
            context[label] = {
                "slide_index": slide.get("slide_index"),
                "slide_type": slide.get("slide_type"),
                "title": slide.get("title"),
                "visible_content": list(slide.get("visible_content", []))[:4],
                "teaching_purpose": slide.get("teaching_purpose"),
            }
    return context


def regenerate_slide_from_manuscript(raw_task, current_slide):
    """Regenerate a manuscript task slide with strategy-aware source context."""

    manuscript_text = str(raw_task.get("manuscript_raw_text") or "").strip()
    if not manuscript_text:
        raise ValueError("The manuscript task does not contain source text.")

    lesson_request = parse_requirement(raw_task)
    _record_common_rule_stage(
        "requirement_parser_agent",
        lesson_request,
        "Normalized lesson request for manuscript slide regeneration.",
    )
    page_structure = generate_rule_page_structure_detection(manuscript_text)
    _record_common_rule_stage(
        "page_structure_detector_agent",
        lesson_request,
        "Detected page markers with local rule-based logic for manuscript regeneration.",
    )
    strategy = _resolve_strategy(raw_task, page_structure)
    lesson_request["manuscript_generation_strategy"] = strategy
    knowledge_context = _resolve_knowledge_context(lesson_request, manuscript_text)

    if strategy == "preserve_original_pages":
        result = _run_preserve_pipeline(
            lesson_request,
            manuscript_text,
            page_structure,
            use_rule_only=False,
        )
        slides = result["ppt_json"]
        target_index = int(current_slide.get("slide_index") or 1)
        slide = slides[min(max(target_index - 1, 0), len(slides) - 1)]
        slide["layout_plan"] = plan_layout_for_slide(slide, lesson_request)
        return check_schema(slide)

    manuscript_analysis = analyze_manuscript(
        lesson_request,
        manuscript_text,
        knowledge_context=knowledge_context,
    )
    if str(lesson_request.get("lesson_type") or "").strip() == "Other":
        lesson_request["lesson_type"] = manuscript_analysis.get("detected_lesson_type") or "Reading"
    lesson_structure = extract_lesson_structure(
        lesson_request,
        manuscript_text,
        manuscript_analysis,
        knowledge_context=knowledge_context,
    )
    target_index = int(current_slide.get("slide_index") or 1)
    neighbor_context = _neighbor_slide_context(raw_task.get("_all_slides") or [], target_index)
    slide = regenerate_manuscript_slide(
        lesson_request,
        manuscript_text,
        manuscript_analysis,
        lesson_structure,
        current_slide,
        neighbor_context=neighbor_context,
        knowledge_context=knowledge_context,
    )
    slide = compress_slide_content(slide, lesson_request, knowledge_context=knowledge_context)
    slide = polish_language(slide, lesson_request, knowledge_context=knowledge_context)
    slide["layout_plan"] = plan_layout_for_slide(slide, lesson_request)
    slide = check_schema(slide)
    return slide
