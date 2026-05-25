from services.agents import generate_rule_slide_content, generate_rule_lesson_design, generate_rule_ppt_outline
from services.ppt_quality_check_service import check_ppt_quality
from services.ppt_render_service import LAYOUT_RENDERERS


def _build_task(lesson_type, topic):
    return {
        "id": 9999,
        "course_title": topic,
        "topic": topic,
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修二",
        "unit": "Unit 3",
        "lesson_type": lesson_type,
        "duration": 45,
        "student_level": "中等",
        "style": "常规课",
    }


def run():
    # 1) fallback quality check catches generic placeholders
    bad_slides = [
        {"slide_index": 1, "slide_type": "task_design", "title": "Task", "visible_content": ["Complete the classroom task."], "layout_plan": {}},
        {"slide_index": 2, "slide_type": "reading_task", "title": "", "visible_content": [], "layout_plan": {}},
    ]
    bad_report = check_ppt_quality(_build_task("Reading", "The Internet"), bad_slides)
    assert bad_report["status"] == "有风险"
    assert bad_report["issue_count"] > 0

    # 2) Reading fallback should include fast/careful reading tasks
    reading_task = _build_task("Reading", "The Internet")
    rd_design = generate_rule_lesson_design(reading_task)
    rd_outline = generate_rule_ppt_outline(reading_task, rd_design)
    rd_slides = generate_rule_slide_content(reading_task, rd_design, rd_outline)
    all_text = " ".join(" ".join(s.get("visible_content") or []) for s in rd_slides).lower()
    assert "complete the classroom task." not in all_text
    assert any(s.get("slide_type") == "fast_reading" for s in rd_slides)
    assert any(s.get("slide_type") == "careful_reading" for s in rd_slides)

    # 3) Writing fallback includes structure / expressions / checklist-style hints
    writing_task = _build_task("Writing", "A Letter of Advice")
    wr_design = generate_rule_lesson_design(writing_task)
    wr_outline = generate_rule_ppt_outline(writing_task, wr_design)
    wr_slides = generate_rule_slide_content(writing_task, wr_design, wr_outline)
    wr_text = " ".join(" ".join(s.get("visible_content") or []) for s in wr_slides).lower()
    assert "structure" in wr_text
    assert "expression" in wr_text or "useful" in wr_text
    assert "checklist" in wr_text or "check" in wr_text

    # 4) Grammar fallback includes observe / rule / practice
    grammar_task = _build_task("Grammar", "Attributive Clauses")
    gr_design = generate_rule_lesson_design(grammar_task)
    gr_outline = generate_rule_ppt_outline(grammar_task, gr_design)
    gr_slides = generate_rule_slide_content(grammar_task, gr_design, gr_outline)
    gr_types = {s.get("slide_type") for s in gr_slides}
    assert "observe_discover" in gr_types
    assert "grammar_rule" in gr_types
    assert "controlled_practice" in gr_types

    # 5) renderer supports key visual field layouts + 6) distinct layout functions
    assert "cover_layout" in LAYOUT_RENDERERS
    assert "objectives_layout" in LAYOUT_RENDERERS
    assert "discussion_layout" in LAYOUT_RENDERERS
    assert "homework_layout" in LAYOUT_RENDERERS
    assert len({LAYOUT_RENDERERS["cover_layout"], LAYOUT_RENDERERS["objectives_layout"], LAYOUT_RENDERERS["discussion_layout"], LAYOUT_RENDERERS["homework_layout"]}) == 4

    print("ROUND_017_OK")


if __name__ == "__main__":
    run()
