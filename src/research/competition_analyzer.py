"""
경쟁 분석기

네이버 검색 결과를 DeepSeek Reasoner로 분석하여
SEO 인사이트와 콘텐츠 갭을 파악합니다.
"""

import logging
from typing import Dict, List, Optional
from dataclasses import dataclass

from src.shared.deepseek_client import DeepSeekClient
from src.content.prompts.seo_prompts import (
    COMPETITION_ANALYSIS_SYSTEM_PROMPT,
    build_competition_analysis_prompt
)

logger = logging.getLogger("blog_writer.competition_analyzer")


@dataclass
class CompetitionAnalysis:
    """경쟁 분석 결과"""
    keyword: str
    competition_level: str  # low, medium, high
    avg_word_count: int
    blog_exposure_count: int
    search_intent: str  # informational, transactional, navigational
    content_gaps: List[str]
    seo_recommendations: List[str]
    title_suggestions: List[str]
    reasoning: str  # Reasoner의 추론 과정


class CompetitionAnalyzer:
    """
    경쟁 분석기

    네이버 검색 결과를 분석하여 SEO 전략을 수립합니다.

    사용 예시:
        analyzer = CompetitionAnalyzer(deepseek_client)
        analysis = await analyzer.analyze(search_result)
    """

    def __init__(self, deepseek_client: DeepSeekClient):
        """
        Args:
            deepseek_client: DeepSeek API 클라이언트
        """
        self.client = deepseek_client

    async def analyze(
        self,
        search_result: Dict,
        keyword: Optional[str] = None
    ) -> CompetitionAnalysis:
        """
        검색 결과 분석

        Args:
            search_result: NaverSearchClient.search_and_analyze() 결과
            keyword: 키워드 (search_result에 없는 경우)

        Returns:
            CompetitionAnalysis 분석 결과
        """
        kw = keyword or search_result.get("keyword", "")
        top_blogs = search_result.get("top_blogs", [])

        if not top_blogs:
            logger.warning(f"No blogs to analyze for keyword: {kw}")
            return self._empty_analysis(kw)

        # 분석 프롬프트 생성
        prompt = build_competition_analysis_prompt(kw, top_blogs)

        try:
            # DeepSeek Reasoner로 분석
            result = await self.client.reason_json(
                user_prompt=prompt,
                system_prompt=COMPETITION_ANALYSIS_SYSTEM_PROMPT
            )

            data = result["data"]
            reasoning = result["reasoning_content"]

            # 분석 결과 파싱
            analysis = CompetitionAnalysis(
                keyword=kw,
                competition_level=data.get("competition_level", "medium"),
                avg_word_count=data.get("avg_word_count", 2000),
                blog_exposure_count=len(top_blogs),
                search_intent=data.get("search_intent", "informational"),
                content_gaps=data.get("content_gaps", []),
                seo_recommendations=data.get("seo_recommendations", []),
                title_suggestions=data.get("title_suggestions", []),
                reasoning=reasoning
            )

            logger.info(
                f"Competition analysis for '{kw}': "
                f"level={analysis.competition_level}, "
                f"intent={analysis.search_intent}"
            )

            return analysis

        except Exception as e:
            logger.error(f"Competition analysis failed for '{kw}': {e}")
            return self._empty_analysis(kw)

    def _empty_analysis(self, keyword: str) -> CompetitionAnalysis:
        """빈 분석 결과 생성"""
        return CompetitionAnalysis(
            keyword=keyword,
            competition_level="unknown",
            avg_word_count=2000,
            blog_exposure_count=0,
            search_intent="informational",
            content_gaps=[],
            seo_recommendations=[],
            title_suggestions=[],
            reasoning=""
        )

    def to_dict(self, analysis: CompetitionAnalysis) -> Dict:
        """분석 결과를 딕셔너리로 변환 (JSON 저장용)"""
        return {
            "keyword": analysis.keyword,
            "competition_level": analysis.competition_level,
            "avg_word_count": analysis.avg_word_count,
            "blog_exposure_count": analysis.blog_exposure_count,
            "search_intent": analysis.search_intent,
            "content_gaps": analysis.content_gaps,
            "seo_recommendations": analysis.seo_recommendations,
            "title_suggestions": analysis.title_suggestions,
            "reasoning_summary": analysis.reasoning[:500] if analysis.reasoning else ""
        }
