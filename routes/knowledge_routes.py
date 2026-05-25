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
UNIT_OPTIONS = ["Unit 1", "Unit 2", "Unit 3", "Unit 4", "通用"]
LESSON_TYPE_OPTIONS = ["Reading", "Grammar", "Writing", "Listening and Speaking", "Revision", "Vocabulary", "Other"]
STATUS_OPTIONS = ["pending", "parsed", "failed"]


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
    }
    docs = query_knowledge_documents(filters, limit=50)
    return render_template(
        "knowledge_list.html",
        docs=docs,
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
    if request.method == "GET":
        return render_template(
            "knowledge_new.html",
            form_data=form_data,
            doc_type_options=DOC_TYPE_OPTIONS,
            grade_options=GRADE_OPTIONS,
            textbook_options=TEXTBOOK_OPTIONS,
            volume_options=VOLUME_OPTIONS,
            unit_options=UNIT_OPTIONS,
            lesson_type_options=LESSON_TYPE_OPTIONS,
        )

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
        return render_template(
            "knowledge_new.html",
            form_data=form_data,
            doc_type_options=DOC_TYPE_OPTIONS,
            grade_options=GRADE_OPTIONS,
            textbook_options=TEXTBOOK_OPTIONS,
            volume_options=VOLUME_OPTIONS,
            unit_options=UNIT_OPTIONS,
            lesson_type_options=LESSON_TYPE_OPTIONS,
        )

    source_type = "text"
    file_name = ""
    original_file_path = ""
    file_text = ""

    if upload and upload.filename:
        safe_name = secure_filename(upload.filename)
        suffix = Path(safe_name).suffix.lower()
        if suffix not in SUPPORTED_MANUSCRIPT_EXTENSIONS:
            flash("不支持的文件格式，仅支持 txt / md / docx / pdf。", "danger")
            return render_template(
                "knowledge_new.html",
                form_data=form_data,
                doc_type_options=DOC_TYPE_OPTIONS,
                grade_options=GRADE_OPTIONS,
                textbook_options=TEXTBOOK_OPTIONS,
                volume_options=VOLUME_OPTIONS,
                unit_options=UNIT_OPTIONS,
                lesson_type_options=LESSON_TYPE_OPTIONS,
            )

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
        return render_template(
            "knowledge_new.html",
            form_data=form_data,
            doc_type_options=DOC_TYPE_OPTIONS,
            grade_options=GRADE_OPTIONS,
            textbook_options=TEXTBOOK_OPTIONS,
            volume_options=VOLUME_OPTIONS,
            unit_options=UNIT_OPTIONS,
            lesson_type_options=LESSON_TYPE_OPTIONS,
        )

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
    flash("知识资料已保存并解析完成。", "success")
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
    return render_template(
        "knowledge_detail.html",
        doc=doc,
        preview_text=preview_text,
        is_truncated=is_truncated,
        chunks=chunks,
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

    update_knowledge_document(doc_id, payload)
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
