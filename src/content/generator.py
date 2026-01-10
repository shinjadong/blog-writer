"""
콘텐츠 생성기

DeepSeek API를 사용하여 블로그 원고를 자동 생성합니다.

Author: CareOn Blog Writer
Created: 2026-01-10
"""

import json
import uuid
import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any

from src.shared.deepseek_client import DeepSeekClient
from src.shared.models import (
    Article,
    ArticleConfig,
    ArticleTemplate,
    ContentTone,
    GenerationOutline,
)
from src.content.prompts.cctv_domain import (
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

logger = logging.getLogger("blog_writer.generator")


class ContentGenerator:
    """
    블로그 원고 생성기

    키워드를 받아 DeepSeek API를 통해 블로그 원고를 생성합니다.

    사용 예시:
        generator = ContentGenerator(deepseek_api_key="...")
        article = await generator.generate(
            keyword="매장CCTV설치비용",
            config=ArticleConfig(
                template=ArticleTemplate.PERSONAL_STORY,
                tone=ContentTone.EMOTIONAL
            )
        )
    """

    def __init__(
        self,
        deepseek_api_key: str,
        model: str = "deepseek-chat"
    ):
        """
        Args:
            deepseek_api_key: DeepSeek API 키
            model: 사용할 모델 (기본: deepseek-chat)
        """
        self.deepseek = DeepSeekClient(api_key=deepseek_api_key, model=model)

    async def generate(
        self,
        keyword: str,
        config: ArticleConfig = None
    ) -> Article:
        """
        원고 생성 메인 메서드

        단계:
        1. 아웃라인 생성
        2. 섹션별 콘텐츠 생성
        3. 제목/메타 설명/태그 생성
        4. 품질 검증
        5. Article 객체 반환

        Args:
            keyword: 타겟 키워드
            config: 원고 생성 설정 (없으면 기본값 사용)

        Returns:
            생성된 Article 객체
        """
        if config is None:
            config = ArticleConfig(keyword=keyword)
        else:
            config.keyword = keyword

        logger.info(f"Starting article generation for keyword: {keyword}")

        try:
            # 1. 아웃라인 생성
            outline = await self.generate_outline(keyword, config)
            logger.info(f"Outline generated: {outline.title}")

            # 2. 섹션별 콘텐츠 생성
            sections_content = await self._generate_all_sections(outline, config)
            logger.info(f"Generated {len(sections_content)} sections")

            # 3. 전체 콘텐츠 조합
            full_content = self._assemble_content(outline, sections_content)

            # 4. 제목 변형 생성 (최적 선택)
            title = await self._select_best_title(keyword, full_content, outline.title)

            # 5. 메타 설명 생성
            meta_description = await self._generate_meta_description(keyword, full_content)

            # 6. 태그 생성
            tags = await self._generate_tags(keyword, full_content)

            # 7. 품질 점수 계산
            quality_score = self._calculate_quality_score(full_content, config)

            # 8. Article 객체 생성
            article = Article(
                id=str(uuid.uuid4()),
                keyword=keyword,
                title=title,
                content=full_content,
                meta_description=meta_description,
                tags=tags,
                sections=[{"title": s["title"], "content": s["content"][:100] + "..."} for s in sections_content],
                template=config.template.value if isinstance(config.template, ArticleTemplate) else config.template,
                tone=config.tone.value if isinstance(config.tone, ContentTone) else config.tone,
                domain=config.domain,
                quality_score=quality_score,
                seo_score=self._calculate_seo_score(full_content, keyword),
                readability_score=self._calculate_readability_score(full_content),
                word_count=len(full_content.replace(" ", "").replace("\n", "")),
                status="draft",
                created_at=datetime.now(),
                generation_config=config.__dict__,
                ai_model=self.deepseek.model,
            )

            logger.info(f"Article generated successfully: {article.title} ({article.word_count} chars)")
            return article

        except Exception as e:
            logger.error(f"Article generation failed: {e}")
            raise

    async def generate_outline(
        self,
        keyword: str,
        config: ArticleConfig
    ) -> GenerationOutline:
        """
        아웃라인 생성

        Args:
            keyword: 타겟 키워드
            config: 원고 설정

        Returns:
            GenerationOutline 객체
        """
        # 타겟 독자 정보 가져오기
        audience_info = TARGET_AUDIENCE_PERSONAS.get(
            config.target_audience,
            TARGET_AUDIENCE_PERSONAS["소상공인"]
        )

        # 템플릿 구조 가져오기
        template_key = config.template.value if isinstance(config.template, ArticleTemplate) else config.template
        template_info = TEMPLATE_STRUCTURES.get(
            template_key,
            TEMPLATE_STRUCTURES["personal_story"]
        )

        prompt = OUTLINE_GENERATION_PROMPT.format(
            keyword=keyword,
            target_audience=f"{config.target_audience} ({audience_info['persona']})",
            template_type=f"{template_info['name']} - 섹션: {[s['title'] for s in template_info['sections']]}"
        )

        response = await self.deepseek.generate_json(
            prompt=prompt,
            system_prompt=CCTV_BLOG_SYSTEM_PROMPT,
            temperature=0.7
        )

        return GenerationOutline(
            keyword=keyword,
            title=response.get("title", f"{keyword} 완벽 가이드"),
            hook=response.get("hook", ""),
            sections=response.get("sections", []),
            cta=response.get("cta", ""),
            estimated_length=response.get("estimated_length", config.target_length),
            target_keywords=response.get("target_keywords", [keyword])
        )

    async def _generate_all_sections(
        self,
        outline: GenerationOutline,
        config: ArticleConfig
    ) -> List[Dict[str, str]]:
        """모든 섹션 콘텐츠 생성"""
        sections_content = []
        previous_context = outline.hook

        for i, section in enumerate(outline.sections):
            section_content = await self._generate_section(
                keyword=outline.keyword,
                section=section,
                previous_context=previous_context,
                config=config
            )

            sections_content.append({
                "title": section.get("title", f"섹션 {i+1}"),
                "content": section_content
            })

            # 다음 섹션을 위한 컨텍스트 업데이트
            previous_context = section_content[:500]

        return sections_content

    async def _generate_section(
        self,
        keyword: str,
        section: Dict[str, Any],
        previous_context: str,
        config: ArticleConfig
    ) -> str:
        """개별 섹션 콘텐츠 생성"""
        prompt = SECTION_GENERATION_PROMPT.format(
            keyword=keyword,
            section_title=section.get("title", ""),
            section_purpose=section.get("purpose", ""),
            key_points=", ".join(section.get("key_points", [])),
            target_length=section.get("estimated_length", 500),
            previous_context=previous_context[:300]
        )

        return await self.deepseek.generate_blog_content(
            prompt=prompt,
            system_prompt=CCTV_BLOG_SYSTEM_PROMPT,
            temperature=0.8
        )

    def _assemble_content(
        self,
        outline: GenerationOutline,
        sections_content: List[Dict[str, str]]
    ) -> str:
        """전체 콘텐츠 조합"""
        parts = []

        # 도입부 (훅)
        if outline.hook:
            parts.append(outline.hook)
            parts.append("")

        # 섹션들
        for section in sections_content:
            content = section["content"].strip()

            # 콘텐츠가 이미 ## 제목으로 시작하는지 확인
            content_starts_with_heading = content.startswith("## ")

            if section["title"] and not content_starts_with_heading:
                # 제목이 콘텐츠에 없으면 추가
                parts.append(f"## {section['title']}")
            elif content_starts_with_heading:
                # 콘텐츠에 제목이 있으면 중복 제목 제거
                # (첫 줄이 ## 제목이면 그대로 사용)
                pass

            parts.append(content)
            parts.append("")

        # CTA
        if outline.cta:
            parts.append("---")
            parts.append("")
            parts.append(outline.cta)

        return "\n".join(parts)

    async def _select_best_title(
        self,
        keyword: str,
        content: str,
        default_title: str
    ) -> str:
        """최적 제목 선택"""
        try:
            prompt = TITLE_GENERATION_PROMPT.format(
                keyword=keyword,
                content_summary=content[:1000]
            )

            response = await self.deepseek.generate_json(
                prompt=prompt,
                system_prompt=CCTV_BLOG_SYSTEM_PROMPT,
                temperature=0.7
            )

            titles = response.get("titles", [])
            if titles:
                # 첫 번째 제목 선택 (가장 추천)
                return titles[0]

        except Exception as e:
            logger.warning(f"Title generation failed, using default: {e}")

        return default_title

    async def _generate_meta_description(
        self,
        keyword: str,
        content: str
    ) -> str:
        """메타 설명 생성"""
        try:
            prompt = META_DESCRIPTION_PROMPT.format(
                keyword=keyword,
                content_summary=content[:1000]
            )

            return await self.deepseek.chat(
                user_prompt=prompt,
                system_prompt=CCTV_BLOG_SYSTEM_PROMPT,
                temperature=0.5,
                max_tokens=200
            )

        except Exception as e:
            logger.warning(f"Meta description generation failed: {e}")
            return f"{keyword}에 대한 솔직한 후기와 정보를 공유합니다."

    async def _generate_tags(
        self,
        keyword: str,
        content: str
    ) -> List[str]:
        """태그 생성"""
        try:
            prompt = TAGS_GENERATION_PROMPT.format(
                keyword=keyword,
                content_summary=content[:1000]
            )

            response = await self.deepseek.generate_json(
                prompt=prompt,
                system_prompt=CCTV_BLOG_SYSTEM_PROMPT,
                temperature=0.5
            )

            return response.get("tags", [keyword])

        except Exception as e:
            logger.warning(f"Tags generation failed: {e}")
            return [keyword, "CCTV", "보안", "설치"]

    def _calculate_quality_score(
        self,
        content: str,
        config: ArticleConfig
    ) -> float:
        """품질 점수 계산 (0-1)"""
        score = 0.0

        # 1. 길이 점수 (목표 길이 대비)
        word_count = len(content.replace(" ", "").replace("\n", ""))
        length_ratio = min(word_count / config.target_length, 1.5)
        if 0.8 <= length_ratio <= 1.2:
            score += 0.25
        elif 0.6 <= length_ratio <= 1.4:
            score += 0.15

        # 2. 구조 점수 (소제목 수)
        heading_count = content.count("## ")
        if 3 <= heading_count <= 7:
            score += 0.25
        elif heading_count > 0:
            score += 0.1

        # 3. 키워드 포함 점수
        keyword_count = content.lower().count(config.keyword.lower())
        if 3 <= keyword_count <= 10:
            score += 0.25
        elif keyword_count > 0:
            score += 0.1

        # 4. 가독성 점수 (문단 분리)
        paragraph_count = len([p for p in content.split("\n\n") if p.strip()])
        if paragraph_count >= 5:
            score += 0.25

        return min(score, 1.0)

    def _calculate_seo_score(
        self,
        content: str,
        keyword: str
    ) -> float:
        """SEO 점수 계산 (0-1)"""
        score = 0.0

        # 키워드 밀도 (1-3% 권장)
        word_count = len(content.replace(" ", ""))
        keyword_count = content.lower().count(keyword.lower())
        density = (keyword_count * len(keyword)) / word_count if word_count > 0 else 0

        if 0.01 <= density <= 0.03:
            score += 0.4

        # 제목에 키워드 포함
        first_line = content.split("\n")[0] if content else ""
        if keyword.lower() in first_line.lower():
            score += 0.3

        # 소제목에 키워드 포함
        headings = re.findall(r"## .+", content)
        keyword_in_heading = any(keyword.lower() in h.lower() for h in headings)
        if keyword_in_heading:
            score += 0.3

        return min(score, 1.0)

    def _calculate_readability_score(
        self,
        content: str
    ) -> float:
        """가독성 점수 계산 (0-1)"""
        score = 0.0

        # 평균 문장 길이 (30-50자 권장)
        sentences = re.split(r"[.!?]", content)
        sentences = [s.strip() for s in sentences if s.strip()]
        if sentences:
            avg_length = sum(len(s) for s in sentences) / len(sentences)
            if 20 <= avg_length <= 60:
                score += 0.4

        # 문단 수 (5개 이상 권장)
        paragraphs = [p for p in content.split("\n\n") if p.strip()]
        if len(paragraphs) >= 5:
            score += 0.3

        # 소제목 수 (3개 이상 권장)
        heading_count = content.count("## ")
        if heading_count >= 3:
            score += 0.3

        return min(score, 1.0)

    async def regenerate_section(
        self,
        article: Article,
        section_index: int,
        feedback: str = ""
    ) -> str:
        """특정 섹션 재생성"""
        if section_index >= len(article.sections):
            raise ValueError(f"Invalid section index: {section_index}")

        section = article.sections[section_index]
        prompt = f"""기존 섹션을 개선해주세요.

## 기존 내용
{section.get('content', '')}

## 피드백
{feedback if feedback else '더 자연스럽고 공감가는 내용으로 개선해주세요.'}

## 요구사항
- 마크다운 형식
- 개인 경험 기반 서술
- 감정적 공감 요소 포함

개선된 콘텐츠만 출력하세요.
"""

        return await self.deepseek.generate_blog_content(
            prompt=prompt,
            system_prompt=CCTV_BLOG_SYSTEM_PROMPT,
            temperature=0.8
        )

    async def health_check(self) -> bool:
        """DeepSeek API 연결 확인"""
        return await self.deepseek.health_check()
