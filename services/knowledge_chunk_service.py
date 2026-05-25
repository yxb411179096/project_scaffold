"""Knowledge chunking helpers for semantic indexing.

These utilities are deterministic and do not call any external service.
"""

from __future__ import annotations

import re

from services.document_parse_service import clean_extracted_text


def _normalize_text(text):
    return clean_extracted_text(text or "")


def _split_by_sentence(text):
    parts = re.split(r"(?<=[。！？!?；;.!?])\s+", text)
    return [part.strip() for part in parts if part and part.strip()]


def _flush_buffer(buffer, chunks, max_chars):
    if not buffer:
        return ""
    chunk = "\n".join(buffer).strip()
    if chunk:
        chunks.append(chunk[: max_chars * 2])
    return ""


def split_text_into_chunks(text, max_chars=800, overlap=120):
    """Split mixed Chinese/English text into semantic chunks.

    The default size keeps most chunks in the 500-1000 character range.
    """

    normalized = _normalize_text(text)
    if not normalized:
        return []

    paragraphs = [part.strip() for part in re.split(r"\n{2,}", normalized) if part and part.strip()]
    raw_chunks = []
    buffer = []
    buffer_len = 0

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            buffer_len = 0
            _flush_buffer(buffer, raw_chunks, max_chars)
            buffer = []
            sentences = _split_by_sentence(paragraph) or [paragraph]
            sentence_buffer = []
            sentence_len = 0
            for sentence in sentences:
                if sentence_len and sentence_len + len(sentence) + 1 > max_chars:
                    _flush_buffer(sentence_buffer, raw_chunks, max_chars)
                    sentence_buffer = []
                    sentence_len = 0
                sentence_buffer.append(sentence)
                sentence_len += len(sentence) + 1
            _flush_buffer(sentence_buffer, raw_chunks, max_chars)
            continue

        projected = buffer_len + len(paragraph) + (2 if buffer else 0)
        if buffer and projected > max_chars:
            _flush_buffer(buffer, raw_chunks, max_chars)
            buffer = []
            buffer_len = 0

        buffer.append(paragraph)
        buffer_len += len(paragraph) + (2 if len(buffer) > 1 else 0)

    _flush_buffer(buffer, raw_chunks, max_chars)

    chunks = []
    for index, chunk in enumerate(raw_chunks):
        cleaned_chunk = chunk.strip()
        if not cleaned_chunk:
            continue
        if overlap > 0 and chunks:
            previous_tail = chunks[-1][-overlap:].strip()
            if previous_tail and not cleaned_chunk.startswith(previous_tail):
                cleaned_chunk = f"{previous_tail}\n{cleaned_chunk}".strip()
        chunks.append(cleaned_chunk)
    return [chunk for chunk in chunks if chunk.strip()]


def build_chunk_metadata(document, chunk_index):
    return {
        "document_id": int(document.get("id") or 0),
        "title": str(document.get("title") or "").strip(),
        "doc_type": str(document.get("doc_type") or "").strip(),
        "grade": str(document.get("grade") or "").strip(),
        "textbook": str(document.get("textbook") or "").strip(),
        "volume": str(document.get("volume") or "").strip(),
        "unit": str(document.get("unit") or "").strip(),
        "lesson_type": str(document.get("lesson_type") or "").strip(),
        "tags": str(document.get("tags") or "").strip(),
        "chunk_index": int(chunk_index),
    }


def estimate_token_count(text):
    content = str(text or "").strip()
    if not content:
        return 0
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", content))
    english_words = len(re.findall(r"[A-Za-z0-9']+", content))
    return max(1, int(chinese_chars * 1.2 + english_words * 1.3))


def summarize_chunk_text(text, max_chars=160):
    cleaned = _normalize_text(text)
    if not cleaned:
        return ""
    compact = re.sub(r"\s+", " ", cleaned).strip()
    return compact[:max_chars]
