"""Layout planner agent.

Current stage: mock / rule-based implementation.
Future replacement: a real model can plan slide composition from slide content
and teaching intent while keeping the same layout_plan schema.
"""


LAYOUT_TYPE_MAP = {
    "cover": "cover_layout",
    "objectives": "objectives_layout",
    "task_design": "reading_task_layout",
    "lead_in": "leadin_question_layout",
    "warm_up": "warmup_card_layout",
    "pre_reading": "prediction_flow_layout",
    "prediction": "prediction_flow_layout",
    "pre_listening": "image_question_layout",
    "fast_reading": "reading_task_layout",
    "careful_reading": "reading_task_layout",
    "while_listening": "reading_task_layout",
    "guided_practice": "reading_task_layout",
    "controlled_practice": "reading_task_layout",
    "communicative_practice": "reading_task_layout",
    "exercise_practice": "reading_task_layout",
    "writing_task": "reading_task_layout",
    "speaking_task": "reading_task_layout",
    "grammar_rule": "comparison_layout",
    "structure_analysis": "comparison_layout",
    "key_grammar_review": "comparison_layout",
    "error_analysis": "comparison_layout",
    "vocabulary_focus": "vocabulary_card_layout",
    "useful_expressions": "vocabulary_card_layout",
    "key_vocabulary_review": "vocabulary_card_layout",
    "language_points": "sentence_analysis_layout",
    "sample_analysis": "sentence_analysis_layout",
    "observe_discover": "sentence_analysis_layout",
    "error_correction": "sentence_analysis_layout",
    "group_discussion": "discussion_layout",
    "pair_work": "discussion_layout",
    "peer_review": "discussion_layout",
    "summary": "mindmap_layout",
    "consolidation": "mindmap_layout",
    "homework": "homework_layout",
    "blackboard_design": "blackboard_layout",
}


def _topic_parts(lesson_request):
    topic = lesson_request.get("topic") or lesson_request.get("course_title") or "Lesson Topic"
    keyword = topic.split()[-1].strip(".,!?") if topic.strip() else "topic"
    return topic, keyword


def _trim_items(items, limit=5):
    cleaned = [str(item).strip() for item in items if str(item or "").strip()]
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + ["..."]


def _chunk_items(items, chunk_size):
    items = _trim_items(items, limit=6)
    return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]


def _image_placeholder_text(lesson_request):
    topic, keyword = _topic_parts(lesson_request)
    return f"Image Placeholder: {topic} / scene / {keyword}"


def _build_content_blocks(layout_type, slide, lesson_request):
    items = list(slide.get("visible_content", []) or [])
    key_sentence = str(slide.get("key_sentence") or "").strip()
    image_suggestion = str(slide.get("image_suggestion") or "").strip()
    useful_expressions = list(slide.get("useful_expressions", []) or [])
    possible_answers = list(slide.get("possible_answers", []) or [])
    topic, keyword = _topic_parts(lesson_request)

    if layout_type == "cover_layout":
        return [
            {"role": "meta", "title": "Lesson Info", "items": _trim_items(items, limit=3)},
        ]

    if layout_type == "preserve_cover_layout":
        return [
            {"role": "cover_title", "title": slide.get("title"), "items": _trim_items(items[:2], limit=2)},
            {
                "role": "image_placeholder",
                "title": "Scene",
                "items": [image_suggestion or _image_placeholder_text(lesson_request)],
            },
            {"role": "meta", "title": "Meta", "items": _trim_items(items[2:], limit=3)},
        ]

    if layout_type == "objectives_layout":
        cards = []
        for index, item in enumerate(_trim_items(items, limit=4), start=1):
            cards.append({"role": "objective_card", "title": f"Objective {index}", "items": [item]})
        return cards

    if layout_type == "image_question_layout":
        return [
            {
                "role": "image_placeholder",
                "title": "Scene",
                "items": [image_suggestion or _image_placeholder_text(lesson_request)],
            },
            {
                "role": "question_panel",
                "title": slide.get("title"),
                "items": _trim_items(([key_sentence] if key_sentence else []) + items, limit=3),
            },
        ]

    if layout_type == "leadin_question_layout":
        return [
            {
                "role": "image_placeholder",
                "title": "Scene",
                "items": [image_suggestion or _image_placeholder_text(lesson_request)],
            },
            {
                "role": "question_cards",
                "title": slide.get("title"),
                "items": _trim_items(([key_sentence] if key_sentence else []) + items, limit=3),
            },
            {
                "role": "expression_support",
                "title": "Useful Expressions",
                "items": _trim_items(useful_expressions, limit=4),
            },
        ]

    if layout_type == "prediction_flow_layout":
        primary = _trim_items(items, limit=4)
        return [
            {"role": "before_reading", "title": "Before Reading", "items": primary[:1] or [f"Look at the topic of {topic}."]},
            {"role": "predict", "title": "Predict", "items": primary[1:3] or ["Predict the key idea.", "Give one reason."]},
            {"role": "share", "title": "Share", "items": possible_answers[:2] or primary[3:] or ["Share your idea with a partner."]},
            {
                "role": "expression_support",
                "title": "Useful Expressions",
                "items": _trim_items(useful_expressions, limit=4),
            },
            {
                "role": "image_placeholder",
                "title": "Scene",
                "items": [image_suggestion or _image_placeholder_text(lesson_request)],
            },
        ]

    if layout_type == "warmup_card_layout":
        return [
            {
                "role": "image_placeholder",
                "title": "Scene",
                "items": [image_suggestion or _image_placeholder_text(lesson_request)],
            },
            {
                "role": "sentence_box",
                "title": "Key Sentence",
                "items": [key_sentence] if key_sentence else _trim_items(items[:1], limit=1),
            },
            {
                "role": "answer_tags",
                "title": "Possible Answers",
                "items": _trim_items(possible_answers or items[1:], limit=4),
            },
            {
                "role": "expression_support",
                "title": "Useful Expressions",
                "items": _trim_items(useful_expressions, limit=4),
            },
        ]

    if layout_type == "reading_task_layout":
        primary = _trim_items(items, limit=5)
        return [
            {"role": "task_steps", "title": "Task Flow", "items": primary[:3]},
            {
                "role": "checklist",
                "title": "Possible Answers" if possible_answers else "Do This",
                "items": _trim_items(possible_answers or primary[3:] or ["Complete the classroom task."], limit=3),
            },
        ]

    if layout_type == "comparison_layout":
        columns = _chunk_items(items, chunk_size=2)
        left_items = columns[0] if columns else []
        right_items = _trim_items(possible_answers, limit=3) if possible_answers else columns[1] if len(columns) > 1 else []
        if not right_items and len(left_items) > 1:
            midpoint = max(1, len(left_items) // 2)
            right_items = left_items[midpoint:]
            left_items = left_items[:midpoint]
        return [
            {"role": "left_column", "title": "Focus A", "items": left_items or [f"Notice the key idea about {keyword}."]},
            {"role": "right_column", "title": "Focus B", "items": right_items or ["Explain the difference or reason."]},
        ]

    if layout_type == "vocabulary_card_layout":
        cards = []
        card_items = _trim_items(useful_expressions or items, limit=3)
        for index, item in enumerate(card_items, start=1):
            cards.append({"role": "vocabulary_card", "title": f"Card {index}", "items": [item]})
        return cards

    if layout_type == "sentence_analysis_layout":
        primary = _trim_items(items, limit=4)
        sentence = key_sentence or (primary[0] if primary else f"Sentence focus about {keyword}.")
        steps = primary[1:] if key_sentence else primary[1:]
        steps = _trim_items(steps + useful_expressions[:2] + possible_answers[:1], limit=3) or ["Break the sentence into smaller meaning groups."]
        return [
            {"role": "sentence_box", "title": "Sentence Focus", "items": [sentence]},
            {"role": "analysis_steps", "title": "Analysis", "items": steps},
        ]

    if layout_type == "discussion_layout":
        primary = _trim_items(items, limit=4)
        return [
            {"role": "discussion_prompt", "title": "Discuss", "items": primary[:1] or [f"Share ideas about {topic}."]},
            {"role": "group_roles", "title": "How To Work", "items": primary[1:3] or ["Choose a speaker.", "Prepare one class report."]},
            {
                "role": "share_out",
                "title": "Output",
                "items": _trim_items(possible_answers or primary[3:] or ["Share one strong idea with the class."], limit=3),
            },
            {
                "role": "expression_support",
                "title": "Useful Expressions",
                "items": _trim_items(useful_expressions, limit=4),
            },
        ]

    if layout_type == "mindmap_layout":
        primary = _trim_items(items, limit=5)
        center_text = primary[0] if primary else topic
        branches = primary[1:] or ["Key language", "Main task", "Learning result"]
        return [
            {"role": "center_topic", "title": "Center", "items": [center_text]},
            {"role": "branches", "title": "Branches", "items": branches},
        ]

    if layout_type == "homework_layout":
        primary = _trim_items(items, limit=5)
        return [
            {"role": "required_task", "title": "Required", "items": primary[:2] or ["Review today's key language."]},
            {"role": "extension_task", "title": "Extension", "items": primary[2:4] or ["Finish the follow-up task after class."]},
            {"role": "reminder", "title": "Reminder", "items": primary[4:] or ["Bring one question to the next class."]},
        ]

    if layout_type == "blackboard_layout":
        primary = _trim_items(items, limit=5)
        return [
            {"role": "board_header", "title": "Board Theme", "items": primary[:1] or [topic]},
            {"role": "board_left", "title": "Language", "items": primary[1:3] or ["Key words", "Sentence frame"]},
            {"role": "board_right", "title": "Task", "items": primary[3:] or ["Task reminder", "Output target"]},
        ]

    return [{"role": "content", "title": slide.get("title"), "items": _trim_items(items, limit=4)}]


def _visual_suggestion(layout_type, lesson_request):
    image_label = _image_placeholder_text(lesson_request)
    suggestions = {
        "cover_layout": "Strong title panel with clean course metadata and one accent badge.",
        "preserve_cover_layout": "Use a formal cover layout with one strong title, one subtitle, and a large visual placeholder.",
        "objectives_layout": "Three-card objective grid with clear hierarchy and balanced spacing.",
        "leadin_question_layout": "Use question cards for the warm-up and keep one image placeholder nearby.",
        "prediction_flow_layout": "Show a Before reading → Predict → Share flow with expression support.",
        "warmup_card_layout": "Use a strong key-sentence card, possible-answer tags, and one image placeholder.",
        "image_question_layout": f"Use a large image placeholder on the left and a question card on the right: {image_label}",
        "reading_task_layout": "Use task cards or a staged process flow to show classroom steps.",
        "comparison_layout": "Split the slide into two columns for contrast, rule comparison, or example analysis.",
        "vocabulary_card_layout": "Show vocabulary in compact cards with one idea per card.",
        "sentence_analysis_layout": "Use one sentence focus bar plus structured analysis blocks below it.",
        "discussion_layout": "Center the discussion prompt and surround it with task or role cards.",
        "mindmap_layout": "Place the summary idea in the center and radiate key points outward.",
        "homework_layout": "Use checklist or task cards to separate required and extension homework.",
        "blackboard_layout": "Simulate a classroom board with major sections for theme, language, and task.",
    }
    return suggestions.get(layout_type, "Use a clean classroom slide structure with clear spacing.")


def _emphasis_level(layout_type):
    if layout_type in {"cover_layout", "preserve_cover_layout", "discussion_layout", "mindmap_layout", "warmup_card_layout"}:
        return "high"
    if layout_type in {"objectives_layout", "homework_layout", "blackboard_layout"}:
        return "medium"
    return "balanced"


def _teacher_hint_position(layout_type):
    positions = {
        "cover_layout": "bottom_left",
        "preserve_cover_layout": "bottom_left",
        "objectives_layout": "footer",
        "leadin_question_layout": "right_panel",
        "prediction_flow_layout": "footer",
        "warmup_card_layout": "footer",
        "image_question_layout": "right_panel",
        "reading_task_layout": "right_panel",
        "comparison_layout": "footer",
        "vocabulary_card_layout": "footer",
        "sentence_analysis_layout": "bottom_right",
        "discussion_layout": "footer",
        "mindmap_layout": "footer",
        "homework_layout": "right_panel",
        "blackboard_layout": "bottom_right",
    }
    return positions.get(layout_type, "footer")


def plan_layout_for_slide(slide, lesson_request):
    """Generate a layout plan for one slide."""

    slide_type = slide.get("slide_type")
    layout_type = LAYOUT_TYPE_MAP.get(slide_type, "reading_task_layout")
    is_preserve = str(lesson_request.get("manuscript_generation_strategy") or "").strip() == "preserve_original_pages"
    if is_preserve and slide_type == "cover":
        layout_type = "preserve_cover_layout"
    if slide_type not in {"cover", "objectives", "summary", "homework", "blackboard_design"}:
        preserve_locked_types = {"lead_in", "warm_up", "pre_reading", "prediction"}
        if is_preserve and slide_type in preserve_locked_types:
            pass
        elif slide.get("key_sentence"):
            layout_type = "sentence_analysis_layout"
        elif slide.get("useful_expressions"):
            layout_type = "vocabulary_card_layout"
        elif slide.get("image_suggestion"):
            layout_type = "image_question_layout"
        elif slide.get("possible_answers"):
            layout_type = "comparison_layout"
    visual_suggestion = _visual_suggestion(layout_type, lesson_request)
    if slide.get("image_suggestion"):
        visual_suggestion = f"{visual_suggestion} Image suggestion: {slide.get('image_suggestion')}."
    return {
        "layout_type": layout_type,
        "content_blocks": _build_content_blocks(layout_type, slide, lesson_request),
        "visual_suggestion": visual_suggestion,
        "emphasis_level": _emphasis_level(layout_type),
        "need_image_placeholder": layout_type == "image_question_layout" or bool(slide.get("image_suggestion")),
        "teacher_hint_position": _teacher_hint_position(layout_type),
    }


def plan_layouts(slides, lesson_request):
    """Attach layout_plan to each slide after content generation."""

    planned_slides = []
    for slide in slides:
        planned = dict(slide)
        planned["layout_plan"] = plan_layout_for_slide(planned, lesson_request)
        planned_slides.append(planned)
    return planned_slides
