"""PDF page-range based split service.

Stage 0.27.0:
- No OCR
- No physical PDF split
- Extract by page ranges with optional page offset
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from services.document_parse_service import clean_extracted_text, count_text_words


def _safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_pdf_page_count(document):
    doc = document or {}
    path = str(doc.get("original_file_path") or "").strip()
    if not path:
        return {"page_count": 0, "pdf_path": "", "available": False, "error": "资料缺少原始 PDF 路径。"}
    pdf_path = Path(path)
    if not pdf_path.exists() or not pdf_path.is_file():
        return {"page_count": 0, "pdf_path": path, "available": False, "error": "PDF 文件不存在。"}
    if pdf_path.suffix.lower() != ".pdf":
        return {"page_count": 0, "pdf_path": path, "available": False, "error": "当前资料不是 PDF 文件。"}
    try:
        reader = PdfReader(str(pdf_path))
        count = len(reader.pages)
        return {"page_count": count, "pdf_path": str(pdf_path), "available": True, "error": None}
    except Exception as exc:  # pragma: no cover - parser failure depends on source file
        return {"page_count": 0, "pdf_path": str(pdf_path), "available": False, "error": str(exc)}


def clean_extracted_pdf_text(text):
    raw = str(text or "")
    if not raw.strip():
        return ""
    lines = [ln.rstrip() for ln in raw.splitlines()]
    cleaned = []
    for ln in lines:
        line = re.sub(r"\s+", " ", ln).strip()
        # drop isolated page-number lines like "23" or "p. 23"
        if re.fullmatch(r"(p\.\s*)?\d{1,3}", line, flags=re.I):
            continue
        cleaned.append(line)
    # remove repeated headers/footers appearing many times
    freq = {}
    for line in cleaned:
        if 6 <= len(line) <= 80:
            freq[line] = freq.get(line, 0) + 1
    noisy = {k for k, v in freq.items() if v >= 3}
    cleaned = [ln for ln in cleaned if ln not in noisy]
    merged = "\n".join(cleaned)
    merged = re.sub(r"\n{3,}", "\n\n", merged).strip()
    merged = clean_extracted_text(merged)
    # lightweight replacement for obvious garbled symbols
    merged = merged.replace("\ufffd", "")
    merged = re.sub(r"[■□]{2,}", "[可能乱码]", merged)
    return merged


def detect_text_garbled(text):
    content = str(text or "")
    if not content:
        return {"garbled": False, "score": 0, "examples": [], "warnings": []}
    bad_patterns = [r"\ufffd", r"[■□]", r"�"]
    bad_hits = []
    for pat in bad_patterns:
        bad_hits.extend(re.findall(pat, content))
    weird_blocks = re.findall(r"[^A-Za-z0-9\u4e00-\u9fff\s\.,;:!?\-—()\[\]\"'/]{3,}", content)
    bad_count = len(bad_hits) + len(weird_blocks)
    length = max(1, len(content))
    ratio = bad_count / length
    score = min(100, int(ratio * 3000))
    warnings = []
    if any(sym in content for sym in ["■", "□", "�", "\ufffd"]):
        warnings.append("检测到异常字符（■/□/�），可能存在乱码。")
    if weird_blocks:
        warnings.append("检测到连续不可读符号片段。")
    if ratio > 0.02:
        warnings.append("乱码比例较高，建议人工检查后再入库。")
    return {
        "garbled": bool(warnings),
        "score": score,
        "examples": weird_blocks[:5],
        "warnings": warnings,
    }


def extract_text_by_page_range(document, start_page, end_page, page_offset=0):
    info = get_pdf_page_count(document)
    if not info.get("available"):
        return {
            "text": "",
            "char_count": 0,
            "actual_start_page": 0,
            "actual_end_page": 0,
            "warnings": [info.get("error") or "PDF 不可用。"],
        }

    total = _safe_int(info.get("page_count"), 0)
    s = _safe_int(start_page, 0)
    e = _safe_int(end_page, 0)
    offset = _safe_int(page_offset, 0)
    if s <= 0 or e <= 0 or s > e:
        return {
            "text": "",
            "char_count": 0,
            "actual_start_page": 0,
            "actual_end_page": 0,
            "warnings": ["页码范围无效。"],
        }

    actual_start = s + offset
    actual_end = e + offset
    warnings = []
    if actual_start < 1:
        warnings.append("起始 PDF 页码小于 1，已自动调整。")
        actual_start = 1
    if actual_end > total:
        warnings.append("结束 PDF 页码超过总页数，已自动截断到最后一页。")
        actual_end = total
    if actual_start > actual_end:
        return {
            "text": "",
            "char_count": 0,
            "actual_start_page": actual_start,
            "actual_end_page": actual_end,
            "warnings": warnings + ["调整后页码范围为空。"],
        }

    try:
        reader = PdfReader(str(info["pdf_path"]))
    except Exception as exc:  # pragma: no cover
        return {
            "text": "",
            "char_count": 0,
            "actual_start_page": actual_start,
            "actual_end_page": actual_end,
            "warnings": warnings + [f"PDF 读取失败：{exc}"],
        }

    extracted_chunks = []
    for page_no in range(actual_start, actual_end + 1):
        idx = page_no - 1
        page_text = ""
        try:
            page_text = (reader.pages[idx].extract_text() or "").strip()
        except Exception:
            page_text = ""
        if not page_text:
            warnings.append(f"PDF 第 {page_no} 页无可提取文本，可能是扫描页或解析失败。")
            continue
        extracted_chunks.append(page_text)

    merged = "\n\n".join(extracted_chunks)
    cleaned = clean_extracted_pdf_text(merged)
    return {
        "text": cleaned,
        "char_count": len(cleaned),
        "actual_start_page": actual_start,
        "actual_end_page": actual_end,
        "warnings": warnings,
    }


def build_page_range_drafts(source_document, ranges):
    doc = source_document or {}
    drafts = []
    for row in ranges or []:
        unit = str(row.get("unit") or "").strip()
        theme = str(row.get("theme") or "").strip()
        text = str(row.get("text") or "")
        start_page = _safe_int(row.get("start_page"), 0)
        end_page = _safe_int(row.get("end_page"), 0)
        actual_start = _safe_int(row.get("actual_start_page"), 0)
        actual_end = _safe_int(row.get("actual_end_page"), 0)
        base_title = "_".join(
            [
                str(doc.get("textbook") or "").strip(),
                str(doc.get("grade") or "").strip(),
                str(doc.get("volume") or "").strip(),
                unit.replace(" ", ""),
                theme,
                "教材内容",
            ]
        ).strip("_")
        garbled = detect_text_garbled(text)
        warnings = list(row.get("warnings") or [])
        warnings.extend(garbled.get("warnings") or [])
        quality = "good"
        if len(text) < 300:
            quality = "low_quality"
            warnings.append("文本过短，不建议直接入库。")
        elif len(text) < 800 or garbled.get("garbled"):
            quality = "warning"
        if garbled.get("score", 0) >= 35:
            quality = "low_quality"
        page_note = f"来源页码：教材页 {start_page}-{end_page}，PDF 页 {actual_start}-{actual_end}"
        warnings.append(page_note)
        draft = {
            "source_document_id": doc.get("id"),
            "unit": unit,
            "theme": theme,
            "draft_type": "page_range_unit_textbook",
            "suggested_title": base_title or f"{unit}_教材内容",
            "suggested_doc_type": "教材",
            "suggested_grade": str(doc.get("grade") or "").strip(),
            "suggested_textbook": str(doc.get("textbook") or "").strip(),
            "suggested_volume": str(doc.get("volume") or "").strip(),
            "suggested_unit": unit or "通用",
            "suggested_lesson_type": "Other",
            "suggested_tags": ",".join([theme, unit, "page_range_split"]).strip(","),
            "draft_text": text,
            "char_count": len(text),
            "confidence": 0.9,
            "quality_status": quality,
            "quality_warnings": ";".join([w for w in warnings if w]),
            "estimated_vocab_items": 0,
            "status": "pending",
        }
        drafts.append(draft)
    return drafts


def summarize_page_range_quality(draft):
    text = str((draft or {}).get("draft_text") or "")
    garbled = detect_text_garbled(text)
    return {
        "word_count": count_text_words(text),
        "garbled": garbled,
    }
