"""CCTV 도메인 및 SEO 프롬프트"""

from .cctv_domain import (
    CCTV_BLOG_SYSTEM_PROMPT,
    OUTLINE_GENERATION_PROMPT,
    SECTION_GENERATION_PROMPT,
    INTRO_HOOK_PROMPT,
    CTA_GENERATION_PROMPT,
    TITLE_GENERATION_PROMPT,
    META_DESCRIPTION_PROMPT,
    TAGS_GENERATION_PROMPT,
    TARGET_AUDIENCE_PERSONAS,
    TEMPLATE_STRUCTURES,
)

from .seo_prompts import (
    COMPETITION_ANALYSIS_SYSTEM_PROMPT,
    SEO_CONTENT_SYSTEM_PROMPT,
    OUTLINE_REASONING_SYSTEM_PROMPT,
    QUALITY_EVALUATION_PROMPT,
    build_competition_analysis_prompt,
    build_seo_content_prompt,
    build_outline_prompt,
    build_section_content_prompt,
)

__all__ = [
    # CCTV 도메인
    "CCTV_BLOG_SYSTEM_PROMPT",
    "OUTLINE_GENERATION_PROMPT",
    "SECTION_GENERATION_PROMPT",
    "INTRO_HOOK_PROMPT",
    "CTA_GENERATION_PROMPT",
    "TITLE_GENERATION_PROMPT",
    "META_DESCRIPTION_PROMPT",
    "TAGS_GENERATION_PROMPT",
    "TARGET_AUDIENCE_PERSONAS",
    "TEMPLATE_STRUCTURES",
    # SEO 프롬프트
    "COMPETITION_ANALYSIS_SYSTEM_PROMPT",
    "SEO_CONTENT_SYSTEM_PROMPT",
    "OUTLINE_REASONING_SYSTEM_PROMPT",
    "QUALITY_EVALUATION_PROMPT",
    "build_competition_analysis_prompt",
    "build_seo_content_prompt",
    "build_outline_prompt",
    "build_section_content_prompt",
]
