"""Lesson generation pipeline service.

This module wires the local mock/rule-based agents into one stable flow:
parse requirement -> lesson design -> PPT outline -> slide content ->
language polish -> activity review -> layout planning -> schema check.

Later iterations can swap each stage to a real model-backed agent without
changing the rest of the Flask app.
"""

import json

from services.agents import (
    check_schema,
    generate_lesson_design,
    generate_ppt_outline,
    generate_rule_lesson_design,
    generate_rule_ppt_outline,
    generate_rule_slide_content,
    generate_single_slide_content,
    generate_slide_content,
    parse_requirement,
    plan_layout_for_slide,
    plan_layouts,
    polish_language,
    review_activities,
)
from services.knowledge_retrieval_service import load_knowledge_context, retrieve_knowledge_context
from services.llm_service import record_fallback, record_rule_only_agent


def _has_non_empty_slides(ppt_json):
    return isinstance(ppt_json, list) and len(ppt_json) > 0


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


def build_rule_based_slides(lesson_request, teaching_design=None, ppt_outline=None):
    """Build a complete local rule-based slide deck as the last safety net."""

    teaching_design = teaching_design or generate_rule_lesson_design(lesson_request)
    ppt_outline = ppt_outline or generate_rule_ppt_outline(lesson_request, teaching_design)
    ppt_json = generate_rule_slide_content(lesson_request, teaching_design, ppt_outline)
    ppt_json = review_activities(ppt_json, lesson_request)
    ppt_json = plan_layouts(ppt_json, lesson_request)
    return check_schema(ppt_json)


def ensure_non_empty_slides(ppt_json, lesson_request, teaching_design=None, ppt_outline=None):
    """Guarantee that downstream code never receives an empty slide collection.

    If the current pipeline result is empty, rebuild a full local rule-based
    slide deck so the task can still be edited and exported safely.
    """

    if _has_non_empty_slides(ppt_json):
        return ppt_json

    record_fallback(
        "ensure_non_empty_slides",
        "Pipeline returned empty slides. Rebuilding the deck with the full rule-based pipeline.",
    )
    rebuilt = build_rule_based_slides(lesson_request, teaching_design=teaching_design, ppt_outline=ppt_outline)
    if _has_non_empty_slides(rebuilt):
        return rebuilt
    raise ValueError("Pipeline failed to generate any valid slides.")


def run_generation_pipeline(raw_task):
    """Run the full multi-agent generation flow and return pipeline artifacts."""

    lesson_request = parse_requirement(raw_task)
    record_rule_only_agent(
        "requirement_parser_agent",
        lesson_request.get("task_id"),
        "Normalized the lesson request with rule-based parsing.",
    )
    knowledge_context = _resolve_knowledge_context(lesson_request)
    teaching_design = generate_lesson_design(lesson_request, knowledge_context=knowledge_context)
    ppt_outline = generate_ppt_outline(lesson_request, teaching_design, knowledge_context=knowledge_context)
    ppt_json = generate_slide_content(lesson_request, teaching_design, ppt_outline, knowledge_context=knowledge_context)
    ppt_json = polish_language(ppt_json, lesson_request, knowledge_context=knowledge_context)
    ppt_json = review_activities(ppt_json, lesson_request)
    record_rule_only_agent(
        "activity_review_agent",
        lesson_request.get("task_id"),
        "Reviewed activity coverage and lesson timing with local rules.",
    )
    ppt_json = plan_layouts(ppt_json, lesson_request)
    record_rule_only_agent(
        "layout_planner_agent",
        lesson_request.get("task_id"),
        "Planned slide layouts with deterministic teaching layout rules.",
    )
    ppt_json = check_schema(ppt_json)
    record_rule_only_agent(
        "json_schema_checker",
        lesson_request.get("task_id"),
        "Validated final slide schema before persistence.",
    )
    ppt_json = ensure_non_empty_slides(
        ppt_json,
        lesson_request,
        teaching_design=teaching_design,
        ppt_outline=ppt_outline,
    )

    return {
        "lesson_request": lesson_request,
        "teaching_design": teaching_design,
        "ppt_outline": ppt_outline,
        "ppt_json": ppt_json,
        "knowledge_context": knowledge_context,
    }


def generate_ppt_json(raw_task):
    """Return the final PPT JSON from the mock agent pipeline."""

    return run_generation_pipeline(raw_task)["ppt_json"]


def regenerate_slide_with_pipeline(raw_task, current_slide):
    """Regenerate one slide through the new agent structure.

    The current MVP keeps single-slide regeneration lightweight:
    parse requirement -> lesson design -> slide content -> language polish ->
    schema check.
    """

    lesson_request = parse_requirement(raw_task)
    record_rule_only_agent(
        "requirement_parser_agent",
        lesson_request.get("task_id"),
        "Normalized the lesson request for single-slide regeneration.",
    )
    knowledge_context = _resolve_knowledge_context(lesson_request)
    teaching_design = generate_lesson_design(lesson_request, knowledge_context=knowledge_context)
    slide_outline = {
        "slide_index": current_slide.get("slide_index"),
        "slide_type": current_slide.get("slide_type"),
        "title": current_slide.get("title"),
        "teaching_purpose": current_slide.get("teaching_purpose"),
        "estimated_time": current_slide.get("estimated_time"),
    }
    regenerated_slide = generate_single_slide_content(
        lesson_request,
        teaching_design,
        slide_outline,
        regenerate=True,
        knowledge_context=knowledge_context,
    )
    regenerated_slide = polish_language(regenerated_slide, lesson_request, knowledge_context=knowledge_context)
    regenerated_slide["layout_plan"] = plan_layout_for_slide(regenerated_slide, lesson_request)
    record_rule_only_agent(
        "layout_planner_agent",
        lesson_request.get("task_id"),
        "Planned layout for the regenerated slide.",
    )
    regenerated_slide = check_schema(regenerated_slide)
    record_rule_only_agent(
        "json_schema_checker",
        lesson_request.get("task_id"),
        "Validated regenerated slide schema.",
    )
    return regenerated_slide
