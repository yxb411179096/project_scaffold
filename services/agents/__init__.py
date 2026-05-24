"""Mock/rule-based agent package for the lesson generation pipeline.

These agents currently use local rules and templates so the MVP can keep
running without any external AI dependency. Later turns can replace the
internals with Ollama / DeepSeek / OpenAI calls while keeping the same
function signatures.
"""

from services.agents.activity_review_agent import review_activities
from services.agents.content_compressor_agent import (
    compress_slide_content,
    generate_rule_compressed_slides,
)
from services.agents.json_schema_checker import check_schema
from services.agents.layout_planner_agent import plan_layout_for_slide, plan_layouts
from services.agents.language_polish_agent import polish_language
from services.agents.lesson_design_agent import generate_lesson_design, generate_rule_lesson_design
from services.agents.lesson_structure_extractor_agent import (
    extract_lesson_structure,
    generate_rule_lesson_structure,
)
from services.agents.manuscript_analyzer_agent import (
    analyze_manuscript,
    generate_rule_manuscript_analysis,
)
from services.agents.original_page_parser_agent import (
    generate_rule_original_page_slides,
    parse_original_pages,
)
from services.agents.page_structure_detector_agent import (
    detect_page_structure,
    generate_rule_page_structure_detection,
)
from services.agents.ppt_outline_agent import generate_ppt_outline, generate_rule_ppt_outline
from services.agents.requirement_parser_agent import parse_requirement
from services.agents.slide_content_agent import (
    generate_rule_slide_content,
    generate_single_slide_content,
    generate_slide_content,
)
from services.agents.slide_splitter_agent import (
    generate_rule_slides_from_manuscript,
    regenerate_manuscript_slide,
    split_manuscript_into_slides,
)

__all__ = [
    "analyze_manuscript",
    "check_schema",
    "compress_slide_content",
    "detect_page_structure",
    "extract_lesson_structure",
    "generate_rule_compressed_slides",
    "generate_lesson_design",
    "generate_rule_lesson_structure",
    "generate_rule_manuscript_analysis",
    "generate_rule_original_page_slides",
    "generate_rule_page_structure_detection",
    "generate_ppt_outline",
    "generate_rule_lesson_design",
    "generate_rule_ppt_outline",
    "generate_rule_slides_from_manuscript",
    "generate_rule_slide_content",
    "generate_single_slide_content",
    "generate_slide_content",
    "parse_original_pages",
    "parse_requirement",
    "plan_layout_for_slide",
    "plan_layouts",
    "polish_language",
    "regenerate_manuscript_slide",
    "review_activities",
    "split_manuscript_into_slides",
]
