"""Lightweight PPT quality checks based on slide JSON and layout hints."""

from services.mock_ai_service import normalize_lesson_type


GENERIC_BAD_LINES = {
    "complete the classroom task.",
    "please complete the task without specific instruction.",
}


def _clean(value):
    return str(value or "").strip()


def _slide_issues(slide):
    issues = []
    title = _clean(slide.get("title"))
    content = list(slide.get("visible_content") or [])
    slide_type = _clean(slide.get("slide_type")).lower()
    layout_type = _clean((slide.get("layout_plan") or {}).get("layout_type"))
    teacher_notes = _clean(slide.get("teacher_notes"))

    if not title:
        issues.append({"code": "missing_title", "message": "缺少标题", "severity": "critical"})
    if len(title) > 90:
        issues.append({"code": "title_too_long", "message": "标题过长，建议压缩", "severity": "warning"})
    if not content:
        issues.append({"code": "empty_visible_content", "message": "visible_content 为空", "severity": "critical"})
    if len(content) > 6:
        issues.append({"code": "too_many_bullets", "message": "bullet 超过 6 条", "severity": "warning"})
    if len(content) <= 1:
        issues.append({"code": "content_too_sparse", "message": "页面内容过少", "severity": "info"})
    if not layout_type:
        issues.append({"code": "layout_missing", "message": "缺少 layout_plan", "severity": "warning"})

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
    if len(teacher_notes) < 20:
        issues.append({"code": "teacher_notes_too_short", "message": "teacher_notes 过短，建议补充授课提示", "severity": "info"})
    return issues


def _lesson_structure_issues(slides, lesson_type):
    issues = []
    types = {_clean(s.get("slide_type")).lower() for s in slides}
    lesson_key = normalize_lesson_type(lesson_type)
    if lesson_key == "reading":
        required = {"lead_in", "prediction", "fast_reading", "careful_reading", "group_discussion", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append({"code": "reading_structure_missing", "message": f"Reading 课缺少关键环节: {', '.join(missing)}", "severity": "critical"})
    elif lesson_key == "writing":
        required = {"writing_task", "structure_analysis", "useful_expressions", "peer_review", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append({"code": "writing_structure_missing", "message": f"Writing 课缺少关键环节: {', '.join(missing)}", "severity": "critical"})
    elif lesson_key == "grammar":
        required = {"observe_discover", "grammar_rule", "controlled_practice", "communicative_practice", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append({"code": "grammar_structure_missing", "message": f"Grammar 课缺少关键环节: {', '.join(missing)}", "severity": "critical"})
    return issues


def check_ppt_quality(task, slides):
    slides = list(slides or [])
    slide_reports = []
    issue_count = 0
    severe_count = 0
    warning_count = 0
    info_count = 0
    for slide in slides:
        issues = _slide_issues(slide)
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

    structure_issues = _lesson_structure_issues(slides, task.get("lesson_type"))
    issue_count += len(structure_issues)
    severe_count += sum(1 for x in structure_issues if x.get("severity") == "critical")
    warning_count += sum(1 for x in structure_issues if x.get("severity") == "warning")
    info_count += sum(1 for x in structure_issues if x.get("severity") == "info")
    status = "通过" if issue_count == 0 else ("严重问题" if severe_count > 0 else "有风险")
    return {
        "status": status,
        "issue_count": issue_count,
        "severe_count": severe_count,
        "warning_count": warning_count,
        "info_count": info_count,
        "structure_issues": [item["message"] for item in structure_issues],
        "structure_issue_details": structure_issues,
        "slides": slide_reports,
        "export_warning": severe_count > 0,
    }
