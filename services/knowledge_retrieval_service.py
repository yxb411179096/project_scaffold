"""RAG helpers for retrieving local knowledge base context."""

from __future__ import annotations

import json
import re
import time

from services.embedding_service import EmbeddingServiceError
from services.textbook_catalog_service import enrich_lesson_request_with_catalog
from services.vector_store_service import VectorStoreError, build_chroma_where, search_similar


GENERIC_VALUES = {"", "全部", "通用", "不限", "其他", "other", "all", "any", "general", "generic", "none"}


def _clean_text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_field(value):
    text = _clean_text(value)
    if not text or text.lower() in GENERIC_VALUES:
        return ""
    return text


def _normalize_lesson_type(value):
    text = _clean_field(value)
    if not text:
        return ""
    lowered = text.lower()
    mapping = {
        "reading": "Reading",
        "grammar": "Grammar",
        "writing": "Writing",
        "revision": "Revision",
        "listening and speaking": "Listening and Speaking",
        "listening_speaking": "Listening and Speaking",
        "listening-speaking": "Listening and Speaking",
        "listening speaking": "Listening and Speaking",
        "vocabulary": "Vocabulary",
    }
    if lowered in mapping:
        return mapping[lowered]
    return text[:1].upper() + text[1:]


def _normalize_unit(value):
    text = _clean_field(value)
    if not text:
        return ""
    compact = re.sub(r"[\s_-]+", "", text).lower()
    match = re.search(r"unit\s*([0-9]+)", text, re.I) or re.search(r"u\s*([0-9]+)", text, re.I)
    if compact.startswith("unit") and compact[4:].isdigit():
        return f"Unit {int(compact[4:])}"
    if match:
        return f"Unit {int(match.group(1))}"
    return text


def _normalize_filters_value(key, value):
    if key == "lesson_type":
        canonical = _normalize_lesson_type(value)
        if not canonical:
            return ""
        return [canonical, canonical.lower()] if canonical.lower() != canonical else canonical
    if key == "unit":
        canonical = _normalize_unit(value)
        if not canonical:
            return ""
        compact = re.sub(r"[\s_-]+", "", canonical)
        variants = [canonical, compact, compact.lower()]
        if canonical.lower() != canonical:
            variants.append(canonical.lower())
        seen = []
        for item in variants:
            if item and item not in seen:
                seen.append(item)
        return seen if len(seen) > 1 else canonical
    return _clean_field(value)


def _safe_int(value, default=5, minimum=1, maximum=10):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _manuscript_excerpt(manuscript_text, limit=360):
    text = _clean_text(manuscript_text)
    if not text:
        return ""
    return text[:limit] + ("..." if len(text) > limit else "")


def _json_safe_context(context):
    try:
        return json.loads(context) if isinstance(context, str) and context.strip() else context
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def build_knowledge_query(lesson_request, manuscript_text=None):
    """Build a semantic search query from the lesson request and manuscript context."""

    lesson_request = enrich_lesson_request_with_catalog(lesson_request or {})
    explicit_query = _clean_text(lesson_request.get("knowledge_query"))
    if explicit_query:
        return explicit_query

    topic = _clean_field(lesson_request.get("topic") or lesson_request.get("course_title"))
    reading_title = _clean_field(lesson_request.get("reading_title"))
    grade = _clean_field(lesson_request.get("grade"))
    textbook = _clean_field(lesson_request.get("textbook"))
    volume = _clean_field(lesson_request.get("volume"))
    unit = _normalize_unit(lesson_request.get("unit"))
    lesson_type = _normalize_lesson_type(lesson_request.get("lesson_type")) or "Reading"
    extra = _clean_text(lesson_request.get("extra_requirements"))
    manuscript_excerpt = _manuscript_excerpt(manuscript_text)

    descriptors = {
        "Reading": [
            "reading interest",
            "reading habit",
            "lifelong reading",
            "classroom activities",
            "useful expressions",
        ],
        "Grammar": [
            "grammar pattern",
            "guided practice",
            "classroom examples",
            "error correction",
        ],
        "Writing": [
            "writing task",
            "writing structure",
            "useful expressions",
            "drafting support",
        ],
        "Listening and Speaking": [
            "listening input",
            "speaking output",
            "pair work",
            "classroom interaction",
        ],
        "Revision": [
            "review activities",
            "key vocabulary",
            "key grammar",
            "error analysis",
        ],
        "Vocabulary": [
            "vocabulary support",
            "word learning",
            "usage examples",
        ],
    }.get(lesson_type, ["classroom activities", "teaching design", "useful expressions"])

    topic_part = topic or "senior high school English lesson"
    lesson_label = lesson_type.lower()
    base = f"{topic_part} {lesson_label} lesson for senior high school students"
    if grade:
        base += f", {grade}"
    if textbook:
        base += f", {textbook}"
    if volume:
        base += f", {volume}"
    if unit:
        base += f", {unit}"

    parts = [base]
    if reading_title:
        parts.append(reading_title)
    parts.extend(descriptors[:5])
    topic_keywords = lesson_request.get("topic_keywords") or []
    if isinstance(topic_keywords, list):
        parts.extend([_clean_text(item) for item in topic_keywords[:6] if _clean_text(item)])

    if extra:
        parts.extend([piece.strip() for piece in re.split(r"[，,。；;、\n]+", extra) if piece.strip()][:3])
    if manuscript_excerpt:
        parts.extend([piece.strip() for piece in re.split(r"[，,。；;、\n]+", manuscript_excerpt) if piece.strip()][:3])

    if topic and re.search(r"[\u4e00-\u9fff]", topic):
        parts.insert(0, f"{topic} {lesson_type} 高中英语课")
        parts.insert(1, f"{topic} {lesson_label} reading habit classroom activities")

    deduped = []
    for part in parts:
        cleaned = _clean_text(part)
        if cleaned and cleaned not in deduped:
            deduped.append(cleaned)
    return ", ".join(deduped)[:1200]


def build_knowledge_filters(lesson_request):
    """Build Chroma metadata filters with relaxed handling for generic values."""

    lesson_request = lesson_request or {}
    filters = {}
    for key in ("grade", "textbook", "volume", "unit", "lesson_type"):
        value = _normalize_filters_value(key, lesson_request.get(key))
        if value:
            filters[key] = value

    doc_type = _clean_field(lesson_request.get("doc_type") or lesson_request.get("document_type"))
    if doc_type:
        filters["doc_type"] = doc_type
    return filters


def _pick_filters(filters, keys):
    selected = {}
    for key in keys:
        if key in filters and filters.get(key):
            selected[key] = filters[key]
    return selected


def _normalize_result(result):
    if not isinstance(result, dict):
        return {}
    return {
        "document_id": result.get("document_id"),
        "title": _clean_text(result.get("title")),
        "doc_type": _clean_text(result.get("doc_type")),
        "grade": _clean_text(result.get("grade")),
        "textbook": _clean_text(result.get("textbook")),
        "volume": _clean_text(result.get("volume")),
        "unit": _clean_text(result.get("unit")),
        "lesson_type": _clean_text(result.get("lesson_type")),
        "tags": _clean_text(result.get("tags")),
        "chunk_index": result.get("chunk_index"),
        "chunk_text": _clean_text(result.get("chunk_text")),
        "distance": result.get("distance"),
        "score": result.get("score"),
        "document_title": _clean_text(result.get("document_title")),
        "document_doc_type": _clean_text(result.get("document_doc_type")),
        "document_grade": _clean_text(result.get("document_grade")),
        "document_textbook": _clean_text(result.get("document_textbook")),
        "document_volume": _clean_text(result.get("document_volume")),
        "document_unit": _clean_text(result.get("document_unit")),
        "document_lesson_type": _clean_text(result.get("document_lesson_type")),
        "document_tags": _clean_text(result.get("document_tags")),
    }


def retrieve_knowledge_context(lesson_request, query=None, top_k=5, manuscript_text=None):
    """Retrieve semantic references from ChromaDB with graceful fallback."""

    lesson_request = lesson_request or {}
    started = time.perf_counter()
    search_query = _clean_text(query) or build_knowledge_query(lesson_request, manuscript_text)
    requested_top_k = _safe_int(top_k or lesson_request.get("knowledge_top_k") or 5, default=5)
    base_filters = build_knowledge_filters(lesson_request)
    stages = [
        ("exact", _pick_filters(dict(base_filters), ("textbook", "volume", "unit", "lesson_type"))),
        ("without_lesson_type", _pick_filters(dict(base_filters), ("textbook", "volume", "unit"))),
        ("without_unit", _pick_filters(dict(base_filters), ("textbook", "volume"))),
        ("textbook_only", _pick_filters(dict(base_filters), ("textbook",))),
        ("no_filters", {}),
    ]
    if not base_filters:
        stages = [("no_filters", {})]

    used_filters = {}
    relaxed = False
    relaxed_level = "exact" if base_filters else "no_filters"
    error_message = ""
    results = []

    try:
        for index, (label, filters) in enumerate(stages):
            safe_where = build_chroma_where(filters)
            used_filters = filters if safe_where is not None else {}
            results = search_similar(search_query, filters=filters, top_k=requested_top_k)
            if results:
                relaxed = index > 0
                relaxed_level = label
                break
        else:
            results = []
    except (EmbeddingServiceError, VectorStoreError) as exc:
        error_message = str(exc)
    except Exception as exc:  # pragma: no cover - defensive fallback
        error_message = f"语义检索失败：{exc}"

    normalized_results = [_normalize_result(item) for item in results or []]
    duration_ms = int((time.perf_counter() - started) * 1000)
    failed = bool(error_message)
    return {
        "enabled": bool(lesson_request.get("use_knowledge_base")),
        "ok": not failed,
        "failed": failed,
        "error": error_message,
        "query": search_query,
        "top_k": requested_top_k,
        "used_filters": used_filters,
        "relaxed": relaxed,
        "relaxed_level": relaxed_level,
        "results": normalized_results,
        "result_count": len(normalized_results),
        "trace": {
            "type": "knowledge_retrieval",
            "query": search_query,
            "top_k": requested_top_k,
            "filters": used_filters,
            "result_count": len(normalized_results),
            "relaxed": relaxed,
            "relaxed_level": relaxed_level,
            "failed": failed,
            "error": error_message,
            "duration_ms": duration_ms,
        },
    }


def format_knowledge_context_for_prompt(context):
    """Format retrieved knowledge context for agent prompts."""

    context = context or {}
    results = list(context.get("results") or [])
    if not results:
        if context.get("error"):
            return f"Knowledge retrieval warning: {context['error']}"
        return "No knowledge base references were found."

    lines = [
        "以下是从本地教学资料知识库检索到的参考资料。请优先参考这些资料，但不要机械复制。若用户文案与知识库冲突，以用户文案为准。",
        f"检索语句：{_clean_text(context.get('query'))}",
        f"命中数量：{len(results)}",
    ]
    if context.get("relaxed"):
        lines.append("说明：本次检索放宽了筛选条件。")

    total_chars = 0
    for index, item in enumerate(results[:5], start=1):
        chunk_text = _clean_text(item.get("chunk_text"))[:800]
        block = [
            f"【知识库参考资料 {index}】",
            f"标题：{_clean_text(item.get('title') or item.get('document_title')) or '未命名资料'}",
            f"类型：{_clean_text(item.get('doc_type') or item.get('document_doc_type')) or '—'}",
            f"年级/教材/册别/单元/课型：{_clean_text(item.get('grade') or item.get('document_grade')) or '—'} / {_clean_text(item.get('textbook') or item.get('document_textbook')) or '—'} / {_clean_text(item.get('volume') or item.get('document_volume')) or '—'} / {_clean_text(item.get('unit') or item.get('document_unit')) or '—'} / {_clean_text(item.get('lesson_type') or item.get('document_lesson_type')) or '—'}",
            f"相似度：{item.get('score') if item.get('score') is not None else '—'}",
            f"距离：{item.get('distance') if item.get('distance') is not None else '—'}",
            f"内容：{chunk_text}",
        ]
        block_text = "\n".join(block).strip()
        projected = total_chars + len(block_text)
        if projected > 6000:
            break
        lines.append(block_text)
        total_chars = projected

    prompt_text = "\n\n".join(lines).strip()
    return prompt_text[:6000]


def load_knowledge_context(value):
    """Deserialize a stored knowledge context payload if possible."""

    if isinstance(value, dict):
        return value
    if not value:
        return None
    return _json_safe_context(value)
