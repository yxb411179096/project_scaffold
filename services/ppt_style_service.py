"""PPT style preset service.

This module centralizes style presets and style recommendation rules.
It is rule-based for now and can be extended later with DB-managed presets.
"""

from copy import deepcopy


PPT_STYLE_PRESETS = {
    "default": {
        "style_key": "default",
        "display_name": "默认简洁风",
        "primary_color": (24, 76, 121),
        "secondary_color": (53, 95, 136),
        "accent_color": (235, 165, 82),
        "background_color": (246, 248, 252),
        "card_background": (255, 255, 255),
        "text_color": (32, 43, 57),
        "muted_text_color": (96, 112, 128),
        "border_color": (223, 232, 242),
        "title_font_size": 24,
        "subtitle_font_size": 16,
        "body_font_size": 16,
        "small_font_size": 10,
        "card_radius": 0.12,
        "card_shadow": False,
        "footer_style": "subtle",
        "title_align": "left",
        "background_pattern": "none",
    },
    "open_class": {
        "style_key": "open_class",
        "display_name": "公开课展示风",
        "primary_color": (18, 54, 92),
        "secondary_color": (120, 80, 39),
        "accent_color": (214, 156, 81),
        "background_color": (248, 246, 241),
        "card_background": (255, 255, 255),
        "text_color": (33, 34, 36),
        "muted_text_color": (103, 95, 87),
        "border_color": (224, 211, 194),
        "title_font_size": 28,
        "subtitle_font_size": 18,
        "body_font_size": 17,
        "small_font_size": 10,
        "card_radius": 0.14,
        "card_shadow": True,
        "footer_style": "strong",
        "title_align": "left",
        "background_pattern": "soft_blocks",
    },
    "fresh_classroom": {
        "style_key": "fresh_classroom",
        "display_name": "清新课堂风",
        "primary_color": (42, 102, 126),
        "secondary_color": (80, 136, 123),
        "accent_color": (128, 186, 157),
        "background_color": (242, 250, 248),
        "card_background": (250, 255, 253),
        "text_color": (37, 53, 59),
        "muted_text_color": (102, 123, 130),
        "border_color": (204, 228, 220),
        "title_font_size": 24,
        "subtitle_font_size": 16,
        "body_font_size": 16,
        "small_font_size": 10,
        "card_radius": 0.16,
        "card_shadow": False,
        "footer_style": "subtle",
        "title_align": "left",
        "background_pattern": "light_grid",
    },
    "reading_focus": {
        "style_key": "reading_focus",
        "display_name": "阅读课专用风",
        "primary_color": (22, 73, 126),
        "secondary_color": (41, 121, 148),
        "accent_color": (246, 179, 66),
        "background_color": (243, 248, 253),
        "card_background": (255, 255, 255),
        "text_color": (31, 44, 59),
        "muted_text_color": (99, 116, 133),
        "border_color": (210, 225, 238),
        "title_font_size": 25,
        "subtitle_font_size": 16,
        "body_font_size": 16,
        "small_font_size": 10,
        "card_radius": 0.12,
        "card_shadow": False,
        "footer_style": "subtle",
        "title_align": "left",
        "background_pattern": "reading_lines",
    },
    "writing_focus": {
        "style_key": "writing_focus",
        "display_name": "写作课专用风",
        "primary_color": (79, 63, 137),
        "secondary_color": (104, 84, 164),
        "accent_color": (224, 164, 96),
        "background_color": (248, 246, 254),
        "card_background": (255, 255, 255),
        "text_color": (44, 39, 68),
        "muted_text_color": (112, 104, 145),
        "border_color": (222, 216, 241),
        "title_font_size": 24,
        "subtitle_font_size": 16,
        "body_font_size": 16,
        "small_font_size": 10,
        "card_radius": 0.14,
        "card_shadow": False,
        "footer_style": "subtle",
        "title_align": "left",
        "background_pattern": "writing_grid",
    },
    "grammar_focus": {
        "style_key": "grammar_focus",
        "display_name": "语法课专用风",
        "primary_color": (103, 53, 31),
        "secondary_color": (142, 87, 63),
        "accent_color": (217, 151, 92),
        "background_color": (252, 248, 243),
        "card_background": (255, 255, 255),
        "text_color": (56, 44, 36),
        "muted_text_color": (127, 108, 95),
        "border_color": (235, 221, 206),
        "title_font_size": 24,
        "subtitle_font_size": 16,
        "body_font_size": 16,
        "small_font_size": 10,
        "card_radius": 0.12,
        "card_shadow": False,
        "footer_style": "subtle",
        "title_align": "left",
        "background_pattern": "rule_blocks",
    },
}


STYLE_KEY_OPTIONS = [
    "default",
    "open_class",
    "fresh_classroom",
    "reading_focus",
    "writing_focus",
    "grammar_focus",
]


def normalize_style_key(style_key):
    key = str(style_key or "").strip().lower()
    if key in PPT_STYLE_PRESETS:
        return key
    return "default"


def recommend_style_key(lesson_type=None, teaching_style=None):
    teaching_style_text = str(teaching_style or "").strip()
    lesson_key = str(lesson_type or "").strip().lower()
    if teaching_style_text == "公开课":
        return "open_class"
    if lesson_key == "reading":
        return "reading_focus"
    if lesson_key == "writing":
        return "writing_focus"
    if lesson_key == "grammar":
        return "grammar_focus"
    return "default"


def get_style_preset(style_key=None, lesson_type=None, teaching_style=None):
    chosen = normalize_style_key(style_key or recommend_style_key(lesson_type, teaching_style))
    preset = deepcopy(PPT_STYLE_PRESETS.get(chosen, PPT_STYLE_PRESETS["default"]))
    preset["style_key"] = chosen
    return preset


def style_display_name(style_key):
    preset = get_style_preset(style_key=style_key)
    return preset.get("display_name", "默认简洁风")


def get_style_options():
    return [(key, PPT_STYLE_PRESETS[key]["display_name"]) for key in STYLE_KEY_OPTIONS]

