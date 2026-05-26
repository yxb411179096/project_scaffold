from services.ppt_quality_check_service import check_ppt_quality
from services.ppt_render_service import (
    normalize_bullets,
    truncate_text,
    fit_font_size,
    export_pptx,
)


def _task():
    return {
        "id": 18001,
        "course_title": "[TEST] Round18 Render",
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
    # 1) normalize_bullets limits count and line length
    bullets = normalize_bullets(
        [
            "A" * 120,
            "b2",
            "b3",
            "b4",
            "b5",
            "b6",
        ],
        max_items=5,
        max_chars_each=30,
    )
    assert len(bullets) == 5
    assert all(len(item) <= 30 for item in bullets)

    # 2) truncate_text
    assert truncate_text("abcdef", 4) == "a..."
    assert truncate_text("abc", 10) == "abc"

    # 3) fit_font_size shrinks long text
    short_size = fit_font_size("Short title", 4.0, 0.8, max_size=30, min_size=14)
    long_size = fit_font_size("This is a much longer title that should use a smaller font size", 4.0, 0.8, max_size=30, min_size=14)
    assert long_size <= short_size

    # 4/5) quality checker catches too many/too long bullets
    slides = [
        {
            "slide_index": 1,
            "slide_type": "fast_reading",
            "title": "Fast Reading Task",
            "visible_content": [
                "line1",
                "line2",
                "line3",
                "line4",
                "line5",
                "line6",
                "This is an excessively long bullet " + ("x" * 130),
            ],
            "teacher_notes": "notes",
            "layout_plan": {"layout_type": "reading_task_layout"},
        }
    ]
    report = check_ppt_quality(_task(), slides)
    issue_codes = {
        d["code"]
        for slide in report["slides"]
        for d in slide.get("issue_details", [])
    }
    assert "too_many_bullets" in issue_codes
    assert "bullet_too_long" in issue_codes

    # 6/7) render with long content + image suggestion should not fail
    render_slides = [
        {
            "slide_index": 1,
            "slide_type": "cover",
            "title": "Unit 3 The Internet Reading Lesson with a very long title to test sizing stability",
            "visible_content": ["This content is intentionally long " * 8],
            "teacher_notes": "Detailed notes for the teacher script.",
            "teaching_purpose": "Open the lesson clearly.",
            "estimated_time": "2 min",
            "interaction_type": "Teacher-student interaction",
            "image_suggestion": "online community and digital life scene",
            "layout_plan": {"layout_type": "cover_layout"},
        }
    ]
    path = export_pptx(_task(), render_slides)
    assert path.exists()
    assert path.suffix.lower() == ".pptx"

    print("ROUND_018_OK")


if __name__ == "__main__":
    run()
