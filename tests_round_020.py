from services.layout_template_service import get_template, get_template_for_slide
from services.agents.layout_planner_agent import plan_layout_for_slide
from services.ppt_quality_check_service import check_ppt_quality
from services.ppt_render_service import export_pptx


def _task():
    return {
        "id": 20001,
        "course_title": "[TEST] Round20 Template",
        "topic": "The Internet",
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修二",
        "unit": "Unit 3",
        "lesson_type": "Reading",
        "duration": 45,
        "student_level": "中等",
        "style": "常规课",
    }


def run():
    # 1 template lookup
    t = get_template_for_slide("careful_reading")
    assert t.get("template_name") == "careful_reading_question_evidence_template"

    # 2 careful_reading no big-label dominated defaults
    plan = plan_layout_for_slide(
        {"slide_type": "careful_reading", "title": "Careful Reading", "visible_content": ["Q", "Evidence", "Task"]},
        _task(),
    )
    assert plan.get("layout_template", {}).get("name") == "careful_reading_question_evidence_template"

    # 3 summary not only Topic/Skill/Language placeholders in visible output
    s_plan = plan_layout_for_slide(
        {"slide_type": "summary", "title": "Summary", "visible_content": ["The Internet changes lives.", "Read with evidence.", "Share ideas clearly."]},
        _task(),
    )
    assert s_plan.get("layout_template", {}).get("name") == "summary_three_takeaways_template"

    # 4 vocabulary template avoids Item placeholders in default data
    v_plan = plan_layout_for_slide(
        {"slide_type": "vocabulary_focus", "title": "Vocabulary", "visible_content": []},
        _task(),
    )
    cards = (v_plan.get("graphic_data") or {}).get("cards") or []
    assert cards
    assert all("item " not in str((c.get("word") or "")).lower() for c in cards)

    # 5 min font checks
    assert get_template("summary_three_takeaways_template").get("min_font_size", 0) >= 14
    assert get_template("objectives_cards_template").get("body_font_size", 0) >= 18

    # 6 template render compatibility (old slide can still export)
    old_slide = {
        "slide_index": 1,
        "slide_type": "cover",
        "title": "Legacy Cover",
        "visible_content": ["Unit 3", "Reading"],
        "teacher_notes": "notes",
        "teaching_purpose": "open class",
        "estimated_time": "2 min",
        "interaction_type": "Teacher-student interaction",
    }
    path = export_pptx(_task(), [old_slide])
    assert path.exists()

    # 7 quality check recognizes big label small body risk
    report = check_ppt_quality(
        _task(),
        [
            {
                "slide_index": 1,
                "slide_type": "summary",
                "title": "Summary",
                "visible_content": ["a", "b", "c", "d", "e", "f", "g"],
                "teacher_notes": "long enough teacher notes for checking quality risks in this slide.",
                "layout_plan": {
                    "layout_type": "mindmap_layout",
                    "layout_template": {
                        "template_name": "bad_template",
                        "max_blocks": 2,
                        "max_items_per_block": 1,
                        "label_font_size": 20,
                        "body_font_size": 12,
                        "min_font_size": 12,
                    },
                },
            }
        ],
    )
    codes = {d["code"] for s in report["slides"] for d in s.get("issue_details", [])}
    assert "big_label_small_body_risk" in codes

    print("ROUND_020_OK")


if __name__ == "__main__":
    run()
