"""Round 0.12.1 regression checks.

Focus:
- Preserve-mode objective parsing should bind number markers with full lines.
- Compressor should not keep orphan markers like "1." / "2." in visible content.
"""

from services.agents.content_compressor_agent import generate_rule_compressed_slides
from services.agents.original_page_parser_agent import generate_rule_original_page_slides


def _is_orphan_marker(line):
    text = str(line or "").strip()
    if not text:
        return True
    return text in {"1.", "2.", "3.", "4.", "A.", "B.", "C."}


def run():
    lesson_request = {
        "lesson_type": "Reading",
        "manuscript_generation_strategy": "preserve_original_pages",
    }
    manuscript_text = """
第1页: Cover
The Power of Reading

第2页: Learning Objectives
1.
Understand the key idea of the passage and find supporting details.
2.
Identify useful expressions and use them in short responses.
3.
Share personal reading habits and give one reason clearly.
"""
    parsed_slides = generate_rule_original_page_slides(lesson_request, manuscript_text)
    objectives = [slide for slide in parsed_slides if slide.get("slide_type") == "objectives"]
    assert objectives, "Expected an objectives slide in parsed slides."
    objective_slide = objectives[0]
    assert len(objective_slide.get("visible_content", [])) >= 3, "Expected at least 3 parsed objective lines."
    assert not any(_is_orphan_marker(item) for item in objective_slide.get("visible_content", [])), "Parsed objective content still includes orphan number markers."

    compressed_slides = generate_rule_compressed_slides(parsed_slides, lesson_request)
    compressed_objectives = [slide for slide in compressed_slides if slide.get("slide_type") == "objectives"]
    assert compressed_objectives, "Expected an objectives slide after compression."
    compressed_slide = compressed_objectives[0]
    assert len(compressed_slide.get("visible_content", [])) >= 3, "Expected at least 3 compressed objective lines."
    assert not any(_is_orphan_marker(item) for item in compressed_slide.get("visible_content", [])), "Compressed objective content still includes orphan number markers."
    print("ROUND_0121_OK")


if __name__ == "__main__":
    run()
