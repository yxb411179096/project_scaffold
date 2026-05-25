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

    if not title:
        issues.append("缺少标题")
    if len(title) > 90:
        issues.append("标题过长，建议压缩")
    if not content:
        issues.append("visible_content 为空")
    if len(content) > 6:
        issues.append("bullet 超过 6 条")
    if len(content) <= 1:
        issues.append("页面内容过少")

    for line in content:
        text = _clean(line)
        low = text.lower()
        if len(text) > 120:
            issues.append("存在超长行文本")
        if low in GENERIC_BAD_LINES:
            issues.append("出现空泛占位句")
        if low.startswith("step 1") or low.startswith("step 2") or low.startswith("step 3"):
            if len(text) <= 12:
                issues.append("出现空泛 Step 占位")

    if slide.get("image_suggestion") and "Image Placeholder" not in str(slide):
        if layout_type and "image" not in layout_type and slide_type not in {"cover", "lead_in", "prediction", "pre_reading", "warm_up"}:
            issues.append("存在 image_suggestion 但布局可能未突出图片占位")
    if slide.get("key_sentence") and layout_type not in {"warmup_card_layout", "sentence_analysis_layout"}:
        issues.append("存在 key_sentence 但未使用重点句布局")
    if slide.get("useful_expressions") and layout_type not in {"warmup_card_layout", "prediction_flow_layout", "discussion_layout", "sentence_analysis_layout"}:
        issues.append("存在 useful_expressions 但未使用表达支架布局")
    return issues


def _lesson_structure_issues(slides, lesson_type):
    issues = []
    types = {_clean(s.get("slide_type")).lower() for s in slides}
    lesson_key = normalize_lesson_type(lesson_type)
    if lesson_key == "reading":
        required = {"lead_in", "prediction", "fast_reading", "careful_reading", "group_discussion", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append(f"Reading 课缺少关键环节: {', '.join(missing)}")
    elif lesson_key == "writing":
        required = {"writing_task", "structure_analysis", "useful_expressions", "peer_review", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append(f"Writing 课缺少关键环节: {', '.join(missing)}")
    elif lesson_key == "grammar":
        required = {"observe_discover", "grammar_rule", "controlled_practice", "communicative_practice", "summary"}
        missing = sorted(required - types)
        if missing:
            issues.append(f"Grammar 课缺少关键环节: {', '.join(missing)}")
    return issues


def check_ppt_quality(task, slides):
    slides = list(slides or [])
    slide_reports = []
    issue_count = 0
    severe_count = 0
    for slide in slides:
        issues = _slide_issues(slide)
        issue_count += len(issues)
        if any(x in issues for x in ("visible_content 为空", "出现空泛占位句")):
            severe_count += 1
        slide_reports.append(
            {
                "slide_index": slide.get("slide_index"),
                "title": slide.get("title"),
                "slide_type": slide.get("slide_type"),
                "issues": issues,
            }
        )

    structure_issues = _lesson_structure_issues(slides, task.get("lesson_type"))
    issue_count += len(structure_issues)
    severe_count += len(structure_issues)
    status = "通过" if issue_count == 0 else "有风险"
    return {
        "status": status,
        "issue_count": issue_count,
        "severe_count": severe_count,
        "structure_issues": structure_issues,
        "slides": slide_reports,
        "export_warning": severe_count > 0,
    }
