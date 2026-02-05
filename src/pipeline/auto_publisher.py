"""
자동 발행 파이프라인

CSV 키워드 → 네이버 검색 → 경쟁 분석 → SEO 원고 생성 → 발행 → CSV 업데이트
"""

import csv
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum

from src.core.config import get_settings
from src.shared.deepseek_client import DeepSeekClient
from src.research.naver_search import NaverSearchClient
from src.research.competition_analyzer import CompetitionAnalyzer
from src.content.prompts.seo_prompts import (
    SEO_CONTENT_SYSTEM_PROMPT,
    OUTLINE_REASONING_SYSTEM_PROMPT,
    build_seo_content_prompt,
    build_outline_prompt,
    build_section_content_prompt,
)

logger = logging.getLogger("blog_writer.auto_publisher")


class ProcessingStatus(str, Enum):
    """키워드 처리 상태"""
    PENDING = "pending"
    SEARCHED = "searched"
    ANALYZED = "analyzed"
    GENERATED = "generated"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class KeywordEntry:
    """CSV 키워드 엔트리"""
    # 기본 키워드 정보
    keyword: str
    monthly_search_volume: int = 0
    keyword_type: str = ""
    # 검색/분석 결과
    search_date: str = ""
    competition_level: str = ""
    blog_exposure_count: int = 0
    avg_word_count: int = 0
    search_intent: str = ""
    # 원고 데이터
    title: str = ""
    meta_description: str = ""
    tags: str = ""
    quality_score: float = 0.0
    seo_score: float = 0.0
    word_count: int = 0
    created_at: str = ""
    # 상태 관리
    status: str = ProcessingStatus.PENDING.value
    article_id: str = ""
    publish_url: str = ""

    @classmethod
    def from_dict(cls, data: Dict) -> "KeywordEntry":
        # tags: 리스트 → 쉼표 구분 문자열 변환
        tags_raw = data.get("태그", data.get("tags", ""))
        if isinstance(tags_raw, list):
            tags_raw = ", ".join(tags_raw)

        return cls(
            keyword=data.get("키워드", data.get("keyword", "")),
            monthly_search_volume=int(data.get("월간검색수(모바일)", data.get("monthly_search_volume", 0)) or 0),
            keyword_type=data.get("타입", data.get("keyword_type", "")),
            search_date=data.get("검색일자", data.get("search_date", "")),
            competition_level=data.get("경쟁도", data.get("competition_level", "")),
            blog_exposure_count=int(data.get("블로그노출수", data.get("blog_exposure_count", 0)) or 0),
            avg_word_count=int(data.get("평균글자수", data.get("avg_word_count", 0)) or 0),
            search_intent=data.get("검색의도", data.get("search_intent", "")),
            title=data.get("제목", data.get("title", "")),
            meta_description=data.get("메타설명", data.get("meta_description", "")),
            tags=tags_raw,
            quality_score=float(data.get("품질점수", data.get("quality_score", 0)) or 0),
            seo_score=float(data.get("SEO점수", data.get("seo_score", 0)) or 0),
            word_count=int(data.get("글자수", data.get("word_count", 0)) or 0),
            created_at=data.get("생성일시", data.get("created_at", "")),
            status=data.get("처리상태", data.get("status", ProcessingStatus.PENDING.value)),
            article_id=data.get("원고ID", data.get("article_id", "")),
            publish_url=data.get("발행URL", data.get("publish_url", ""))
        )

    def to_dict(self) -> Dict:
        return {
            "키워드": self.keyword,
            "월간검색수(모바일)": self.monthly_search_volume,
            "타입": self.keyword_type,
            "검색일자": self.search_date,
            "경쟁도": self.competition_level,
            "블로그노출수": self.blog_exposure_count,
            "평균글자수": self.avg_word_count,
            "검색의도": self.search_intent,
            "제목": self.title,
            "메타설명": self.meta_description,
            "태그": self.tags,
            "품질점수": self.quality_score,
            "SEO점수": self.seo_score,
            "글자수": self.word_count,
            "생성일시": self.created_at,
            "처리상태": self.status,
            "원고ID": self.article_id,
            "발행URL": self.publish_url
        }


@dataclass
class GeneratedArticle:
    """생성된 원고"""
    keyword: str
    title: str
    content: str
    meta_description: str
    tags: List[str]
    quality_score: float
    seo_score: float
    word_count: int
    created_at: str
    outline: Dict = field(default_factory=dict)
    analysis: Dict = field(default_factory=dict)


class AutoPublisher:
    """
    자동 발행 파이프라인

    사용 예시:
        publisher = AutoPublisher()
        await publisher.process_csv("data/keywords.csv")
    """

    def __init__(
        self,
        data_dir: str = "data",
        search_results_dir: str = "data/search_results",
        articles_dir: str = "data/generated_articles"
    ):
        settings = get_settings()

        self.data_dir = Path(data_dir)
        self.search_results_dir = Path(search_results_dir)
        self.articles_dir = Path(articles_dir)

        # 디렉토리 생성
        self.search_results_dir.mkdir(parents=True, exist_ok=True)
        self.articles_dir.mkdir(parents=True, exist_ok=True)

        # 클라이언트 초기화
        self.deepseek = DeepSeekClient(
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model
        )
        self.naver_search = NaverSearchClient(
            client_id=settings.naver_client_id,
            client_secret=settings.naver_client_secret
        )
        self.analyzer = CompetitionAnalyzer(self.deepseek)

    async def process_csv(
        self,
        csv_path: str,
        limit: int = None,
        skip_searched: bool = True,
        skip_generated: bool = True
    ) -> List[Dict]:
        """
        CSV 파일의 키워드를 처리

        Args:
            csv_path: CSV 파일 경로
            limit: 처리할 최대 키워드 수
            skip_searched: 이미 검색된 키워드 건너뛰기
            skip_generated: 이미 생성된 키워드 건너뛰기

        Returns:
            처리 결과 목록
        """
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")

        # CSV 읽기
        keywords = self._read_csv(csv_path)
        logger.info(f"Loaded {len(keywords)} keywords from {csv_path}")

        # 필터링
        pending_keywords = []
        for kw in keywords:
            if skip_generated and kw.status == ProcessingStatus.GENERATED.value:
                continue
            if skip_searched and kw.status == ProcessingStatus.SEARCHED.value:
                # 검색은 되었지만 생성은 안된 경우 생성만 수행
                pending_keywords.append(kw)
            elif kw.status == ProcessingStatus.PENDING.value:
                pending_keywords.append(kw)

        if limit:
            pending_keywords = pending_keywords[:limit]

        logger.info(f"Processing {len(pending_keywords)} keywords")

        results = []
        for i, kw in enumerate(pending_keywords):
            logger.info(f"[{i+1}/{len(pending_keywords)}] Processing: {kw.keyword}")

            try:
                result = await self.process_single_keyword(kw)
                results.append(result)

                # CSV 업데이트
                self._update_csv(csv_path, kw)

            except Exception as e:
                logger.error(f"Failed to process {kw.keyword}: {e}")
                kw.status = ProcessingStatus.FAILED.value
                self._update_csv(csv_path, kw)
                results.append({"keyword": kw.keyword, "status": "failed", "error": str(e)})

            # Rate limit 대응
            await asyncio.sleep(2)

        return results

    async def process_single_keyword(
        self,
        keyword_entry: KeywordEntry
    ) -> Dict[str, Any]:
        """
        단일 키워드 처리

        Args:
            keyword_entry: 키워드 엔트리

        Returns:
            처리 결과
        """
        keyword = keyword_entry.keyword
        result = {"keyword": keyword, "steps": []}

        # Phase 1: 네이버 검색
        if keyword_entry.status == ProcessingStatus.PENDING.value:
            logger.info(f"Phase 1: Searching for '{keyword}'")
            search_result = await self._search_keyword(keyword)
            keyword_entry.search_date = datetime.now().strftime("%Y-%m-%d")
            keyword_entry.blog_exposure_count = len(search_result.get("top_blogs", []))
            keyword_entry.status = ProcessingStatus.SEARCHED.value
            result["steps"].append("searched")

            # 검색 결과 저장
            self._save_search_result(keyword, search_result)
        else:
            # 기존 검색 결과 로드
            search_result = self._load_search_result(keyword)
            if not search_result:
                search_result = await self._search_keyword(keyword)
                self._save_search_result(keyword, search_result)

        # Phase 2: 경쟁 분석
        logger.info(f"Phase 2: Analyzing competition for '{keyword}'")
        analysis = await self.analyzer.analyze(search_result, keyword)
        analysis_dict = self.analyzer.to_dict(analysis)

        # 분석 결과 CSV 업데이트
        keyword_entry.competition_level = analysis.competition_level
        keyword_entry.avg_word_count = analysis.avg_word_count
        keyword_entry.search_intent = analysis.search_intent
        keyword_entry.status = ProcessingStatus.ANALYZED.value
        result["steps"].append("analyzed")

        # 검색 결과에 분석 추가 후 저장
        search_result["analysis"] = analysis_dict
        self._save_search_result(keyword, search_result)

        # Phase 3: SEO 원고 생성
        logger.info(f"Phase 3: Generating article for '{keyword}'")
        article = await self._generate_article(keyword, analysis_dict)
        keyword_entry.article_id = f"{keyword}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        keyword_entry.status = ProcessingStatus.GENERATED.value
        result["steps"].append("generated")

        # 원고 데이터 → CSV 열 채우기
        keyword_entry.title = article.title
        keyword_entry.meta_description = article.meta_description
        keyword_entry.tags = ", ".join(article.tags) if isinstance(article.tags, list) else article.tags
        keyword_entry.quality_score = round(article.quality_score, 2)
        keyword_entry.seo_score = round(article.seo_score, 2)
        keyword_entry.word_count = article.word_count
        keyword_entry.created_at = article.created_at

        # 원고 저장
        self._save_article(keyword, article)
        result["article_id"] = keyword_entry.article_id
        result["title"] = article.title
        result["word_count"] = article.word_count

        return result

    async def _search_keyword(self, keyword: str) -> Dict:
        """네이버 검색 수행"""
        return await self.naver_search.search_and_analyze(keyword, display=10)

    async def _generate_article(
        self,
        keyword: str,
        analysis: Dict
    ) -> GeneratedArticle:
        """SEO 최적화 원고 생성"""

        # 1. 아웃라인 생성 (Reasoner 사용)
        outline_prompt = build_outline_prompt(
            keyword=keyword,
            analysis=analysis,
            target_word_count=analysis.get("avg_word_count", 3000)
        )

        outline_result = await self.deepseek.reason_json(
            user_prompt=outline_prompt,
            system_prompt=OUTLINE_REASONING_SYSTEM_PROMPT
        )
        outline = outline_result.get("data", {})

        logger.info(f"Outline generated: {outline.get('title', 'No title')}")

        # 2. 섹션별 콘텐츠 생성 (Chat 모델 사용)
        sections = outline.get("sections", [])
        content_parts = []
        previous_sections = ""

        # 도입부 (Hook)
        hook = outline.get("hook", "")
        if hook:
            content_parts.append(hook)
            content_parts.append("")
            previous_sections = hook

        # 섹션별 생성
        for section in sections:
            section_prompt = build_section_content_prompt(
                keyword=keyword,
                section=section,
                previous_sections=previous_sections[:500],
                analysis=analysis
            )

            section_content = await self.deepseek.generate_blog_content(
                prompt=section_prompt,
                system_prompt=SEO_CONTENT_SYSTEM_PROMPT,
                temperature=0.8
            )

            content_parts.append(section_content)
            content_parts.append("")
            previous_sections = section_content

        # 3. CTA 추가
        cta = outline.get("cta", "")
        if cta:
            content_parts.append("---")
            content_parts.append("")
            content_parts.append(cta)

        # 4. 전체 콘텐츠 조합
        full_content = "\n".join(content_parts)

        # 5. 품질 점수 계산
        word_count = len(full_content.replace(" ", "").replace("\n", ""))
        quality_score = self._calculate_quality_score(full_content, keyword, analysis)
        seo_score = self._calculate_seo_score(full_content, keyword)

        return GeneratedArticle(
            keyword=keyword,
            title=outline.get("title", f"{keyword} 완벽 가이드"),
            content=full_content,
            meta_description=outline.get("meta_description", ""),
            tags=outline.get("tags", [keyword]),
            quality_score=quality_score,
            seo_score=seo_score,
            word_count=word_count,
            created_at=datetime.now().isoformat(),
            outline=outline,
            analysis=analysis
        )

    def _calculate_quality_score(
        self,
        content: str,
        keyword: str,
        analysis: Dict
    ) -> float:
        """품질 점수 계산"""
        score = 0.0

        # 길이 점수
        word_count = len(content.replace(" ", "").replace("\n", ""))
        target_length = analysis.get("avg_word_count", 3000)
        length_ratio = word_count / target_length if target_length > 0 else 0

        if 0.8 <= length_ratio <= 1.3:
            score += 0.3
        elif 0.6 <= length_ratio <= 1.5:
            score += 0.2

        # 구조 점수
        heading_count = content.count("## ")
        if 3 <= heading_count <= 8:
            score += 0.25
        elif heading_count > 0:
            score += 0.1

        # 키워드 포함 점수
        keyword_count = content.lower().count(keyword.lower())
        if 3 <= keyword_count <= 15:
            score += 0.25
        elif keyword_count > 0:
            score += 0.1

        # 이미지 위치 표시
        image_count = content.count("[이미지:")
        if image_count >= 3:
            score += 0.2

        return min(score, 1.0)

    def _calculate_seo_score(self, content: str, keyword: str) -> float:
        """SEO 점수 계산"""
        import re
        score = 0.0

        # 키워드 밀도
        word_count = len(content.replace(" ", ""))
        keyword_count = content.lower().count(keyword.lower())
        density = (keyword_count * len(keyword)) / word_count if word_count > 0 else 0

        if 0.01 <= density <= 0.04:
            score += 0.35

        # 제목/첫 문단에 키워드
        first_paragraph = content.split("\n\n")[0] if content else ""
        if keyword.lower() in first_paragraph.lower():
            score += 0.25

        # 소제목에 키워드
        headings = re.findall(r"## .+", content)
        keyword_in_heading = any(keyword.lower() in h.lower() for h in headings)
        if keyword_in_heading:
            score += 0.25

        # 마지막 문단에 키워드 (CTA)
        last_paragraph = content.split("\n\n")[-1] if content else ""
        if keyword.lower() in last_paragraph.lower():
            score += 0.15

        return min(score, 1.0)

    def _read_csv(self, csv_path: Path) -> List[KeywordEntry]:
        """CSV 파일 읽기"""
        keywords = []
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                keywords.append(KeywordEntry.from_dict(row))
        return keywords

    def _update_csv(self, csv_path: Path, updated_entry: KeywordEntry):
        """CSV 파일 업데이트"""
        # 전체 읽기
        keywords = self._read_csv(csv_path)

        # 업데이트
        for i, kw in enumerate(keywords):
            if kw.keyword == updated_entry.keyword:
                keywords[i] = updated_entry
                break

        # 전체 쓰기
        self._write_csv(csv_path, keywords)

    def _write_csv(self, csv_path: Path, keywords: List[KeywordEntry]):
        """CSV 파일 쓰기"""
        if not keywords:
            return

        fieldnames = list(keywords[0].to_dict().keys())
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for kw in keywords:
                writer.writerow(kw.to_dict())

    def _save_search_result(self, keyword: str, data: Dict):
        """검색 결과 저장"""
        safe_keyword = keyword.replace(" ", "_").replace("/", "_")
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{safe_keyword}_{date_str}.json"
        filepath = self.search_results_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Search result saved: {filepath}")

    def _load_search_result(self, keyword: str) -> Optional[Dict]:
        """검색 결과 로드 (가장 최근 파일)"""
        safe_keyword = keyword.replace(" ", "_").replace("/", "_")
        pattern = f"{safe_keyword}_*.json"
        files = list(self.search_results_dir.glob(pattern))

        if not files:
            return None

        # 가장 최근 파일
        latest_file = max(files, key=lambda f: f.stat().st_mtime)
        with open(latest_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_article(self, keyword: str, article: GeneratedArticle):
        """원고 저장"""
        safe_keyword = keyword.replace(" ", "_").replace("/", "_")
        filename = f"{safe_keyword}_article.json"
        filepath = self.articles_dir / filename

        data = {
            "keyword": article.keyword,
            "title": article.title,
            "content": article.content,
            "meta_description": article.meta_description,
            "tags": article.tags,
            "quality_score": article.quality_score,
            "seo_score": article.seo_score,
            "word_count": article.word_count,
            "created_at": article.created_at,
            "outline": article.outline,
            "analysis": article.analysis
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # 마크다운 파일도 저장
        md_filepath = self.articles_dir / f"{safe_keyword}_article.md"
        with open(md_filepath, "w", encoding="utf-8") as f:
            f.write(f"# {article.title}\n\n")
            f.write(article.content)

        logger.info(f"Article saved: {filepath}")

    def backfill_csv_from_json(self, csv_path: str) -> int:
        """
        기존 JSON 파일에서 CSV 열을 백필

        generated_articles/, search_results/ 디렉토리의 JSON을 읽어
        CSV의 빈 열을 채웁니다.

        Args:
            csv_path: CSV 파일 경로

        Returns:
            업데이트된 키워드 수
        """
        csv_path = Path(csv_path)
        keywords = self._read_csv(csv_path)
        updated_count = 0

        for kw in keywords:
            changed = False

            # 1. 원고 JSON에서 데이터 로드
            article_data = self._load_article_json(kw.keyword)
            if article_data:
                if not kw.title and article_data.get("title"):
                    kw.title = article_data["title"]
                    changed = True
                if not kw.meta_description and article_data.get("meta_description"):
                    kw.meta_description = article_data["meta_description"]
                    changed = True
                if not kw.tags and article_data.get("tags"):
                    tags = article_data["tags"]
                    kw.tags = ", ".join(tags) if isinstance(tags, list) else tags
                    changed = True
                if not kw.quality_score and article_data.get("quality_score"):
                    kw.quality_score = round(float(article_data["quality_score"]), 2)
                    changed = True
                if not kw.seo_score and article_data.get("seo_score"):
                    kw.seo_score = round(float(article_data["seo_score"]), 2)
                    changed = True
                if not kw.word_count and article_data.get("word_count"):
                    kw.word_count = int(article_data["word_count"])
                    changed = True
                if not kw.created_at and article_data.get("created_at"):
                    kw.created_at = article_data["created_at"]
                    changed = True
                if kw.status == ProcessingStatus.PENDING.value:
                    kw.status = ProcessingStatus.GENERATED.value
                    changed = True

            # 2. 검색 결과 JSON에서 분석 데이터 로드
            search_data = self._load_search_result(kw.keyword)
            if search_data:
                analysis = search_data.get("analysis", {})
                if not kw.search_date and search_data.get("search_date"):
                    kw.search_date = search_data["search_date"]
                    changed = True
                if not kw.blog_exposure_count and search_data.get("top_blogs"):
                    kw.blog_exposure_count = len(search_data["top_blogs"])
                    changed = True
                if analysis:
                    if not kw.competition_level and analysis.get("competition_level"):
                        kw.competition_level = analysis["competition_level"]
                        changed = True
                    if not kw.avg_word_count and analysis.get("avg_word_count"):
                        kw.avg_word_count = int(analysis["avg_word_count"])
                        changed = True
                    if not kw.search_intent and analysis.get("search_intent"):
                        kw.search_intent = analysis["search_intent"]
                        changed = True

            if changed:
                updated_count += 1
                logger.info(f"Backfilled: {kw.keyword}")

        # CSV 전체 쓰기
        self._write_csv(csv_path, keywords)
        logger.info(f"Backfill complete: {updated_count}/{len(keywords)} keywords updated")
        return updated_count

    def _load_article_json(self, keyword: str) -> Optional[Dict]:
        """원고 JSON 로드"""
        safe_keyword = keyword.replace(" ", "_").replace("/", "_")
        filepath = self.articles_dir / f"{safe_keyword}_article.json"
        if not filepath.exists():
            return None
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)

    async def process_single(self, keyword: str) -> Dict[str, Any]:
        """
        단일 키워드 직접 처리 (CSV 없이)

        Args:
            keyword: 처리할 키워드

        Returns:
            처리 결과
        """
        entry = KeywordEntry(keyword=keyword)
        return await self.process_single_keyword(entry)


# CLI 실행용
async def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.pipeline.auto_publisher <csv_path> [limit]")
        print("       python -m src.pipeline.auto_publisher --single <keyword>")
        sys.exit(1)

    publisher = AutoPublisher()

    if sys.argv[1] == "--single":
        if len(sys.argv) < 3:
            print("Error: keyword required")
            sys.exit(1)
        keyword = sys.argv[2]
        result = await publisher.process_single(keyword)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        csv_path = sys.argv[1]
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        results = await publisher.process_csv(csv_path, limit=limit)
        print(f"\nProcessed {len(results)} keywords")
        for r in results:
            print(f"  - {r.get('keyword')}: {r.get('steps', ['failed'])}")


if __name__ == "__main__":
    asyncio.run(main())
