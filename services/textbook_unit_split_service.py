"""Semi-automatic unit text split for textbook documents."""

from __future__ import annotations

import re
import hashlib

from services.textbook_catalog_service import CATALOG


def _clean(v):
    return str(v or "").strip()


def _first_marker_index(text, start, markers):
    lowered = text.lower()
    idx = -1
    for m in markers:
        p = lowered.find(m.lower(), start)
        if p >= 0 and (idx < 0 or p < idx):
            idx = p
    return idx


def _estimate_vocab_items(text):
    content = str(text or "")
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    count = 0
    for line in lines:
        lower = line.lower()
        if len(line) > 120:
            continue
        # common POS/word-list style features
        if re.search(r"\b(n|v|adj|adv|prep|pron|conj)\.\s*", lower):
            count += 1
            continue
        if re.search(r"/[^/\n]{1,25}/", line):
            count += 1
            continue
        if re.search(r"[A-Za-z][A-Za-z\- ]{1,30}\s+[;；]\s*[\u4e00-\u9fff]", line):
            count += 1
            continue
        if re.search(r"^[A-Za-z][A-Za-z\- ]{1,24}\s+[\u4e00-\u9fff]{1,16}", line):
            count += 1
            continue
        # short word/phrase lines in lists
        if re.search(r"^[A-Za-z][A-Za-z\- ]{1,24}$", line):
            count += 1
            continue
    return count


def _estimate_reading_features(text):
    content = str(text or "")
    sentences = re.split(r"[.!?。！？]\s*", content)
    valid_sentences = [s.strip() for s in sentences if len(s.strip()) > 20]
    paragraph_lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    long_lines = sum(1 for ln in paragraph_lines if len(ln) > 40)
    reading_markers = [
        "read the passage",
        "read the text",
        "answer the questions",
        "paragraph",
        "story",
        "article",
    ]
    marker_hits = sum(1 for m in reading_markers if m in content.lower())
    return {
        "long_sentence_count": len(valid_sentences),
        "long_line_count": long_lines,
        "marker_hits": marker_hits,
    }


def classify_draft_type(text, initial_type, unit="", theme=""):
    content = str(text or "")
    lowered = content.lower()
    initial = _clean(initial_type)
    vocab_items = _estimate_vocab_items(content)
    reading_features = _estimate_reading_features(content)
    has_pos_density = len(re.findall(r"\b(n|v|adj|adv|prep|pron|conj)\.\s*", lowered)) >= 4
    reading_like = (
        reading_features["long_sentence_count"] >= 4
        or reading_features["long_line_count"] >= 4
        or reading_features["marker_hits"] >= 1
    )
    if initial == "vocabulary":
        if vocab_items < 10 and len(content) >= 350 and reading_like and not has_pos_density:
            return {
                "draft_type": "reading_text",
                "suggested_lesson_type": "Reading",
                "warnings": ["疑似课文内容被识别为词汇表，请人工确认。"],
                "force_warning": True,
            }
        return {"draft_type": initial, "suggested_lesson_type": "Vocabulary", "warnings": [], "force_warning": False}
    if initial == "reading_text":
        if vocab_items >= 12 and not reading_like and has_pos_density:
            return {
                "draft_type": "vocabulary",
                "suggested_lesson_type": "Vocabulary",
                "warnings": ["疑似词汇表内容被识别为课文，请人工确认。"],
                "force_warning": True,
            }
        return {"draft_type": initial, "suggested_lesson_type": "Reading", "warnings": [], "force_warning": False}
    return {"draft_type": initial, "suggested_lesson_type": "", "warnings": [], "force_warning": False}


def detect_unit_boundaries(text, textbook="人教版", volume=None):
    content = str(text or "")
    if not content.strip():
        return []
    unit_map = CATALOG.get(_clean(textbook), {}).get(_clean(volume), {}) or {}
    pattern = re.compile(r"(?:^|\n)\s*(UNIT|Unit)\s*([0-9]{1,2})\s+([A-Za-z][^\n]{0,80})", re.M)
    matches = list(pattern.finditer(content))
    candidates = []
    for m in matches:
        unit = f"Unit {int(m.group(2))}"
        if unit_map and unit not in unit_map:
            continue
        theme = _clean(m.group(3))
        catalog_theme = _clean((unit_map.get(unit) or {}).get("theme"))
        confidence = 0.62
        if catalog_theme and catalog_theme.lower() in theme.lower():
            confidence = 0.9
            theme = catalog_theme
        elif catalog_theme:
            confidence = 0.75
            theme = catalog_theme
        start = m.start()
        window = content[max(0, start - 240): min(len(content), start + 360)].lower()
        if re.search(r"\bp\.\s*\d+\b", window) or re.search(r"\bcontents?\b", window):
            confidence -= 0.2
        if any(k in window for k in ["workbook", "appendix", "appendices", "grammar notes"]):
            confidence -= 0.35
        if re.search(r"listening and speaking|listening and talking|reading for writing", window):
            confidence -= 0.12
        candidates.append(
            {
                "unit": unit,
                "theme": theme,
                "start_index": start,
                "confidence": max(0.1, min(0.99, confidence)),
            }
        )

    # Deduplicate same unit and keep the most likely main boundary.
    by_unit = {}
    for c in candidates:
        u = c["unit"]
        old = by_unit.get(u)
        if old is None:
            by_unit[u] = c
            continue
        # prefer higher confidence, then later position (正文 usually after目录)
        if c["confidence"] > old["confidence"] + 0.01 or (
            abs(c["confidence"] - old["confidence"]) <= 0.01 and c["start_index"] > old["start_index"]
        ):
            by_unit[u] = c

    selected = sorted(by_unit.values(), key=lambda x: x["start_index"])
    catalog_unit_count = len(unit_map) if unit_map else 0
    if catalog_unit_count and len(candidates) > catalog_unit_count * 2:
        # strict mode: keep only catalog units with best boundary.
        strict = []
        for unit in sorted(unit_map.keys(), key=lambda x: int(re.search(r"\d+", x).group(0))):
            if unit in by_unit:
                strict.append(by_unit[unit])
        selected = sorted(strict, key=lambda x: x["start_index"])

    boundaries = []
    for idx, row in enumerate(selected):
        end = selected[idx + 1]["start_index"] if idx + 1 < len(selected) else len(content)
        boundaries.append(
            {
                "unit": row["unit"],
                "theme": row["theme"],
                "start_index": row["start_index"],
                "end_index": end,
                "confidence": row["confidence"],
            }
        )
    return boundaries


def split_text_by_units(text, catalog_units):
    content = str(text or "")
    chunks = []
    for row in catalog_units or []:
        seg = content[int(row["start_index"]): int(row["end_index"])].strip()
        chunks.append(
            {
                "unit": row.get("unit"),
                "theme": row.get("theme"),
                "text": seg,
                "char_count": len(seg),
                "confidence": row.get("confidence", 0),
            }
        )
    return chunks


def extract_unit_sections(unit_text, textbook="人教版", volume="", unit=""):
    text = str(unit_text or "")
    catalog_meta = CATALOG.get(_clean(textbook), {}).get(_clean(volume), {}).get(_clean(unit), {}) or {}
    reading_title = _clean(catalog_meta.get("reading_title"))
    markers = {
        "reading_and_thinking": [
            "Reading and Thinking",
            "Read the text",
            "Read the passage",
            "Stronger Together",
            "A Day in the Clouds",
            "From Problems to Solutions",
            "Start an online community",
        ],
        "reading_for_writing": ["Reading for Writing"],
        "grammar": ["Discovering Useful Structures", "Grammar"],
        "vocabulary": ["Words and Expressions", "New Words and Expressions", "Word List", "Vocabulary"],
    }
    result = {"full_unit_text": text}
    for key, names in markers.items():
        result[key] = ""
        pos = -1
        name_hit = ""
        for name in names:
            p = text.lower().find(name.lower())
            if p >= 0 and (pos < 0 or p < pos):
                pos = p
                name_hit = name
        if key == "reading_and_thinking" and pos < 0 and reading_title:
            tpos = text.lower().find(reading_title.lower())
            if tpos >= 0:
                pos = tpos
                name_hit = reading_title

        if pos >= 0:
            tail = text[pos:]
            next_mark = len(tail)
            for other_names in markers.values():
                for n in other_names:
                    if n.lower() == name_hit.lower():
                        continue
                    p2 = tail.lower().find(n.lower())
                    if p2 > 0:
                        next_mark = min(next_mark, p2)
            section_text = tail[:next_mark].strip()
            if key == "reading_and_thinking":
                abs_start = pos
                reading_end_markers = [
                    "discovering useful structures",
                    "listening and talking",
                    "reading for writing",
                    "assessing your progress",
                    "video time",
                    "words and expressions",
                    "workbook",
                    "appendices",
                    "appendix",
                ]
                unit_pattern = re.compile(r"(?:^|\n)\s*unit\s*[0-9]{1,2}\b", re.I)
                unit_match = unit_pattern.search(text, abs_start + 1)
                cut_points = []
                if unit_match:
                    cut_points.append(unit_match.start())
                marker_idx = _first_marker_index(text, abs_start + 1, reading_end_markers)
                if marker_idx >= 0:
                    cut_points.append(marker_idx)
                if cut_points:
                    section_text = text[abs_start:min(cut_points)].strip()
            if key == "vocabulary":
                abs_start = pos
                vocab_end_markers = [
                    "workbook",
                    "appendix",
                    "appendices",
                    "grammar notes",
                    "notes",
                    "reading and thinking",
                    "reading for writing",
                    "discovering useful structures",
                    "listening and speaking",
                    "listening and talking",
                    "assessing your progress",
                    "video time",
                ]
                unit_pattern = re.compile(r"(?:^|\n)\s*unit\s*[0-9]{1,2}\b", re.I)
                unit_match = unit_pattern.search(text, abs_start + 1)
                cut_points = []
                if unit_match:
                    cut_points.append(unit_match.start())
                marker_idx = _first_marker_index(text, abs_start + 1, vocab_end_markers)
                if marker_idx >= 0:
                    cut_points.append(marker_idx)
                if cut_points:
                    section_text = text[abs_start:min(cut_points)].strip()
            result[key] = section_text
    return result


def _quality_for_draft(draft):
    text = str(draft.get("draft_text") or "")
    char_count = int(draft.get("char_count") or len(text))
    draft_type = _clean(draft.get("draft_type"))
    warnings = []
    quality = "good"
    low_markers = ["contents", "workbook", "appendix", "p. ", "......"]
    lowered = text.lower()
    if any(m in lowered for m in low_markers):
        warnings.append("疑似目录片段")
        quality = "warning"
    if "workbook" in lowered:
        warnings.append("疑似Workbook片段")
        quality = "warning"
    if "appendix" in lowered:
        warnings.append("疑似附录片段")
        quality = "warning"

    if draft_type == "unit_textbook":
        if char_count < 300:
            return "low_quality", "文本过短;无正文内容"
        if char_count < 800:
            warnings.append("文本过短")
            quality = "low_quality"
    elif draft_type == "reading_text":
        if char_count < 300:
            return "low_quality", "文本过短"
        if 300 <= char_count < 500:
            warnings.append("课文文本偏短")
            quality = "warning"
        if "reading and thinking" not in lowered and "how we have been changed" not in lowered:
            warnings.append("疑似非阅读正文")
            quality = "warning"
        if any(k in lowered for k in ["workbook", "appendix", "appendices", "grammar notes"]):
            warnings.append("疑似混入Workbook/附录")
            quality = "warning"
    elif draft_type == "vocabulary":
        estimated_items = int(draft.get("estimated_vocab_items") or _estimate_vocab_items(text))
        draft["estimated_vocab_items"] = estimated_items
        contamination_markers = [
            "workbook",
            "appendices",
            "appendix",
            "grammar notes",
            "read the passage",
            "listen to",
            "answer the questions",
            "complete the sentences",
        ]
        has_contamination = any(m in lowered for m in contamination_markers) or bool(
            re.search(r"\bp\.\s*\d+\b", lowered)
        ) or bool(re.search(r"unit\s*\d+\s*p\.", lowered))
        if has_contamination:
            warnings.append("疑似混入Workbook/附录/练习内容")
            quality = "warning"
        unit_hits = set(re.findall(r"\bunit\s*([0-9]{1,2})\b", lowered))
        if len(unit_hits) >= 2:
            warnings.append("疑似跨单元")
            quality = "warning"
        if char_count < 100:
            warnings.append("文本过短")
            warning_text = ";".join(["词条估算:" + str(estimated_items)] + warnings)
            return "low_quality", warning_text
        if char_count < 200:
            warnings.append("文本较短")
            quality = "warning" if quality != "low_quality" else quality
        if estimated_items < 5:
            warnings.append("词汇条目不足")
            warning_text = ";".join(["词条估算:" + str(estimated_items)] + warnings)
            return "low_quality", warning_text
        if 5 <= estimated_items <= 10:
            warnings.append("词汇条目偏少")
            quality = "warning" if quality != "low_quality" else quality
        if "sports and fitnessunit" in lowered:
            warnings.append("疑似PDF粘连短文本")
            quality = "low_quality"
        if "words and expressions" in lowered and len(unit_hits) >= 2:
            warnings.append("疑似整册词汇表，单元归属需人工确认")
            if quality == "good":
                quality = "warning"
        if has_contamination or len(unit_hits) >= 2:
            if quality == "good":
                quality = "warning"
    elif draft_type == "grammar":
        if char_count < 200:
            return "low_quality", "文本过短"
    elif draft_type == "writing":
        if char_count < 200:
            return "low_quality", "文本过短"

    if draft_type == "vocabulary":
        item_info = f"词条估算:{int(draft.get('estimated_vocab_items') or 0)}"
        warnings = [w for w in warnings if w]
        if item_info not in warnings:
            warnings.insert(0, item_info)
    return quality, ";".join(warnings)


def build_unit_document_drafts(source_document, unit_split):
    src = source_document or {}
    drafts = []
    for row in unit_split or []:
        unit = _clean(row.get("unit"))
        theme = _clean(row.get("theme"))
        unit_text = str(row.get("text") or "")
        sections = extract_unit_sections(
            unit_text,
            textbook=src.get("textbook"),
            volume=src.get("volume"),
            unit=unit,
        )
        base = {
            "source_document_id": src.get("id"),
            "unit": unit,
            "theme": theme,
            "suggested_grade": _clean(src.get("grade")),
            "suggested_textbook": _clean(src.get("textbook")),
            "suggested_volume": _clean(src.get("volume")),
            "suggested_unit": unit,
            "char_count": len(unit_text),
            "confidence": float(row.get("confidence") or 0),
            "status": "pending",
        }
        textbook_draft = {
            **base,
            "draft_type": "unit_textbook",
            "suggested_title": f"{base['suggested_textbook']}_{base['suggested_grade']}_{base['suggested_volume']}_{unit.replace(' ', '')}_{theme}_教材内容".strip("_"),
            "suggested_doc_type": "教材",
            "suggested_lesson_type": "Other",
            "suggested_tags": ",".join([theme, unit, base["suggested_textbook"]]).strip(","),
            "draft_text": sections.get("full_unit_text") or unit_text,
            "text_hash": hashlib.sha1((sections.get("full_unit_text") or unit_text).encode("utf-8", errors="ignore")).hexdigest(),
        }
        textbook_draft["quality_status"], textbook_draft["quality_warnings"] = _quality_for_draft(textbook_draft)
        drafts.append(textbook_draft)
        if sections.get("reading_and_thinking"):
            reading_draft = {
                **base,
                "draft_type": "reading_text",
                "suggested_title": f"{base['suggested_textbook']}_{base['suggested_grade']}_{base['suggested_volume']}_{unit.replace(' ', '')}_{theme}_Reading课文".strip("_"),
                "suggested_doc_type": "课文",
                "suggested_lesson_type": "Reading",
                "suggested_tags": ",".join([theme, unit, "Reading and Thinking"]).strip(","),
                "draft_text": sections["reading_and_thinking"],
                "char_count": len(sections["reading_and_thinking"]),
                "text_hash": hashlib.sha1(sections["reading_and_thinking"].encode("utf-8", errors="ignore")).hexdigest(),
            }
            reading_cls = classify_draft_type(
                reading_draft.get("draft_text"),
                "reading_text",
                unit=unit,
                theme=theme,
            )
            reading_draft["draft_type"] = reading_cls["draft_type"]
            if reading_cls["suggested_lesson_type"]:
                reading_draft["suggested_lesson_type"] = reading_cls["suggested_lesson_type"]
            reading_draft["quality_status"], reading_draft["quality_warnings"] = _quality_for_draft(reading_draft)
            if reading_cls["warnings"]:
                old = reading_draft.get("quality_warnings") or ""
                reading_draft["quality_warnings"] = ";".join([w for w in [old] + reading_cls["warnings"] if w])
            if reading_cls.get("force_warning") and reading_draft.get("quality_status") == "good":
                reading_draft["quality_status"] = "warning"
            drafts.append(reading_draft)
        if sections.get("vocabulary"):
            vocab_draft = {
                **base,
                "draft_type": "vocabulary",
                "suggested_title": f"{base['suggested_textbook']}_{base['suggested_grade']}_{base['suggested_volume']}_{unit.replace(' ', '')}_{theme}_词汇表".strip("_"),
                "suggested_doc_type": "词汇表",
                "suggested_lesson_type": "Vocabulary",
                "suggested_tags": ",".join([theme, unit, "Words and Expressions"]).strip(","),
                "draft_text": sections["vocabulary"],
                "char_count": len(sections["vocabulary"]),
                "text_hash": hashlib.sha1(sections["vocabulary"].encode("utf-8", errors="ignore")).hexdigest(),
                "estimated_vocab_items": _estimate_vocab_items(sections["vocabulary"]),
            }
            vocab_cls = classify_draft_type(
                vocab_draft.get("draft_text"),
                "vocabulary",
                unit=unit,
                theme=theme,
            )
            vocab_draft["draft_type"] = vocab_cls["draft_type"]
            if vocab_cls["suggested_lesson_type"]:
                vocab_draft["suggested_lesson_type"] = vocab_cls["suggested_lesson_type"]
            vocab_draft["quality_status"], vocab_draft["quality_warnings"] = _quality_for_draft(vocab_draft)
            if vocab_cls["warnings"]:
                old = vocab_draft.get("quality_warnings") or ""
                vocab_draft["quality_warnings"] = ";".join([w for w in [old] + vocab_cls["warnings"] if w])
            if vocab_cls.get("force_warning") and vocab_draft.get("quality_status") == "good":
                vocab_draft["quality_status"] = "warning"
            drafts.append(vocab_draft)

    # de-dup same unit+type+lesson_type+hash
    dedup = {}
    for d in drafts:
        key = (
            _clean(d.get("suggested_volume")),
            _clean(d.get("suggested_unit")),
            _clean(d.get("draft_type")),
            _clean(d.get("suggested_lesson_type")),
            _clean(d.get("text_hash")),
        )
        if key not in dedup:
            dedup[key] = d
    return list(dedup.values())
