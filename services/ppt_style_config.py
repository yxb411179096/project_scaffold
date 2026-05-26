"""Compatibility shim for renderer style profile.

Canonical preset definitions live in services/ppt_style_service.py.
"""

from services.ppt_style_service import get_style_preset, recommend_style_key


def get_ppt_style_profile(task):
    style_key = str(task.get("ppt_style") or "").strip().lower()
    if not style_key:
        style_key = recommend_style_key(task.get("lesson_type"), task.get("style"))
    preset = get_style_preset(style_key=style_key, lesson_type=task.get("lesson_type"), teaching_style=task.get("style"))
    return {
        "name": preset["style_key"],
        "display_name": preset["display_name"],
        "background": preset["background_color"],
        "surface": preset["card_background"],
        "primary": preset["primary_color"],
        "secondary": preset["secondary_color"],
        "accent": preset["accent_color"],
        "text": preset["text_color"],
        "muted": preset["muted_text_color"],
        "soft": tuple(min(255, int((c + 255) / 2)) for c in preset["border_color"]),
        "border": preset["border_color"],
        "title_font_size": preset["title_font_size"],
        "subtitle_font_size": preset["subtitle_font_size"],
        "body_font_size": preset["body_font_size"],
        "small_font_size": preset["small_font_size"],
        "card_radius": preset["card_radius"],
        "card_shadow": bool(preset.get("card_shadow")),
        "footer_style": preset["footer_style"],
        "title_align": preset["title_align"],
        "background_pattern": preset["background_pattern"],
    }
