import json
import uuid
from pathlib import Path

from flask import Blueprint, abort, flash, redirect, render_template, request, send_file, url_for
from werkzeug.utils import secure_filename

from config import KNOWLEDGE_TEXT_DIR, KNOWLEDGE_UPLOAD_DIR
from models.database import (
    create_knowledge_document,
    delete_knowledge_document,
    delete_knowledge_chunks_by_document,
    get_knowledge_document,
    now,
    list_knowledge_chunks_by_document,
    query_knowledge_documents,
    update_knowledge_document,
)
from services.document_parse_service import (
    DocumentParseError,
    SUPPORTED_MANUSCRIPT_EXTENSIONS,
    clean_extracted_text,
    count_text_words,
    extract_text_from_file,
    generate_basic_summary,
    save_parsed_text,
)
from services.embedding_service import EmbeddingServiceError, test_embedding_connection
from services.knowledge_index_service import (
    delete_knowledge_document_index,
    index_knowledge_document,
    search_knowledge_semantic,
)
from services.knowledge_governance_service import (
    create_unit_placeholders,
    documents_need_reindex,
    get_knowledge_coverage,
    suggest_metadata,
    update_document_metadata_quality,
)
from services.vector_store_service import VectorStoreError


knowledge_bp = Blueprint("knowledge", __name__)

DOC_TYPE_OPTIONS = [
    "教材",
    "课文",
    "教案",
    "讲稿",
    "说课稿",
    "试卷",
    "词汇表",
    "课堂表达",
    "PPT文案",
    "阅读材料",
    "写作范文",
    "其他",
]
GRADE_OPTIONS = ["高一", "高二", "高三", "通用"]
TEXTBOOK_OPTIONS = ["人教版", "外研版", "北师大版", "译林版", "通用"]
VOLUME_OPTIONS = ["必修一", "必修二", "必修三", "选择性必修一", "选择性必修二", "选择性必修三", "通用"]
UNIT_OPTIONS = ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "Unit 5", "通用"]
LESSON_TYPE_OPTIONS = ["Reading", "Grammar", "Writing", "Listening and Speaking", "Revision", "Vocabulary", "Other"]
STATUS_OPTIONS = ["pending", "parsed", "failed"]
SUPPLEMENT_TYPE_OPTIONS = [
    ("textbook_content", "教材内容"),
    ("reading_text", "Reading 课文"),
    ("reading_plan", "Reading 教案"),
    ("vocabulary", "词汇表"),
    ("writing", "Writing 资料"),
    ("grammar", "Grammar 资料"),
    ("classroom_expressions", "课堂表达"),
]


def _blank_form():
    return {
        "title": "",
        "doc_type": "教案",
        "grade": "高一",
        "textbook": "人教版",
        "volume": "必修一",
        "unit": "通用",
        "lesson_type": "Reading",
        "tags": "",
        "raw_text": "",
    }


def _supplement_recommendation(supplement_type, textbook="", volume="", unit="", theme=""):
    label_map = dict(SUPPLEMENT_TYPE_OPTIONS)
    kind = (supplement_type or "").strip()
    if kind not in label_map:
        kind = "reading_text"

    rec = {
        "supplement_type": kind,
        "recommended_label": label_map.get(kind, "补充资料"),
        "doc_type": "其他",
        "lesson_type": "Other",
        "title_suffix": label_map.get(kind, "补充资料"),
        "tags": "",
    }
    if kind == "textbook_content":
        rec.update({"doc_type": "教材", "lesson_type": "Other", "title_suffix": "教材内容", "tags": "教材,单元资料"})
    elif kind == "reading_text":
        rec.update({"doc_type": "课文", "lesson_type": "Reading", "title_suffix": "Reading 课文", "tags": "Reading,Reading and Thinking"})
    elif kind == "reading_plan":
        rec.update({"doc_type": "教案", "lesson_type": "Reading", "title_suffix": "Reading 教案", "tags": "教案,Reading"})
    elif kind == "vocabulary":
        rec.update({"doc_type": "词汇表", "lesson_type": "Vocabulary", "title_suffix": "词汇表", "tags": "词汇表,Vocabulary"})
    elif kind == "writing":
        rec.update({"doc_type": "写作范文", "lesson_type": "Writing", "title_suffix": "Writing 资料", "tags": "Writing,写作"})
    elif kind == "grammar":
        rec.update({"doc_type": "其他", "lesson_type": "Grammar", "title_suffix": "Grammar 资料", "tags": "Grammar,语法"})
    elif kind == "classroom_expressions":
        rec.update({"doc_type": "课堂表达", "lesson_type": "Other", "title_suffix": "课堂表达", "tags": "课堂表达,口语"})

    prefix = "_".join([part for part in [textbook, volume, unit, theme] if part])
    rec["title"] = f"{prefix}_{rec['title_suffix']}" if prefix else rec["title_suffix"]
    return rec


def _safe_remove(path_value):
    if not path_value:
        return
    path = Path(path_value)
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except OSError:
        # Non-fatal by design.
        return


def _load_full_text(doc):
    text_file_path = str(doc.get("text_file_path") or "").strip()
    if text_file_path:
        path = Path(text_file_path)
        if path.exists() and path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                if content.strip():
                    return content
            except OSError:
                pass
    return str(doc.get("parsed_text") or "")


def _optional_int(value, default=5, minimum=1, maximum=20):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    number = max(minimum, number)
    if maximum is not None:
        number = min(maximum, number)
    return number


def _semantic_filters_from_request(req):
    return {
        "doc_type": str(req.args.get("doc_type") or "").strip(),
        "grade": str(req.args.get("grade") or "").strip(),
        "textbook": str(req.args.get("textbook") or "").strip(),
        "volume": str(req.args.get("volume") or "").strip(),
        "unit": str(req.args.get("unit") or "").strip(),
        "lesson_type": str(req.args.get("lesson_type") or "").strip(),
    }


def _build_doc_payload(form_data, source_type, parsed_text, text_file_path, file_name="", original_file_path="", status="parsed", error_message=""):
    title = str(form_data.get("title") or "").strip()
    doc_type = str(form_data.get("doc_type") or "").strip() or "其他"
    summary = generate_basic_summary(parsed_text, title=title, doc_type=doc_type)
    return {
        "title": title,
        "doc_type": doc_type,
        "grade": str(form_data.get("grade") or "").strip(),
        "textbook": str(form_data.get("textbook") or "").strip(),
        "volume": str(form_data.get("volume") or "").strip(),
        "unit": str(form_data.get("unit") or "").strip(),
        "lesson_type": str(form_data.get("lesson_type") or "").strip(),
        "source_type": source_type,
        "file_name": file_name,
        "original_file_path": original_file_path,
        "text_file_path": text_file_path,
        "parsed_text": parsed_text[:10000],
        "summary": summary,
        "word_count": count_text_words(parsed_text),
        "tags": str(form_data.get("tags") or "").strip(),
        "status": status,
        "error_message": error_message,
        "embedding_status": "not_indexed",
        "chunk_count": 0,
        "vector_collection": "",
        "embedding_error": "",
        "indexed_at": "",
    }


@knowledge_bp.route("/knowledge")
def knowledge_list():
    filters = {
        "keyword": str(request.args.get("keyword") or "").strip(),
        "doc_type": str(request.args.get("doc_type") or "").strip(),
        "grade": str(request.args.get("grade") or "").strip(),
        "textbook": str(request.args.get("textbook") or "").strip(),
        "volume": str(request.args.get("volume") or "").strip(),
        "unit": str(request.args.get("unit") or "").strip(),
        "lesson_type": str(request.args.get("lesson_type") or "").strip(),
        "status": str(request.args.get("status") or "").strip(),
        "placeholder_filter": str(request.args.get("placeholder_filter") or "").strip(),
    }
    docs = query_knowledge_documents(filters, limit=50)
    need_reindex_ids = {d["id"] for d in documents_need_reindex()}
    enriched_docs = []
    for doc in docs:
        if int(doc.get("metadata_quality_score") or 0) == 0:
            updated = update_document_metadata_quality(doc)
            if updated:
                doc.update(updated)
        doc["need_reindex"] = doc["id"] in need_reindex_ids
        title = str(doc.get("title") or "")
        tags = str(doc.get("tags") or "")
        is_placeholder = (
            str(doc.get("doc_type") or "") == "其他"
            and ("资料占位" in title or "资料占位" in tags)
        )
        doc["is_placeholder"] = is_placeholder
        if is_placeholder and int(doc.get("word_count") or 0) == 0:
            doc["placeholder_note"] = "等待补充资料"
        else:
            doc["placeholder_note"] = ""
        enriched_docs.append(doc)

    placeholder_filter = filters.get("placeholder_filter")
    if placeholder_filter == "hide":
        enriched_docs = [d for d in enriched_docs if not d.get("is_placeholder")]
    elif placeholder_filter == "only":
        enriched_docs = [d for d in enriched_docs if d.get("is_placeholder")]

    return render_template(
        "knowledge_list.html",
        docs=enriched_docs,
        filters=filters,
        doc_type_options=DOC_TYPE_OPTIONS,
        grade_options=GRADE_OPTIONS,
        textbook_options=TEXTBOOK_OPTIONS,
        volume_options=VOLUME_OPTIONS,
        unit_options=UNIT_OPTIONS,
        lesson_type_options=LESSON_TYPE_OPTIONS,
        status_options=STATUS_OPTIONS,
    )


@knowledge_bp.route("/knowledge/new", methods=["GET", "POST"])
def knowledge_new():
    form_data = _blank_form()
    supplement_type = str(request.args.get("supplement_type") or request.form.get("supplement_type") or "reading_text").strip()
    action_after = str(request.args.get("action_after") or request.form.get("action_after") or "detail").strip()
    coverage_return = {
        "textbook": str(request.args.get("textbook") or request.form.get("coverage_textbook") or "").strip(),
        "volume": str(request.args.get("volume") or request.form.get("coverage_volume") or "").strip(),
        "unit": str(request.args.get("unit") or request.form.get("coverage_unit") or "").strip(),
    }
    query_theme = str(request.args.get("theme") or "").strip()

    def _render_new():
        rec = _supplement_recommendation(
            supplement_type,
            textbook=form_data.get("textbook") or coverage_return.get("textbook", ""),
            volume=form_data.get("volume") or coverage_return.get("volume", ""),
            unit=form_data.get("unit") or coverage_return.get("unit", ""),
            theme=query_theme,
        )
        return render_template(
            "knowledge_new.html",
            form_data=form_data,
            doc_type_options=DOC_TYPE_OPTIONS,
            grade_options=GRADE_OPTIONS,
            textbook_options=TEXTBOOK_OPTIONS,
            volume_options=VOLUME_OPTIONS,
            unit_options=UNIT_OPTIONS,
            lesson_type_options=LESSON_TYPE_OPTIONS,
            supplement_type_options=SUPPLEMENT_TYPE_OPTIONS,
            selected_supplement_type=supplement_type,
            action_after=action_after,
            coverage_return=coverage_return,
            recommended_label=rec["recommended_label"],
        )

    if request.method == "GET":
        for key in ("grade", "textbook", "volume", "unit"):
            value = str(request.args.get(key) or "").strip()
            if value:
                form_data[key] = value
        rec = _supplement_recommendation(
            supplement_type,
            textbook=form_data["textbook"],
            volume=form_data["volume"],
            unit=form_data["unit"],
            theme=query_theme,
        )
        form_data["doc_type"] = str(request.args.get("doc_type") or rec["doc_type"]).strip()
        form_data["lesson_type"] = str(request.args.get("lesson_type") or rec["lesson_type"]).strip()
        form_data["tags"] = str(request.args.get("tags") or rec["tags"]).strip()
        form_data["title"] = str(request.args.get("title") or rec["title"]).strip()
        if not coverage_return["textbook"]:
            coverage_return["textbook"] = form_data["textbook"]
        if not coverage_return["volume"]:
            coverage_return["volume"] = form_data["volume"]
        if not coverage_return["unit"]:
            coverage_return["unit"] = form_data["unit"]
        return _render_new()

    form_data.update({key: str(request.form.get(key) or "").strip() for key in form_data.keys()})
    upload = request.files.get("file")
    raw_text = str(request.form.get("raw_text") or "").strip()
    has_error = False

    if not form_data["title"]:
        flash("请填写资料标题。", "danger")
        has_error = True
    if not raw_text and (upload is None or not upload.filename):
        flash("请填写资料文本或上传资料文件。", "danger")
        has_error = True
    if has_error:
        return _render_new()

    source_type = "text"
    file_name = ""
    original_file_path = ""
    file_text = ""

    if upload and upload.filename:
        safe_name = secure_filename(upload.filename)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED_MANUSCRIPT_EXTENSIONS:
            flash("不支持的文件格式，仅支持 txt / md / docx / pdf。", "danger")
            return _render_new()

        unique_name = f"{now().replace(' ', '_').replace(':', '')}_{uuid.uuid4().hex[:8]}_{safe_name}"
        target_path = KNOWLEDGE_UPLOAD_DIR / unique_name
        upload.save(target_path)
        file_name = upload.filename
        original_file_path = str(target_path)
        source_type = "file"
        try:
            file_text = extract_text_from_file(target_path, upload.filename)
        except DocumentParseError as exc:
            payload = _build_doc_payload(
                form_data=form_data,
                source_type=source_type,
                parsed_text="",
                text_file_path="",
                file_name=file_name,
                original_file_path=original_file_path,
                status="failed",
                error_message=str(exc),
            )
            doc = create_knowledge_document(payload)
            flash("资料上传成功，但解析失败，请在详情页重试解析。", "warning")
            return redirect(url_for("knowledge.knowledge_detail", doc_id=doc["id"]))

    if file_text and raw_text:
        source_type = "mixed"
    elif file_text:
        source_type = "file"
    else:
        source_type = "text"

    merged_text = clean_extracted_text("\n\n".join(part for part in [file_text, raw_text] if part.strip()))
    if not merged_text:
        flash("解析后的资料内容为空，请检查文件或输入文本。", "danger")
        return _render_new()

    base_name = f"{secure_filename(form_data['title']) or 'knowledge'}_{uuid.uuid4().hex[:8]}"
    text_file_path = save_parsed_text(merged_text, KNOWLEDGE_TEXT_DIR, base_name)
    payload = _build_doc_payload(
        form_data=form_data,
        source_type=source_type,
        parsed_text=merged_text,
        text_file_path=text_file_path,
        file_name=file_name,
        original_file_path=original_file_path,
        status="parsed",
    )
    doc = create_knowledge_document(payload)
    update_document_metadata_quality(doc)
    if action_after in {"index_detail", "index_coverage"}:
        index_result = index_knowledge_document(doc["id"])
        if index_result.get("ok"):
            flash("知识资料已保存并解析完成，且已建立向量索引。", "success")
        else:
            flash(f"知识资料已保存，但建立索引失败：{index_result.get('message','未知错误')}", "warning")
    else:
        flash("知识资料已保存并解析完成。", "success")

    if action_after in {"coverage", "index_coverage"}:
        return redirect(url_for("knowledge.knowledge_coverage", volume=coverage_return.get("volume") or ""))
    return redirect(url_for("knowledge.knowledge_detail", doc_id=doc["id"]))


@knowledge_bp.route("/knowledge/<int:doc_id>")
def knowledge_detail(doc_id):
    doc = get_knowledge_document(doc_id)
    if not doc:
        abort(404)
    full_text = _load_full_text(doc)
    preview_text = full_text[:5000]
    is_truncated = len(full_text) > 5000
    chunks = list_knowledge_chunks_by_document(doc_id)
    updated = update_document_metadata_quality(doc)
    if updated:
        doc = updated
    metadata_suggestions = suggest_metadata(doc)
    need_reindex = any(d["id"] == doc_id for d in documents_need_reindex())
    return render_template(
        "knowledge_detail.html",
        doc=doc,
        preview_text=preview_text,
        is_truncated=is_truncated,
        chunks=chunks,
        metadata_suggestions=metadata_suggestions,
        need_reindex=need_reindex,
    )


@knowledge_bp.route("/knowledge/<int:doc_id>/index", methods=["POST"])
def knowledge_index(doc_id):
    result = index_knowledge_document(doc_id)
    if result.get("ok"):
        flash(result.get("message") or "已建立向量索引。", "success")
    else:
        flash(result.get("message") or "建立向量索引失败。", "danger")
    return redirect(url_for("knowledge.knowledge_detail", doc_id=doc_id))


@knowledge_bp.route("/knowledge/<int:doc_id>/reindex", methods=["POST"])
def knowledge_reindex(doc_id):
    result = index_knowledge_document(doc_id)
    if result.get("ok"):
        flash(result.get("message") or "已重新建立向量索引。", "success")
    else:
        flash(result.get("message") or "重新建立向量索引失败。", "danger")
    return redirect(url_for("knowledge.knowledge_detail", doc_id=doc_id))


@knowledge_bp.route("/knowledge/<int:doc_id>/delete-index", methods=["POST"])
def knowledge_delete_index(doc_id):
    result = delete_knowledge_document_index(doc_id)
    if result.get("warning"):
        flash(result["warning"], "warning")
    if result.get("ok"):
        flash(result.get("message") or "已删除向量索引。", "success")
    else:
        flash(result.get("message") or "删除向量索引失败。", "danger")
    return redirect(url_for("knowledge.knowledge_detail", doc_id=doc_id))


@knowledge_bp.route("/knowledge/<int:doc_id>/delete", methods=["POST"])
def knowledge_delete(doc_id):
    doc = get_knowledge_document(doc_id)
    if not doc:
        abort(404)
    result = delete_knowledge_document_index(doc_id)
    if result.get("warning"):
        flash(result["warning"], "warning")
    _safe_remove(doc.get("original_file_path"))
    _safe_remove(doc.get("text_file_path"))
    delete_knowledge_chunks_by_document(doc_id)
    delete_knowledge_document(doc_id)
    flash("资料已删除。", "success")
    return redirect(url_for("knowledge.knowledge_list"))


@knowledge_bp.route("/knowledge/<int:doc_id>/reparse", methods=["POST"])
def knowledge_reparse(doc_id):
    doc = get_knowledge_document(doc_id)
    if not doc:
        abort(404)

    parsed_text = ""
    status = "parsed"
    error_message = ""
    source_path = str(doc.get("original_file_path") or "").strip()
    file_name = str(doc.get("file_name") or "").strip()

    try:
        if source_path and Path(source_path).exists():
            parsed_text = extract_text_from_file(source_path, file_name or Path(source_path).name)
        else:
            current_text = _load_full_text(doc)
            if current_text.strip():
                parsed_text = clean_extracted_text(current_text)
            else:
                raise DocumentParseError("该资料没有可重新解析的原始文件或文本内容。")
    except DocumentParseError as exc:
        status = "failed"
        error_message = str(exc)

    payload = dict(doc)
    if status == "parsed":
        base_name = f"{secure_filename(doc.get('title') or 'knowledge')}_{uuid.uuid4().hex[:8]}"
        text_file_path = save_parsed_text(parsed_text, KNOWLEDGE_TEXT_DIR, base_name)
        cleanup_result = delete_knowledge_document_index(doc_id)
        if cleanup_result.get("warning"):
            flash(cleanup_result["warning"], "warning")
        payload.update(
            {
                "parsed_text": parsed_text[:10000],
                "text_file_path": text_file_path,
                "summary": generate_basic_summary(parsed_text, title=doc.get("title"), doc_type=doc.get("doc_type")),
                "word_count": count_text_words(parsed_text),
                "status": "parsed",
                "error_message": "",
                "embedding_status": "not_indexed",
                "embedding_error": "",
                "indexed_at": "",
                "chunk_count": 0,
                "vector_collection": "",
            }
        )
    else:
        payload.update(
            {
                "status": "failed",
                "error_message": error_message,
            }
        )

    updated = update_knowledge_document(doc_id, payload)
    update_document_metadata_quality(updated)
    if status == "parsed":
        flash("资料已重新解析。", "success")
    else:
        flash(f"重新解析失败：{error_message}", "danger")
    return redirect(url_for("knowledge.knowledge_detail", doc_id=doc_id))


@knowledge_bp.route("/knowledge/search-semantic")
def knowledge_semantic_search_page():
    filters = _semantic_filters_from_request(request)
    query = str(request.args.get("query") or "").strip()
    top_k = _optional_int(request.args.get("top_k"), default=5, minimum=1, maximum=20)
    embedding_probe = test_embedding_connection()
    results = []
    search_error = ""

    if query:
        try:
            results = search_knowledge_semantic(query, filters=filters, top_k=top_k)
        except (EmbeddingServiceError, VectorStoreError) as exc:
            search_error = str(exc)

    return render_template(
        "knowledge_semantic_search.html",
        query=query,
        top_k=top_k,
        filters=filters,
        results=results,
        embedding_probe=embedding_probe,
        search_error=search_error,
        doc_type_options=DOC_TYPE_OPTIONS,
        grade_options=GRADE_OPTIONS,
        textbook_options=TEXTBOOK_OPTIONS,
        volume_options=VOLUME_OPTIONS,
        unit_options=UNIT_OPTIONS,
        lesson_type_options=LESSON_TYPE_OPTIONS,
    )


@knowledge_bp.route("/knowledge/<int:doc_id>/download")
def knowledge_download(doc_id):
    doc = get_knowledge_document(doc_id)
    if not doc:
        abort(404)
    source_path = str(doc.get("original_file_path") or "").strip()
    if not source_path or not Path(source_path).exists():
        flash("该资料没有原始文件。", "warning")
        return redirect(url_for("knowledge.knowledge_detail", doc_id=doc_id))
    download_name = doc.get("file_name") or Path(source_path).name
    return send_file(source_path, as_attachment=True, download_name=download_name)


@knowledge_bp.route("/knowledge/<int:doc_id>/text")
def knowledge_text(doc_id):
    doc = get_knowledge_document(doc_id)
    if not doc:
        abort(404)
    content = _load_full_text(doc)
    return render_template("knowledge_text.html", doc=doc, content=content)


@knowledge_bp.route("/knowledge/governance")
def knowledge_governance():
    docs = query_knowledge_documents({}, limit=1500)
    only_incomplete = str(request.args.get("only_incomplete") or "") == "1"
    only_unindexed = str(request.args.get("only_unindexed") or "") == "1"
    only_whole_book = str(request.args.get("only_whole_book") or "") == "1"
    only_suggest_split = str(request.args.get("only_suggest_split") or "") == "1"
    textbook_filter = str(request.args.get("textbook") or "").strip()
    volume_filter = str(request.args.get("volume") or "").strip()
    unit_filter = str(request.args.get("unit") or "").strip()
    doc_type_filter = str(request.args.get("doc_type") or "").strip()
    need_reindex_ids = {d["id"] for d in documents_need_reindex()}
    filtered = []
    for doc in docs:
        updated = update_document_metadata_quality(doc) or doc
        updated["need_reindex"] = updated["id"] in need_reindex_ids
        warnings_text = str(updated.get("metadata_warnings") or "")
        try:
            updated["warning_list"] = json.loads(warnings_text) if warnings_text else []
        except Exception:
            updated["warning_list"] = [warnings_text]
        if only_incomplete and int(updated.get("metadata_quality_score") or 0) >= 80:
            continue
        if only_unindexed and updated.get("embedding_status") == "indexed":
            continue
        if only_whole_book and not updated.get("is_whole_book"):
            continue
        if only_suggest_split and not updated.get("is_whole_book"):
            continue
        if textbook_filter and updated.get("textbook") != textbook_filter:
            continue
        if volume_filter and updated.get("volume") != volume_filter:
            continue
        if unit_filter and updated.get("unit") != unit_filter:
            continue
        if doc_type_filter and updated.get("doc_type") != doc_type_filter:
            continue
        filtered.append(updated)
    stats = {
        "total": len(docs),
        "indexed": sum(1 for d in docs if d.get("embedding_status") == "indexed"),
        "unindexed": sum(1 for d in docs if d.get("embedding_status") != "indexed"),
        "metadata_good": sum(1 for d in docs if int(d.get("metadata_quality_score") or 0) >= 80),
        "metadata_risk": sum(1 for d in docs if int(d.get("metadata_quality_score") or 0) < 80),
        "whole_book": sum(1 for d in docs if d.get("is_whole_book")),
        "need_split": sum(1 for d in docs if d.get("is_whole_book")),
    }
    return render_template(
        "knowledge_governance.html",
        docs=filtered,
        stats=stats,
        textbook_options=TEXTBOOK_OPTIONS,
        volume_options=VOLUME_OPTIONS,
        unit_options=UNIT_OPTIONS,
        doc_type_options=DOC_TYPE_OPTIONS,
    )


@knowledge_bp.route("/knowledge/coverage")
def knowledge_coverage():
    volume_filter = str(request.args.get("volume") or "").strip()
    coverage = get_knowledge_coverage().get("textbooks", [])
    if volume_filter:
        coverage = [group for group in coverage if group.get("volume") == volume_filter]
    return render_template(
        "knowledge_coverage.html",
        groups=coverage,
        volume_options=VOLUME_OPTIONS,
        volume_filter=volume_filter,
    )


@knowledge_bp.route("/knowledge/bulk-reindex", methods=["POST"])
def knowledge_bulk_reindex():
    reindex_unindexed = str(request.form.get("reindex_unindexed") or "").lower() in {"1", "true", "on", "yes"}
    reindex_stale = str(request.form.get("reindex_stale") or "").lower() in {"1", "true", "on", "yes"}
    limit = _optional_int(request.form.get("limit"), default=20, minimum=1, maximum=20)
    docs = query_knowledge_documents({}, limit=2000)
    stale_ids = {d["id"] for d in documents_need_reindex()}
    targets = []
    for doc in docs:
        if len(targets) >= limit:
            break
        if reindex_unindexed and doc.get("embedding_status") != "indexed" and _load_full_text(doc).strip():
            targets.append(doc)
            continue
        if reindex_stale and doc.get("id") in stale_ids:
            targets.append(doc)
    ok_count = 0
    failed = []
    for doc in targets:
        result = index_knowledge_document(doc["id"])
        if result.get("ok"):
            ok_count += 1
        else:
            failed.append(result.get("message") or f"doc {doc['id']} failed")
    if failed:
        flash(f"批量重索引完成：成功 {ok_count}，失败 {len(failed)}。示例：{failed[0]}", "warning")
    else:
        flash(f"批量重索引完成：成功 {ok_count}。", "success")
    return redirect(url_for("knowledge.knowledge_governance"))


@knowledge_bp.route("/knowledge/<int:doc_id>/mark-metadata-reviewed", methods=["POST"])
def knowledge_mark_metadata_reviewed(doc_id):
    doc = get_knowledge_document(doc_id)
    if not doc:
        abort(404)
    payload = dict(doc)
    payload["metadata_reviewed"] = True
    update_knowledge_document(doc_id, payload)
    flash("已标记元信息已人工确认。", "success")
    return redirect(url_for("knowledge.knowledge_detail", doc_id=doc_id))


@knowledge_bp.route("/knowledge/<int:doc_id>/suggest-metadata", methods=["POST"])
def knowledge_suggest_metadata(doc_id):
    doc = get_knowledge_document(doc_id)
    if not doc:
        abort(404)
    payload = dict(doc)
    payload.update(suggest_metadata(doc))
    update_knowledge_document(doc_id, payload)
    flash("已生成元信息建议。", "success")
    return redirect(url_for("knowledge.knowledge_detail", doc_id=doc_id))


@knowledge_bp.route("/knowledge/create-unit-placeholders", methods=["POST"])
def knowledge_create_placeholders():
    textbook = str(request.form.get("textbook") or "人教版").strip()
    volume = str(request.form.get("volume") or "必修二").strip()
    created = create_unit_placeholders(textbook, volume)
    flash(f"已创建 {created} 条 Unit 占位资料。", "success")
    return redirect(url_for("knowledge.knowledge_coverage"))
