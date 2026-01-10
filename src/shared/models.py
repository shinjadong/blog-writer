"""
Blog Writer 데이터 모델

원고, 키워드, 발행 관련 데이터 구조를 정의합니다.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class ArticleTemplate(str, Enum):
    """원고 템플릿 유형"""
    PERSONAL_STORY = "personal_story"      # 개인 경험 스토리
    EXPERT_REVIEW = "expert_review"        # 전문가 리뷰
    COMPARISON = "comparison"              # 비교 분석
    PROBLEM_SOLUTION = "problem_solution"  # 문제-해결 구조
    LISTICLE = "listicle"                  # 리스트형


class ContentTone(str, Enum):
    """콘텐츠 톤앤매너"""
    CASUAL = "casual"              # 친근한 톤
    PROFESSIONAL = "professional"  # 전문적 톤
    EMOTIONAL = "emotional"        # 감정적 톤
    INFORMATIVE = "informative"    # 정보 전달


class ArticleStatus(str, Enum):
    """원고 상태"""
    DRAFT = "draft"              # 초안
    REVIEWED = "reviewed"        # 검토됨
    APPROVED = "approved"        # 승인됨
    SCHEDULED = "scheduled"      # 예약됨
    PUBLISHED = "published"      # 발행됨
    ARCHIVED = "archived"        # 보관됨


class PublishStatus(str, Enum):
    """발행 상태"""
    PENDING = "pending"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    FAILED = "failed"


@dataclass
class ArticleConfig:
    """원고 생성 설정"""
    keyword: str
    template: ArticleTemplate = ArticleTemplate.PERSONAL_STORY
    tone: ContentTone = ContentTone.EMOTIONAL
    target_length: int = 3000  # 글자 수
    include_images: bool = True
    include_cta: bool = True
    cta_type: str = "consultation"  # consultation, landing_page, product
    target_audience: str = "소상공인"  # 소상공인, 가정, 기업

    # SEO 설정
    meta_description_length: int = 150
    include_internal_links: bool = True

    # 도메인 설정
    domain: str = "cctv"  # cctv, security, rental


@dataclass
class Article:
    """생성된 원고"""
    id: str
    keyword: str
    title: str
    content: str  # HTML 또는 마크다운
    meta_description: str = ""
    tags: List[str] = field(default_factory=list)

    # 구조
    sections: List[Dict[str, str]] = field(default_factory=list)

    # 설정
    template: str = "personal_story"
    tone: str = "emotional"
    domain: str = "cctv"

    # 품질 점수
    quality_score: float = 0.0
    seo_score: float = 0.0
    readability_score: float = 0.0
    word_count: int = 0

    # 상태
    status: str = "draft"

    # 발행 정보
    blog_url: Optional[str] = None
    blog_post_id: Optional[str] = None
    published_at: Optional[datetime] = None

    # 캠페인 연동
    campaign_id: Optional[str] = None

    # 타임스탬프
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # 메타데이터
    generation_config: Dict[str, Any] = field(default_factory=dict)
    ai_model: str = "deepseek-chat"
    generation_tokens: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        return {
            "id": self.id,
            "keyword": self.keyword,
            "title": self.title,
            "content": self.content,
            "meta_description": self.meta_description,
            "tags": self.tags,
            "sections": self.sections,
            "template": self.template,
            "tone": self.tone,
            "domain": self.domain,
            "quality_score": self.quality_score,
            "seo_score": self.seo_score,
            "readability_score": self.readability_score,
            "word_count": self.word_count,
            "status": self.status,
            "blog_url": self.blog_url,
            "blog_post_id": self.blog_post_id,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "campaign_id": self.campaign_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "generation_config": self.generation_config,
            "ai_model": self.ai_model,
            "generation_tokens": self.generation_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Article":
        """딕셔너리에서 생성"""
        return cls(
            id=data.get("id", ""),
            keyword=data.get("keyword", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            meta_description=data.get("meta_description", ""),
            tags=data.get("tags", []),
            sections=data.get("sections", []),
            template=data.get("template", "personal_story"),
            tone=data.get("tone", "emotional"),
            domain=data.get("domain", "cctv"),
            quality_score=data.get("quality_score", 0.0),
            seo_score=data.get("seo_score", 0.0),
            readability_score=data.get("readability_score", 0.0),
            word_count=data.get("word_count", 0),
            status=data.get("status", "draft"),
            blog_url=data.get("blog_url"),
            blog_post_id=data.get("blog_post_id"),
            published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None,
            campaign_id=data.get("campaign_id"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            updated_at=datetime.fromisoformat(data["updated_at"]) if data.get("updated_at") else None,
            generation_config=data.get("generation_config", {}),
            ai_model=data.get("ai_model", "deepseek-chat"),
            generation_tokens=data.get("generation_tokens", 0),
        )


@dataclass
class Keyword:
    """키워드"""
    id: str
    keyword: str
    domain: str = "cctv"
    category: Optional[str] = None

    # 검색량/경쟁도
    search_volume: Optional[int] = None
    competition_level: Optional[str] = None  # low, medium, high

    # 사용 현황
    articles_count: int = 0
    last_used_at: Optional[datetime] = None

    # 상태
    is_active: bool = True
    priority: int = 0

    created_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "keyword": self.keyword,
            "domain": self.domain,
            "category": self.category,
            "search_volume": self.search_volume,
            "competition_level": self.competition_level,
            "articles_count": self.articles_count,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


@dataclass
class PublishConfig:
    """발행 설정"""
    blog_id: str  # 네이버 블로그 ID
    category: str = ""  # 카테고리
    is_public: bool = True
    allow_comments: bool = True
    allow_sympathies: bool = True  # 공감 허용
    tags: List[str] = field(default_factory=list)

    # Chrome 유저 데이터
    chrome_user_data_dir: Optional[str] = None

    # 자동화 설정
    schedule_publish: bool = False
    publish_at: Optional[datetime] = None

    # 재시도 설정
    max_retries: int = 3
    retry_delay_sec: int = 60


@dataclass
class PublishLog:
    """발행 로그"""
    id: str
    article_id: str
    blog_id: str
    status: str  # pending, publishing, published, failed
    success: bool = False
    blog_url: Optional[str] = None
    error_message: Optional[str] = None
    screenshots: List[str] = field(default_factory=list)
    logs: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    publish_config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "article_id": self.article_id,
            "blog_id": self.blog_id,
            "status": self.status,
            "success": self.success,
            "blog_url": self.blog_url,
            "error_message": self.error_message,
            "screenshots": self.screenshots,
            "logs": self.logs,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "publish_config": self.publish_config,
        }


@dataclass
class GenerationOutline:
    """원고 아웃라인"""
    keyword: str
    title: str
    hook: str  # 도입부 훅
    sections: List[Dict[str, str]]  # {"title": "...", "purpose": "...", "key_points": [...]}
    cta: str  # Call to Action
    estimated_length: int
    target_keywords: List[str]  # SEO용 타겟 키워드

    def to_dict(self) -> Dict[str, Any]:
        return {
            "keyword": self.keyword,
            "title": self.title,
            "hook": self.hook,
            "sections": self.sections,
            "cta": self.cta,
            "estimated_length": self.estimated_length,
            "target_keywords": self.target_keywords,
        }
