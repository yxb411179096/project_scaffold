"""Knowledge base governance helpers (rule-based, no LLM)."""

from __future__ import annotations

import hashlib
import json
import re

from models.database import (
    create_knowledge_document,
    get_db,
    get_knowledge_document,
    now,
    query_knowledge_documents,
    update_knowledge_document,
)
from services.document_parse_service import clean_extracted_text
from services.textbook_catalog_service import CATALOG, normalize_unit


WHOLE_BOOK_MARKERS = ["全册", "整本", "教材整本", "必修一.pdf", "必修二.pdf", "必修三.pdf"]


def _clean(value):
    return str(value or "").strip()


def _valid(value):
    text = _clean(value)
    return bool(text and text not in {"通用", "Other", "其他"})


def _unit_from_text(text):
    m = re.search(r"unit\s*([0-9]+)", str(text or ""), re.I)
    return f"Unit {int(m.group(1))}" if m else ""


def evaluate_document_metadata(document):
    doc = document or {}
    title = _clean(doc.get("title"))
    file_name = _clean(doc.get("file_name"))
    doc_type = _clean(doc.get("doc_type"))
    grade = _clean(doc.get("grade"))
    textbook = _clean(doc.get("textbook"))
    volume = _clean(doc.get("volume"))
    unit = _clean(doc.get("unit"))
    lesson_type = _clean(doc.get("lesson_type"))
    tags = _clean(doc.get("tags"))
    haystack = f"{title} {file_name}"

    score = 0
    missing = []
    warnings = []
    recs = []

    checks = [
        ("title", _valid(title), 10),
        ("doc_type", _valid(doc_type), 15),
        ("grade", _valid(grade), 10),
        ("textbook", _valid(textbook), 10),
        ("volume", _valid(volume), 15),
        ("unit", _valid(unit), 15),
        ("lesson_type", _valid(lesson_type), 15),
        ("tags", _valid(tags), 10),
    ]
    for key, ok, pts in checks:
        if ok:
            score += pts
        else:
            missing.append(key)

    normalized_unit = normalize_unit(unit)
    inferred_unit = _unit_from_text(haystack)
    if inferred_unit and normalized_unit and inferred_unit != normalized_unit:
        warnings.append(f"标题/文件名疑似 {inferred_unit}，但当前 unit 为 {normalized_unit}。")
        score -= 8
    elif inferred_unit and not normalized_unit:
        warnings.append(f"标题/文件名疑似 {inferred_unit}，建议补充 unit。")
        recs.append(f"将 unit 设置为 {inferred_unit}")
        score -= 5

    inferred_volume = ""
    for v in ("必修一", "必修二", "必修三", "选择性必修一", "选择性必修二", "选择性必修三"):
        if v in haystack:
            inferred_volume = v
            break
    if inferred_volume and volume and inferred_volume != volume:
        warnings.append(f"标题/文件名疑似 {inferred_volume}，但当前 volume 为 {volume}。")
        score -= 8

    is_whole_book = any(marker.lower() in haystack.lower() for marker in WHOLE_BOOK_MARKERS)
    if is_whole_book:
        recs.append("该资料疑似整本教材，建议按 Unit 补充单元级资料。")
        if not normalized_unit or unit == "通用":
            # whole book docs can omit unit
            score = max(score, 60)

    score = max(0, min(100, score))
    if missing:
        recs.append("补全元信息字段: " + ", ".join(missing))

    return {
        "score": score,
        "warnings": warnings,
        "is_whole_book": is_whole_book,
        "missing_fields": missing,
        "recommendations": recs,
    }


def suggest_metadata(document):
    doc = document or {}
    title = _clean(doc.get("title"))
    file_name = _clean(doc.get("file_name"))
    parsed_text = _clean(doc.get("parsed_text"))[:3000]
    blob = f"{title}\n{file_name}\n{parsed_text}"
    head_blob = f"{title}\n{file_name}"
    is_whole_book = evaluate_document_metadata(doc).get("is_whole_book", False)

    suggested = {
        "suggested_title": "",
        "suggested_doc_type": "",
        "suggested_grade": "",
        "suggested_textbook": "",
        "suggested_volume": "",
        "suggested_unit": "",
        "suggested_lesson_type": "",
        "suggested_tags": "",
    }

    if "人教版" in blob:
        suggested["suggested_textbook"] = "人教版"
    if "高一" in blob:
        suggested["suggested_grade"] = "高一"
    if "高二" in blob:
        suggested["suggested_grade"] = "高二"
    if "高三" in blob:
        suggested["suggested_grade"] = "高三"

    for v in ("必修一", "必修二", "必修三", "选择性必修一", "选择性必修二", "选择性必修三"):
        if v in blob:
            suggested["suggested_volume"] = v
            break
    unit = _unit_from_text(blob)
    if unit:
        suggested["suggested_unit"] = unit

    lowered_blob = blob.lower()
    lowered_head = head_blob.lower()
    if is_whole_book:
        suggested["suggested_lesson_type"] = "Other"
    else:
        if "reading for writing" in lowered_head:
            suggested["suggested_lesson_type"] = "Writing"
        elif "reading and thinking" in lowered_head:
            suggested["suggested_lesson_type"] = "Reading"
        elif "discovering useful structures" in lowered_head or " grammar " in f" {lowered_head} ":
            suggested["suggested_lesson_type"] = "Grammar"
        elif "words and expressions" in lowered_head or "vocabulary" in lowered_head:
            suggested["suggested_lesson_type"] = "Vocabulary"
        elif "reading and thinking" in lowered_blob:
            suggested["suggested_lesson_type"] = "Reading"

    if "教案" in blob:
        suggested["suggested_doc_type"] = "教案"
    elif "教材" in blob:
        suggested["suggested_doc_type"] = "教材"
    elif "课文" in blob:
        suggested["suggested_doc_type"] = "课文"

    # Try infer theme from catalog
    textbook = suggested["suggested_textbook"] or _clean(doc.get("textbook"))
    volume = suggested["suggested_volume"] or _clean(doc.get("volume"))
    unit_value = suggested["suggested_unit"] or normalize_unit(doc.get("unit"))
    meta = (CATALOG.get(textbook, {}).get(volume, {}) or {}).get(unit_value, {})
    if meta and meta.get("theme"):
        suggested["suggested_title"] = f"{textbook}_{volume}_{unit_value}_{meta.get('theme')}"
        suggested["suggested_tags"] = ",".join(
            [meta.get("theme", ""), meta.get("reading_title", ""), "Reading and Thinking"]
        ).strip(",")
    elif not suggested["suggested_tags"] and _clean(doc.get("tags")):
        suggested["suggested_tags"] = _clean(doc.get("tags"))

    # Never degrade existing valid metadata to empty in suggestions.
    for field, src in (
        ("suggested_doc_type", "doc_type"),
        ("suggested_grade", "grade"),
        ("suggested_textbook", "textbook"),
        ("suggested_volume", "volume"),
        ("suggested_unit", "unit"),
        ("suggested_lesson_type", "lesson_type"),
    ):
        if not _clean(suggested[field]) and _valid(doc.get(src)):
            suggested[field] = _clean(doc.get(src))

    if not _clean(suggested["suggested_title"]) and _valid(doc.get("title")):
        suggested["suggested_title"] = _clean(doc.get("title"))

    return suggested


def update_document_metadata_quality(document):
    doc = document if isinstance(document, dict) else get_knowledge_document(document)
    if not doc:
        return None
    report = evaluate_document_metadata(doc)
    payload = dict(doc)
    payload.update(
        {
            "metadata_quality_score": report["score"],
            "metadata_warnings": json.dumps(report["warnings"], ensure_ascii=False),
            "is_whole_book": 1 if report["is_whole_book"] else 0,
        }
    )
    return update_knowledge_document(doc["id"], payload)


def get_knowledge_coverage():
    docs = query_knowledge_documents({}, limit=2000)
    coverage = []
    for textbook, volumes in CATALOG.items():
        for volume, units in volumes.items():
            unit_rows = []
            for unit, meta in units.items():
                unit_docs = [d for d in docs if _clean(d.get("textbook")) == textbook and _clean(d.get("volume")) == volume and normalize_unit(d.get("unit")) == unit]
                # Placeholder records should not count as real coverage.
                effective_docs = [
                    d
                    for d in unit_docs
                    if not (
                        _clean(d.get("doc_type")) == "其他"
                        and ("资料占位" in _clean(d.get("title")) or "资料占位" in _clean(d.get("tags")))
                    )
                ]
                has_textbook = any(d.get("doc_type") == "教材" for d in effective_docs)
                has_reading = any(_clean(d.get("lesson_type")) == "Reading" for d in effective_docs)
                has_vocab = any(_clean(d.get("lesson_type")) == "Vocabulary" or d.get("doc_type") == "词汇表" for d in effective_docs)
                has_plan = any(d.get("doc_type") in {"教案", "讲稿", "说课稿"} for d in effective_docs)
                has_writing = any(_clean(d.get("lesson_type")) == "Writing" for d in effective_docs)
                missing = []
                if not has_reading:
                    missing.append("Reading")
                if not has_vocab:
                    missing.append("Vocabulary")
                if not has_plan:
                    missing.append("教案")
                if not has_writing:
                    missing.append("Writing")
                unit_rows.append(
                    {
                        "unit": unit,
                        "theme": meta.get("theme", ""),
                        "reading_title": meta.get("reading_title", ""),
                        "has_textbook": has_textbook,
                        "has_reading": has_reading,
                        "has_vocabulary": has_vocab,
                        "has_lesson_plan": has_plan,
                        "has_writing": has_writing,
                        "indexed_count": sum(1 for d in effective_docs if d.get("embedding_status") == "indexed"),
                        "missing": missing,
                        "doc_count": len(effective_docs),
                    }
                )
            coverage.append({"textbook": textbook, "volume": volume, "units": unit_rows})
    return {"textbooks": coverage}


def create_unit_placeholders(textbook, volume):
    textbook = _clean(textbook)
    volume = _clean(volume)
    units = CATALOG.get(textbook, {}).get(volume, {}) or {}
    created = 0
    for unit, meta in units.items():
        title = f"{textbook}_高一_{volume}_{unit}_{meta.get('theme','')}_资料占位"
        existing = query_knowledge_documents(
            {"textbook": textbook, "volume": volume, "unit": unit, "keyword": "资料占位"},
            limit=5,
        )
        if any(_clean(d.get("title")) == title for d in existing):
            continue
        payload = {
            "title": title,
            "doc_type": "其他",
            "grade": "高一",
            "textbook": textbook,
            "volume": volume,
            "unit": unit,
            "lesson_type": "Other",
            "source_type": "text",
            "file_name": "",
            "original_file_path": "",
            "text_file_path": "",
            "parsed_text": "",
            "summary": "等待补充该单元资料",
            "word_count": 0,
            "tags": "资料占位",
            "status": "pending",
            "error_message": "",
            "embedding_status": "not_indexed",
            "chunk_count": 0,
            "vector_collection": "",
            "embedding_error": "",
            "source_unit_key": f"{textbook}|{volume}|{unit}",
            "indexed_at": "",
        }
        create_knowledge_document(payload)
        created += 1
    return created


def documents_need_reindex():
    docs = query_knowledge_documents({}, limit=2000)
    needs = []
    for doc in docs:
        parsed = clean_extracted_text(doc.get("parsed_text") or "")
        text_hash = hashlib.sha1(parsed.encode("utf-8", errors="ignore")).hexdigest() if parsed else ""
        indexed = doc.get("embedding_status") == "indexed"
        chunk_count = int(doc.get("chunk_count") or 0)
        indexed_hash = _clean(doc.get("last_indexed_text_hash"))

        # Backfill hash for historical indexed docs that missed this field.
        if indexed and chunk_count > 0 and parsed and not indexed_hash:
            update_knowledge_document(
                doc["id"],
                {
                    **dict(doc),
                    "last_indexed_text_hash": text_hash,
                    "updated_at": now(),
                },
            )
            indexed_hash = text_hash

        stale_hash = bool(parsed and indexed_hash and indexed_hash != text_hash)
        need = (
            (not indexed and bool(parsed))
            or (indexed and chunk_count == 0 and bool(parsed))
            or stale_hash
        )
        if need:
            item = dict(doc)
            item["_computed_text_hash"] = text_hash
            needs.append(item)
    return needs
