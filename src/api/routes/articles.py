"""
원고 관리 API

엔드포인트:
- POST /articles/generate - 원고 생성
- GET /articles - 원고 목록
- GET /articles/{id} - 원고 상세
- PATCH /articles/{id} - 원고 수정
- DELETE /articles/{id} - 원고 삭제
"""

import logging
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.shared.models import ArticleConfig, ArticleTemplate, ContentTone
from src.shared.supabase_client import SupabaseClient
from src.content.generator import ContentGenerator

logger = logging.getLogger("blog_writer.api.articles")
router = APIRouter()


# ========== 요청/응답 모델 ==========

class GenerateRequest(BaseModel):
    """원고 생성 요청"""
    keyword: str = Field(..., description="타겟 키워드")
    template: str = Field("personal_story", description="템플릿 유형")
    tone: str = Field("emotional", description="톤앤매너")
    target_length: int = Field(2500, description="목표 글자수")
    target_audience: str = Field("소상공인", description="타겟 독자")


class GenerateResponse(BaseModel):
    """원고 생성 응답"""
    success: bool
    article_id: Optional[str] = None
    title: Optional[str] = None
    keyword: str = ""
    word_count: int = 0
    quality_score: float = 0.0
    message: str = ""


class ArticleItem(BaseModel):
    """원고 목록 아이템"""
    id: str
    keyword: str
    title: str
    status: str
    word_count: int
    quality_score: float
    created_at: str


class ArticleDetail(BaseModel):
    """원고 상세"""
    id: str
    keyword: str
    title: str
    content: str
    meta_description: Optional[str] = None
    tags: List[str] = []
    status: str
    template: str
    tone: str
    word_count: int
    quality_score: float
    seo_score: float
    readability_score: float
    blog_url: Optional[str] = None
    published_at: Optional[str] = None
    created_at: str


class UpdateArticleRequest(BaseModel):
    """원고 수정 요청"""
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


# ========== 백그라운드 작업 ==========

async def generate_article_task(
    keyword: str,
    config: ArticleConfig,
    supabase: SupabaseClient
):
    """백그라운드 원고 생성"""
    settings = get_settings()

    try:
        generator = ContentGenerator(
            deepseek_api_key=settings.deepseek_api_key,
            model=settings.deepseek_model
        )

        article = await generator.generate(keyword=keyword, config=config)

        # Supabase에 저장
        supabase.create_article(article)

        logger.info(f"Article generated and saved: {article.id}")

    except Exception as e:
        logger.error(f"Background article generation failed: {e}")


# ========== 엔드포인트 ==========

@router.post("/generate", response_model=GenerateResponse)
async def generate_article(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    background: bool = Query(False, description="백그라운드 실행 여부")
):
    """
    원고 생성

    키워드를 기반으로 블로그 원고를 생성합니다.
    """
    settings = get_settings()

    config = ArticleConfig(
        keyword=request.keyword,
        template=ArticleTemplate(request.template),
        tone=ContentTone(request.tone),
        target_length=request.target_length,
        target_audience=request.target_audience
    )

    if background:
        # 백그라운드 실행
        supabase = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_service_key
        )
        background_tasks.add_task(
            generate_article_task,
            request.keyword,
            config,
            supabase
        )
        return GenerateResponse(
            success=True,
            keyword=request.keyword,
            message="백그라운드에서 원고 생성 중..."
        )

    try:
        generator = ContentGenerator(
            deepseek_api_key=settings.deepseek_api_key,
            model=settings.deepseek_model
        )

        article = await generator.generate(keyword=request.keyword, config=config)

        # Supabase에 저장
        supabase = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_service_key
        )
        supabase.create_article(article)

        return GenerateResponse(
            success=True,
            article_id=article.id,
            title=article.title,
            keyword=article.keyword,
            word_count=article.word_count,
            quality_score=article.quality_score,
            message="원고 생성 완료"
        )

    except Exception as e:
        logger.error(f"Article generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ArticleItem])
async def list_articles(
    status: Optional[str] = Query(None, description="상태 필터"),
    keyword: Optional[str] = Query(None, description="키워드 검색"),
    limit: int = Query(20, ge=1, le=100, description="최대 조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋")
):
    """
    원고 목록 조회
    """
    settings = get_settings()

    try:
        supabase = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_service_key
        )

        articles = await supabase.get_articles(
            status=status,
            keyword=keyword,
            limit=limit,
            offset=offset
        )

        return [
            ArticleItem(
                id=a.id,
                keyword=a.keyword,
                title=a.title,
                status=a.status,
                word_count=a.word_count,
                quality_score=a.quality_score,
                created_at=a.created_at.isoformat() if a.created_at else ""
            )
            for a in articles
        ]

    except Exception as e:
        logger.error(f"Failed to list articles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{article_id}", response_model=ArticleDetail)
async def get_article(article_id: str):
    """
    원고 상세 조회
    """
    settings = get_settings()

    try:
        supabase = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_service_key
        )

        article = supabase.get_article(article_id)

        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        return ArticleDetail(
            id=article.id,
            keyword=article.keyword,
            title=article.title,
            content=article.content,
            meta_description=article.meta_description,
            tags=article.tags or [],
            status=article.status,
            template=article.template,
            tone=article.tone,
            word_count=article.word_count,
            quality_score=article.quality_score,
            seo_score=article.seo_score,
            readability_score=article.readability_score,
            blog_url=article.blog_url,
            published_at=article.published_at.isoformat() if article.published_at else None,
            created_at=article.created_at.isoformat() if article.created_at else ""
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get article: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{article_id}")
async def update_article(article_id: str, request: UpdateArticleRequest):
    """
    원고 수정
    """
    settings = get_settings()

    try:
        supabase = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_service_key
        )

        update_data = {k: v for k, v in request.dict().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        result = supabase.update_article(article_id, update_data)

        if not result:
            raise HTTPException(status_code=404, detail="Article not found")

        return {"success": True, "message": "원고가 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update article: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{article_id}")
async def delete_article(article_id: str):
    """
    원고 삭제
    """
    settings = get_settings()

    try:
        supabase = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_service_key
        )

        success = supabase.delete_article(article_id)

        if not success:
            raise HTTPException(status_code=404, detail="Article not found")

        return {"success": True, "message": "원고가 삭제되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete article: {e}")
        raise HTTPException(status_code=500, detail=str(e))
