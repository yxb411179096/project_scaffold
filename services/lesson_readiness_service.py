"""Lesson knowledge readiness checks before generation."""

from __future__ import annotations

from services.knowledge_governance_service import get_knowledge_coverage
from models.database import query_knowledge_documents


def _clean(v):
    return str(v or "").strip()


def _is_placeholder(doc):
    return _clean(doc.get("doc_type")) == "其他" and ("资料占位" in _clean(doc.get("title")) or "资料占位" in _clean(doc.get("tags")))


def _coverage_unit(textbook, volume, unit):
    coverage = get_knowledge_coverage().get("textbooks", [])
    for group in coverage:
        if _clean(group.get("textbook")) == textbook and _clean(group.get("volume")) == volume:
            for row in group.get("units", []):
                if _clean(row.get("unit")) == unit:
                    return row
    return None


def _required_for_lesson_type(lesson_type):
    lt = _clean(lesson_type).lower()
    if lt == "reading":
        return ["has_textbook", "has_reading", "has_lesson_plan", "has_vocabulary"]
    if lt == "writing":
        return ["has_writing", "has_lesson_plan"]
    if lt == "grammar":
        return ["has_grammar", "has_lesson_plan"]
    return ["has_textbook", "has_lesson_plan"]


def check_lesson_knowledge_readiness(lesson_request):
    textbook = _clean(lesson_request.get("textbook"))
    grade = _clean(lesson_request.get("grade"))
    volume = _clean(lesson_request.get("volume"))
    unit = _clean(lesson_request.get("unit"))
    lesson_type = _clean(lesson_request.get("lesson_type"))
    topic = _clean(lesson_request.get("topic"))

    matched = _coverage_unit(textbook, volume, unit) or {
        "unit": unit,
        "theme": "",
        "has_textbook": False,
        "has_reading": False,
        "has_vocabulary": False,
        "has_lesson_plan": False,
        "has_writing": False,
        "has_grammar": False,
        "indexed_count": 0,
        "missing": [],
    }

    docs = query_knowledge_documents({"textbook": textbook, "volume": volume, "unit": unit}, limit=200)
    effective_docs = [d for d in docs if not _is_placeholder(d)]
    whole_book_only = bool(effective_docs) and all(bool(d.get("is_whole_book")) for d in effective_docs)

    has_textbook = bool(matched.get("has_textbook"))
    has_reading = bool(matched.get("has_reading"))
    has_vocabulary = bool(matched.get("has_vocabulary"))
    has_lesson_plan = bool(matched.get("has_lesson_plan"))
    has_writing = bool(matched.get("has_writing"))
    has_grammar = bool(matched.get("has_grammar"))
    indexed_count = int(matched.get("indexed_count") or 0)

    score = 0
    if has_textbook:
        score += 20
    if has_lesson_plan:
        score += 20
    if has_vocabulary:
        score += 15
    if indexed_count > 0:
        score += 20

    lt = lesson_type.lower()
    has_type_material = False
    if lt == "reading":
        has_type_material = has_reading
    elif lt == "writing":
        has_type_material = has_writing
    elif lt == "grammar":
        has_type_material = has_grammar
    else:
        has_type_material = has_textbook or has_lesson_plan
    if has_type_material:
        score += 25

    required = _required_for_lesson_type(lesson_type)
    check_map = {
        "has_textbook": has_textbook,
        "has_reading": has_reading,
        "has_vocabulary": has_vocabulary,
        "has_lesson_plan": has_lesson_plan,
        "has_writing": has_writing,
        "has_grammar": has_grammar,
    }
    missing = [key for key in required if not check_map.get(key)]
    missing_labels = {
        "has_textbook": "教材内容",
        "has_reading": "Reading 课文",
        "has_vocabulary": "词汇表",
        "has_lesson_plan": "教案",
        "has_writing": "Writing 资料",
        "has_grammar": "Grammar 资料",
    }
    missing_human = [missing_labels[m] for m in missing]

    recommendations = []
    if whole_book_only:
        recommendations.append("当前以整本教材为主，建议补充单元级资料。")
    if missing_human:
        recommendations.append("建议补充：" + "、".join(missing_human))
    if indexed_count <= 0:
        recommendations.append("当前单元缺少可用索引资料，知识库增强可能无法发挥作用。")

    if indexed_count <= 0 and not effective_docs:
        status = "missing"
    elif whole_book_only or missing_human:
        status = "warning"
    else:
        status = "ready"

    supplement_links = [
        {
            "label": "去补充本单元资料",
            "url": f"/knowledge/unit-supplement?textbook={textbook}&volume={volume}&unit={unit}",
        },
        {
            "label": "打开资料覆盖情况",
            "url": f"/knowledge/coverage?volume={volume}&highlight_unit={unit}&highlight_volume={volume}",
        },
    ]

    return {
        "status": status,
        "score": max(0, min(100, score)),
        "matched_unit": matched,
        "has_textbook": has_textbook,
        "has_reading": has_reading,
        "has_vocabulary": has_vocabulary,
        "has_lesson_plan": has_lesson_plan,
        "has_writing": has_writing,
        "has_grammar": has_grammar,
        "indexed_count": indexed_count,
        "missing": missing_human,
        "recommendations": recommendations,
        "supplement_links": supplement_links,
        "lesson_request": {
            "textbook": textbook,
            "grade": grade,
            "volume": volume,
            "unit": unit,
            "lesson_type": lesson_type,
            "topic": topic,
        },
    }

