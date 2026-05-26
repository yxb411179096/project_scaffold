from services.knowledge_retrieval_service import build_knowledge_query
from services.ppt_quality_check_service import check_ppt_quality


def _task():
    return {
        "id": 21101,
        "course_title": "Unit 3 The Internet Reading Lesson",
        "topic": "The Internet",
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修二",
        "unit": "Unit 3",
        "lesson_type": "Reading",
        "duration": 45,
        "student_level": "中等",
        "style": "常规课",
        "ppt_style": "reading_focus",
    }


def run():
    # 1) Unit 3 Reading query boost terms
    q = build_knowledge_query(_task())
    lowered = q.lower()
    assert "the internet" in lowered
    assert "stronger together" in lowered
    assert "jan tchamani" in lowered
    assert "online community" in lowered
    assert "digital divide" in lowered
    assert "reading and thinking" in lowered

    # 2) quality detail includes code/severity suggestions
    slides = [
        {
            "slide_index": 6,
            "slide_type": "summary",
            "title": "Summary",
            "visible_content": ["Topic...", "Skill...", "Language..."],
            "teacher_notes": "short",
            "layout_plan": {"layout_type": "reading_task_layout"},
        }
    ]
    report = check_ppt_quality(_task(), slides)
    details = report["slides"][0]["issue_details"]
    assert details and all("code" in d and "severity" in d and "suggestion" in d for d in details)

    print("ROUND_0211_OK")


if __name__ == "__main__":
    run()
