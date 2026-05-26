"""Lightweight PPT quality checks based on slide JSON and layout hints."""

import re

from services.layout_template_service import get_template_for_slide
from services.mock_ai_service import normalize_lesson_type
from services.ppt_style_service import recommend_style_key


GENERIC_BAD_LINES = {
    "complete the classroom task.",
    "please complete the task without specific instruction.",
}

EXPECTED_GRAPHIC_BY_SLIDE = {
    "careful_reading": "reading_structure",
    "structure_analysis": "writing_framework",
    "guided_writing": "writing_framework",
    "grammar_rule": "grammar_rule_chart",
}

ISSUE_SUGGESTIONS = {
    "page_may_be_too_dense": "建议减少主体条目，或在该页启用 safe_compact_layout。",
    "font_too_small_risk": "建议压缩每条文字长度，确保正文字号可读。",
    "vocabulary_card_too_long": "建议词汇卡减少到 3 个词，每个词只保留短释义和短例句。",
    "summary_too_verbose": "建议改为三点总结短句（What we learned / How we read / What we can say）。",
    "summary_hard_truncated": "建议改写为完整短句，避免半截断文本。",
    "graphic_too_dense": "建议减少图形节点到 3-4 个，详细内容移至 teacher_notes。",
    "template_overflow": "建议把超出模板容量的内容下沉到 teacher_notes / DOCX。",
    "duplicate_rendering_risk": "建议该页仅保留一种主体结构（模板或图形其一）。",
}


def _clean(value):
    return str(value or "").strip()


def _slide_issues(slide):
    issues = []
    title = _clean(slide.get("title"))
    content = list(slide.get("visible_content") or [])
    slide_type = _clean(slide.get("slide_type")).lower()
    layout_type = _clean((slide.get("layout_plan") or {}).get("layout_type"))
    rendered_variant = _clean((slide.get("layout_plan") or {}).get("rendered_visual_variant"))
    graphic_type = _clean(slide.get("graphic_type") or (slide.get("layout_plan") or {}).get("graphic_type")).lower()
    graphic_data = slide.get("graphic_data") or (slide.get("layout_plan") or {}).get("graphic_data")
    teacher_notes = _clean(slide.get("teacher_notes"))
    template = (slide.get("layout_plan") or {}).get("layout_template") or get_template_for_slide(slide_type)

    if not title:
        issues.append({"code": "missing_title", "message": "缺少标题", "severity": "critical"})
    if len(title) > 90:
        issues.append({"code": "title_too_long", "message": "标题过长，建议压缩", "severity": "warning"})
    if not content:
        issues.append({"code": "empty_visible_content", "message": "visible_content 为空", "severity": "critical"})
    if len(content) > 6:
        issues.append({"code": "too_many_bullets", "message": "bullet 超过 6 条", "severity": "warning"})
    if template:
        visual_variant = _clean(template.get("visual_variant"))
        if not visual_variant:
            issues.append({"code": "template_visual_variant_missing", "message": "模板缺少 visual_variant，页面可能退化为通用样式。", "severity": "warning"})
        max_blocks = int(template.get("max_blocks") or 3)
        max_items = int(template.get("max_items_per_block") or 2)
        if len(content) > max_blocks * max_items:
            issues.append({"code": "template_overflow", "message": "超过模板内容上限，建议下沉到 teacher_notes。", "severity": "warning"})
        if int(template.get("min_font_size") or 14) < 14:
            issues.append({"code": "template_font_too_small", "message": "模板最小字体过小。", "severity": "critical"})
        if int(template.get("label_font_size") or 14) > int(template.get("body_font_size") or 18):
            issues.append({"code": "big_label_small_body_risk", "message": "标签字号大于正文，存在视觉比例风险。", "severity": "warning"})
        plain_like_layouts = {"reading_task_layout", "comparison_layout"}
        if (
            visual_variant
            and (layout_type in plain_like_layouts or (rendered_variant == "plain_fallback"))
            and slide_type in {"objectives", "lead_in", "prediction", "careful_reading", "vocabulary_focus", "summary", "homework"}
        ):
            issues.append({"code": "template_rendered_as_plain_bullets", "message": "页面已配置模板但视觉上接近普通文本页，建议使用对应视觉变体。", "severity": "warning"})
    if len(content) <= 1:
        issues.append({"code": "content_too_sparse", "message": "页面内容过少", "severity": "info"})
    if not layout_type:
        issues.append({"code": "layout_missing", "message": "缺少 layout_plan", "severity": "warning"})
    expected_graphic = EXPECTED_GRAPHIC_BY_SLIDE.get(slide_type)
    if expected_graphic and graphic_type in {"", "none"}:
        issues.append({"code": "graphic_type_missing", "message": f"该页面建议使用图形组件：{expected_graphic}", "severity": "warning"})
    if graphic_type and graphic_type != "none" and (not isinstance(graphic_data, dict) or not graphic_data):
        issues.append({"code": "graphic_data_empty", "message": "graphic_type 存在但 graphic_data 为空", "severity": "warning"})
    if graphic_type and graphic_type != "none":
        node_count = 0
        long_node_text = 0
        if isinstance(graphic_data, dict):
            for key in ("nodes", "cards", "steps", "branches", "events", "rows", "examples", "common_mistakes", "useful_expressions"):
                value = graphic_data.get(key)
                if isinstance(value, list):
                    node_count += len(value)
                    for item in value:
                        text = _clean(item if not isinstance(item, dict) else " ".join(str(v) for v in item.values()))
                        if len(text) > 90:
                            long_node_text += 1
        if node_count > 4 or long_node_text > 2:
            issues.append({"code": "graphic_too_dense", "message": "图形组件信息密度过高，建议减少节点或缩短文本。", "severity": "critical"})
    if graphic_type == "task_steps":
        generic_steps = 0
        for line in content:
            low = _clean(line).lower()
            if low.startswith("step 1") or low.startswith("step 2") or low.startswith("step 3"):
                if ":" not in low and len(low) <= 10:
                    generic_steps += 1
        if generic_steps >= 2:
            issues.append({"code": "task_steps_too_generic", "message": "task_steps 过于空泛（Step 1/2 无具体任务）", "severity": "critical"})
    if graphic_type and graphic_type != "none" and len(content) >= 4:
        issues.append(
            {
                "code": "duplicate_rendering_risk",
                "message": "该页启用了图形组件，PPTX 导出时应避免重复渲染普通内容。",
                "severity": "warning",
            }
        )

    long_bullet_count = 0
    for line in content:
        text = _clean(line)
        low = text.lower()
        if len(text) > 120:
            long_bullet_count += 1
            issues.append({"code": "bullet_too_long", "message": "存在超长行文本", "severity": "warning"})
        if low in GENERIC_BAD_LINES:
            issues.append({"code": "generic_placeholder", "message": "出现空泛占位句", "severity": "critical"})
        if low.startswith("step 1") or low.startswith("step 2") or low.startswith("step 3"):
            if len(text) <= 12:
                issues.append({"code": "generic_step_placeholder", "message": "出现空泛 Step 占位", "severity": "critical"})
        if re.search(r"[A-Za-z]{4,}\.\.\.", text):
            issues.append({"code": "hard_truncation_risk", "message": "检测到疑似半词截断（如 classr...），建议优化文本裁剪。", "severity": "critical"})
        if re.search(r"\bitem\s+\d+\b", low):
            issues.append({"code": "item_placeholder_risk", "message": "检测到 Item 占位词，建议替换为真实词汇。", "severity": "warning"})

    if long_bullet_count >= 2:
        issues.append({"code": "possible_overflow", "message": "多条长文本可能导致溢出", "severity": "warning"})

    visual_blocks = 0
    for key in ("key_sentence", "useful_expressions", "possible_answers", "image_suggestion"):
        if slide.get(key):
            visual_blocks += 1
    if visual_blocks >= 4:
        issues.append({"code": "too_many_visual_blocks", "message": "视觉区块过多，页面可能拥挤", "severity": "warning"})

    if slide.get("image_suggestion") and "Image Placeholder" not in str(slide):
        if layout_type and "image" not in layout_type and slide_type not in {"cover", "lead_in", "prediction", "pre_reading", "warm_up"}:
            issues.append({"code": "image_suggestion_not_rendered", "message": "存在 image_suggestion 但布局可能未突出图片占位", "severity": "warning"})
    if slide.get("key_sentence") and layout_type not in {"warmup_card_layout", "sentence_analysis_layout"}:
        issues.append({"code": "key_sentence_not_highlighted", "message": "存在 key_sentence 但未使用重点句布局", "severity": "warning"})
    if slide.get("useful_expressions") and layout_type not in {"warmup_card_layout", "prediction_flow_layout", "discussion_layout", "sentence_analysis_layout"}:
        issues.append({"code": "useful_expressions_not_scaffolded", "message": "存在 useful_expressions 但未使用表达支架布局", "severity": "warning"})
    if len(content) >= 5 and sum(len(_clean(x)) for x in content) > 280:
        issues.append({"code": "page_may_be_too_dense", "message": "页面信息密度偏高", "severity": "warning"})
        issues.append({"code": "font_too_small_risk", "message": "内容过多可能导致字体低于 11。", "severity": "critical"})
    if len(teacher_notes) < 20:
        issues.append({"code": "teacher_notes_too_short", "message": "teacher_notes 过短，建议补充授课提示", "severity": "info"})
    if graphic_type == "vocabulary_cards" and isinstance(graphic_data, dict):
        cards = list(graphic_data.get("cards") or [])
        for card in cards:
            if not isinstance(card, dict):
                continue
            if len(_clean(card.get("word"))) > 30 or len(_clean(card.get("meaning"))) > 80 or len(_clean(card.get("example"))) > 80:
                issues.append({"code": "vocabulary_card_too_long", "message": "词汇卡内容偏长，建议缩短 word/meaning/example。", "severity": "warning"})
                break
    if slide_type == "summary":
        total_len = sum(len(_clean(x)) for x in content)
        if total_len > 180:
            issues.append({"code": "summary_too_verbose", "message": "Summary 页内容偏长，建议改为关键词。", "severity": "warning"})
        if any("..." in _clean(x) for x in content):
            issues.append({"code": "summary_hard_truncated", "message": "Summary 页存在截断内容，建议改为完整短句。", "severity": "critical"})
        if layout_type in {"reading_task_layout", "comparison_layout"} and graphic_type in {"", "none"}:
            issues.append({"code": "summary_too_plain", "message": "Summary 页过于普通，建议使用总结卡片结构。", "severity": "warning"})
    if slide_type == "vocabulary_focus":
        card_like = layout_type in {"vocabulary_card_layout"} or graphic_type == "vocabulary_cards"
        if not card_like:
            issues.append({"code": "vocabulary_not_card_like", "message": "Vocabulary 页缺少词汇卡片结构。", "severity": "warning"})
    return issues


def _issue_suggestion(code):
    return ISSUE_SUGGESTIONS.get(code) or "建议精简该页可见内容，并把细节转移到 teacher_notes。"


def _lesson_structure_issues(slides, lesson_type):
    issues = []
    types = {_clean(s.get("slide_type")).lower() for s in slides}
    lesson_key = normalize_lesson_type(lesson_type)
    if lesson_key == "reading":
        required = {"lead_in", "prediction", "fast_reading", "careful_reading", "group_discussion", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append({"code": "reading_structure_missing", "message": f"Reading 课缺少关键环节: {', '.join(missing)}", "severity": "critical"})
        for slide in slides:
            if _clean(slide.get("slide_type")).lower() == "careful_reading":
                g = _clean(slide.get("graphic_type") or (slide.get("layout_plan") or {}).get("graphic_type")).lower()
                if g not in {"reading_structure"}:
                    issues.append({"code": "reading_structure_missing", "message": "careful_reading 页缺少 reading_structure 图形", "severity": "warning"})
    elif lesson_key == "writing":
        required = {"writing_task", "structure_analysis", "useful_expressions", "peer_review", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append({"code": "writing_structure_missing", "message": f"Writing 课缺少关键环节: {', '.join(missing)}", "severity": "critical"})
        has_framework = any(
            _clean(s.get("graphic_type") or (s.get("layout_plan") or {}).get("graphic_type")).lower() == "writing_framework"
            for s in slides
        )
        if not has_framework:
            issues.append({"code": "writing_framework_missing", "message": "Writing 课缺少 writing_framework 图形组件", "severity": "warning"})
    elif lesson_key == "grammar":
        required = {"observe_discover", "grammar_rule", "controlled_practice", "communicative_practice", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append({"code": "grammar_structure_missing", "message": f"Grammar 课缺少关键环节: {', '.join(missing)}", "severity": "critical"})
        for slide in slides:
            if _clean(slide.get("slide_type")).lower() == "grammar_rule":
                g = _clean(slide.get("graphic_type") or (slide.get("layout_plan") or {}).get("graphic_type")).lower()
                if g not in {"grammar_rule_chart"}:
                    issues.append({"code": "grammar_rule_chart_missing", "message": "grammar_rule 页缺少 grammar_rule_chart 图形", "severity": "warning"})
    return issues


def check_ppt_quality(task, slides):
    slides = list(slides or [])
    slide_reports = []
    issue_count = 0
    severe_count = 0
    warning_count = 0
    info_count = 0
    variants = []
    for slide in slides:
        template = (slide.get("layout_plan") or {}).get("layout_template") or get_template_for_slide(_clean(slide.get("slide_type")).lower())
        variants.append(_clean(template.get("visual_variant")))
        raw_issues = _slide_issues(slide)
        issues = []
        for issue in raw_issues:
            enriched = dict(issue)
            enriched["suggestion"] = _issue_suggestion(enriched.get("code"))
            issues.append(enriched)
        issue_count += len(issues)
        severe_count += sum(1 for x in issues if x.get("severity") == "critical")
        warning_count += sum(1 for x in issues if x.get("severity") == "warning")
        info_count += sum(1 for x in issues if x.get("severity") == "info")
        slide_reports.append(
            {
                "slide_index": slide.get("slide_index"),
                "title": slide.get("title"),
                "slide_type": slide.get("slide_type"),
                "issues": [item["message"] for item in issues],
                "issue_details": issues,
            }
        )

    repeat_run = 0
    prev = ""
    for variant in variants:
        if variant and variant == prev:
            repeat_run += 1
        else:
            repeat_run = 1
        prev = variant
        if variant and repeat_run >= 4:
            structure_issues = [{
                "code": "slide_type_visual_repetition",
                "message": "连续多页使用同一 visual_variant，建议增加页面视觉差异。",
                "severity": "warning",
            }]
            break
    else:
        structure_issues = []

    structure_issues.extend(_lesson_structure_issues(slides, task.get("lesson_type")))
    issue_count += len(structure_issues)
    severe_count += sum(1 for x in structure_issues if x.get("severity") == "critical")
    warning_count += sum(1 for x in structure_issues if x.get("severity") == "warning")
    info_count += sum(1 for x in structure_issues if x.get("severity") == "info")
    style_key = str(task.get("ppt_style") or "").strip().lower()
    if not style_key:
        style_key = "default"
        structure_issues.append({"code": "style_missing", "message": "任务未设置 ppt_style，已自动按 default 检查。", "severity": "info"})
        issue_count += 1
        info_count += 1
    recommended = recommend_style_key(task.get("lesson_type"), task.get("style"))
    if style_key != recommended:
        structure_issues.append(
            {
                "code": "style_not_matching_lesson_type",
                "message": f"当前风格与课型不完全匹配，可考虑 {recommended}。",
                "severity": "info",
            }
        )
        issue_count += 1
        info_count += 1

    status = "通过" if issue_count == 0 else ("严重问题" if severe_count > 0 else "有风险")
    return {
        "status": status,
        "style_applied": style_key,
        "issue_count": issue_count,
        "severe_count": severe_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "structure_issues": [item["message"] for item in structure_issues],
        "structure_issue_details": structure_issues,
        "slides": slide_reports,
        "export_warning": severe_count > 0,
    }
