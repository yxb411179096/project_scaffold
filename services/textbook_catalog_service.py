"""Textbook catalog service for deterministic unit/topic mapping.

Current stage: local rule-based catalog.
Future replacement: can be expanded to full textbook metadata storage.
"""

import re


RENJIAO_REQUIRED_1 = {
    "Unit 1": {
        "theme": "Teenage Life",
    },
    "Unit 2": {
        "theme": "Travelling Around",
    },
    "Unit 3": {
        "theme": "Sports and Fitness",
    },
    "Unit 4": {
        "theme": "Natural Disasters",
    },
    "Unit 5": {
        "theme": "Languages Around the World",
    },
}

RENJIAO_REQUIRED_2 = {
    "Unit 1": {
        "theme": "Cultural Heritage",
    },
    "Unit 2": {
        "theme": "Wildlife Protection",
    },
    "Unit 3": {
        "theme": "The Internet",
        "reading_title": "Stronger Together: How We Have Been Changed by the Internet",
        "reading_skill": "Read headlines",
        "keywords": ["online community", "internet", "digital life", "reading headlines"],
    },
    "Unit 4": {
        "theme": "History and Traditions",
    },
    "Unit 5": {
        "theme": "Music",
    },
}

RENJIAO_REQUIRED_3 = {
    "Unit 1": {"theme": "Festivals and Celebrations"},
    "Unit 2": {"theme": "Morals and Virtues"},
    "Unit 3": {"theme": "Diverse Cultures"},
    "Unit 4": {"theme": "Space Exploration"},
    "Unit 5": {"theme": "The Value of Money"},
}

CATALOG = {
    "人教版": {
        "必修一": RENJIAO_REQUIRED_1,
        "必修二": RENJIAO_REQUIRED_2,
        "必修三": RENJIAO_REQUIRED_3,
    }
}


def _clean_text(value):
    return str(value or "").strip()


def normalize_unit(value):
    text = _clean_text(value)
    if not text:
        return ""
    compact = re.sub(r"[\s_-]+", "", text).lower()
    if compact.startswith("unit") and compact[4:].isdigit():
        return f"Unit {int(compact[4:])}"
    match = re.search(r"unit\s*([0-9]+)", text, flags=re.I)
    if match:
        return f"Unit {int(match.group(1))}"
    return text


def get_unit_metadata(textbook, volume, unit):
    textbook_name = _clean_text(textbook)
    volume_name = _clean_text(volume)
    unit_name = normalize_unit(unit)
    unit_map = CATALOG.get(textbook_name, {}).get(volume_name, {})
    return dict(unit_map.get(unit_name) or {})


def enrich_lesson_request_with_catalog(lesson_request):
    """Fill topic/reading metadata from catalog when textbook-volume-unit are known."""

    req = dict(lesson_request or {})
    metadata = get_unit_metadata(req.get("textbook"), req.get("volume"), req.get("unit"))
    if not metadata:
        return req

    lesson_type = _clean_text(req.get("lesson_type")).lower()
    topic = _clean_text(req.get("topic"))
    if not topic or topic.lower().startswith("unit ") or topic.lower() == "senior english lesson":
        req["topic"] = metadata.get("theme") or topic or "Senior English Lesson"

    if lesson_type == "reading" and metadata.get("reading_title"):
        req["reading_title"] = metadata["reading_title"]
        req["reading_skill"] = metadata.get("reading_skill") or ""
    if metadata.get("keywords"):
        req["topic_keywords"] = list(metadata["keywords"])

    return req


def build_catalog_course_title(lesson_request):
    """Build a consistent course title for export naming and display."""

    req = enrich_lesson_request_with_catalog(lesson_request)
    unit = normalize_unit(req.get("unit")) or "Unit"
    lesson_type = _clean_text(req.get("lesson_type")) or "Lesson"
    topic = _clean_text(req.get("topic"))
    if topic:
        return f"{unit} {topic} {lesson_type} Lesson"
    return _clean_text(req.get("course_title")) or "Senior English Lesson"
