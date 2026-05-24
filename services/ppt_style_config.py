"""Built-in PPT style profiles for exported classroom decks."""

PPT_STYLE_PROFILES = {
    "default": {
        "name": "default",
        "background": (246, 248, 252),
        "surface": (255, 255, 255),
        "primary": (24, 76, 121),
        "secondary": (53, 95, 136),
        "accent": (235, 165, 82),
        "text": (32, 43, 57),
        "muted": (96, 112, 128),
        "soft": (231, 240, 248),
    },
    "open_class": {
        "name": "open_class",
        "background": (248, 246, 241),
        "surface": (255, 255, 255),
        "primary": (18, 54, 92),
        "secondary": (120, 80, 39),
        "accent": (214, 156, 81),
        "text": (33, 34, 36),
        "muted": (103, 95, 87),
        "soft": (241, 233, 220),
    },
    "review": {
        "name": "review",
        "background": (243, 248, 244),
        "surface": (255, 255, 255),
        "primary": (49, 101, 74),
        "secondary": (85, 132, 108),
        "accent": (143, 179, 101),
        "text": (33, 47, 40),
        "muted": (98, 118, 107),
        "soft": (228, 239, 231),
    },
}


STYLE_ALIAS = {
    "常规课": "default",
    "公开课": "open_class",
    "复习课": "review",
}


def get_ppt_style_profile(task):
    style_name = STYLE_ALIAS.get(task.get("style"), "default")
    return PPT_STYLE_PROFILES.get(style_name, PPT_STYLE_PROFILES["default"])
