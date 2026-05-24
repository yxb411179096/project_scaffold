import re


def safe_course_filename(task, suffix):
    course_title = (task.get("course_title") or "lesson").strip()
    safe_title = re.sub(r'[\\/:*?"<>|]+', "_", course_title)
    safe_title = re.sub(r"\s+", "_", safe_title).strip("._")
    safe_title = safe_title or f"lesson_{task.get('id', 'task')}"
    return f"lesson_{task.get('id', 'task')}_{safe_title}_{suffix}"
