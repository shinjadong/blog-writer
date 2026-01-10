"""
파이프라인 실행 API

엔드포인트:
- POST /pipeline/execute - 전체 파이프라인 실행 (생성 → 발행 → 트래픽)
"""

import logging
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.shared.models import ArticleConfig, ArticleTemplate, ContentTone
from src.shared.supabase_client import SupabaseClient
from src.content.generator import ContentGenerator
from src.publisher.naver_publisher import NaverPublisher, PublishConfig
from src.traffic.trigger import TrafficTrigger, TrafficTriggerConfig

logger = logging.getLogger("blog_writer.api.pipeline")
router = APIRouter()


# ========== 요청/응답 모델 ==========

class PipelineRequest(BaseModel):
    """파이프라인 실행 요청"""
    # 키워드
    keyword: str = Field(..., description="타겟 키워드")

    # 원고 생성 옵션
    template: str = Field("personal_story", description="템플릿 유형")
    tone: str = Field("emotional", description="톤앤매너")
    target_length: int = Field(2500, description="목표 글자수")
    target_audience: str = Field("소상공인", description="타겟 독자")

    # 발행 옵션 (없으면 발행 안 함)
    blog_id: Optional[str] = Field(None, description="네이버 블로그 ID")
    category: Optional[str] = Field(None, description="카테고리")
    chrome_user_data_dir: Optional[str] = Field(None, description="Chrome 유저 데이터 경로")
    headless: bool = Field(True, description="headless 모드")

    # 트래픽 옵션 (없으면 트래픽 안 함)
    campaign_id: Optional[str] = Field(None, description="캠페인 ID (트래픽 트리거용)")
    traffic_api_url: str = Field("http://localhost:8000", description="ai-project API URL")


class PipelineResponse(BaseModel):
    """파이프라인 실행 응답"""
    success: bool
    message: str = ""

    # 생성 결과
    article_id: Optional[str] = None
    title: Optional[str] = None
    word_count: int = 0
    quality_score: float = 0.0

    # 발행 결과
    published: bool = False
    blog_url: Optional[str] = None

    # 트래픽 결과
    traffic_triggered: bool = False
    traffic_execution_id: Optional[str] = None


class PipelineStepResult(BaseModel):
    """파이프라인 단계 결과"""
    step: str
    success: bool
    message: str = ""
    data: dict = {}


# ========== 헬퍼 함수 ==========

def get_default_chrome_user_data() -> str:
    """기본 Chrome 유저 데이터 경로"""
    home = Path.home()
    linux_path = home / ".config" / "google-chrome"
    if linux_path.exists():
        return str(linux_path)
    mac_path = home / "Library" / "Application Support" / "Google" / "Chrome"
    if mac_path.exists():
        return str(mac_path)
    return str(linux_path)


# ========== 백그라운드 작업 ==========

async def execute_pipeline_task(
    request: PipelineRequest,
    supabase: SupabaseClient
):
    """백그라운드 파이프라인 실행"""
    settings = get_settings()

    try:
        # STEP 1: 원고 생성
        logger.info(f"[Pipeline] Starting article generation: {request.keyword}")

        generator = ContentGenerator(
            deepseek_api_key=settings.deepseek_api_key,
            model=settings.deepseek_model
        )

        config = ArticleConfig(
            keyword=request.keyword,
            template=ArticleTemplate(request.template),
            tone=ContentTone(request.tone),
            target_length=request.target_length,
            target_audience=request.target_audience
        )

        article = await generator.generate(keyword=request.keyword, config=config)
        supabase.create_article(article)

        logger.info(f"[Pipeline] Article generated: {article.id}")

        # STEP 2: 발행
        if request.blog_id:
            logger.info(f"[Pipeline] Publishing to blog: {request.blog_id}")

            chrome_path = request.chrome_user_data_dir or get_default_chrome_user_data()

            publish_config = PublishConfig(
                blog_id=request.blog_id,
                category=request.category or "",
                tags=article.tags[:10] if article.tags else [],
                chrome_user_data_dir=chrome_path,
                headless=request.headless,
                slow_mo=150,
                screenshot_on_error=True
            )

            publisher = NaverPublisher()
            result = await publisher.publish(article.title, article.content, publish_config)

            # 발행 로그 저장
            supabase.create_publish_log_simple(
                article_id=article.id,
                blog_id=request.blog_id,
                success=result.success,
                blog_url=result.blog_url,
                error_message=result.error_message
            )

            if result.success:
                supabase.update_article(article.id, {
                    "status": "published",
                    "blog_url": result.blog_url,
                    "blog_post_id": result.post_id,
                    "published_at": datetime.now().isoformat()
                })

                logger.info(f"[Pipeline] Published: {result.blog_url}")

                # STEP 3: 트래픽 트리거
                if request.campaign_id and result.success:
                    logger.info(f"[Pipeline] Triggering traffic: {request.campaign_id}")

                    trigger_config = TrafficTriggerConfig(
                        api_base_url=request.traffic_api_url,
                        api_key="careon-traffic-engine-2026"
                    )
                    trigger = TrafficTrigger(config=trigger_config)

                    if await trigger.health_check():
                        traffic_result = await trigger.execute_ai(
                            campaign_id=request.campaign_id,
                            keyword=request.keyword,
                            blog_title=article.title,
                            blog_url=result.blog_url
                        )
                        logger.info(f"[Pipeline] Traffic triggered: {traffic_result.success}")
            else:
                logger.warning(f"[Pipeline] Publish failed: {result.error_message}")

        logger.info(f"[Pipeline] Completed: {request.keyword}")

    except Exception as e:
        logger.error(f"[Pipeline] Failed: {e}")


# ========== 엔드포인트 ==========

@router.post("/execute", response_model=PipelineResponse)
async def execute_pipeline(
    request: PipelineRequest,
    background_tasks: BackgroundTasks,
    background: bool = False
):
    """
    전체 파이프라인 실행

    키워드 → 원고 생성 → 네이버 발행 → 트래픽 트리거
    """
    settings = get_settings()

    supabase = SupabaseClient(
        url=settings.supabase_url,
        key=settings.supabase_service_key
    )

    if background:
        # 백그라운드 실행
        background_tasks.add_task(execute_pipeline_task, request, supabase)
        return PipelineResponse(
            success=True,
            message="백그라운드에서 파이프라인 실행 중..."
        )

    try:
        # STEP 1: 원고 생성
        logger.info(f"Starting pipeline for keyword: {request.keyword}")

        generator = ContentGenerator(
            deepseek_api_key=settings.deepseek_api_key,
            model=settings.deepseek_model
        )

        config = ArticleConfig(
            keyword=request.keyword,
            template=ArticleTemplate(request.template),
            tone=ContentTone(request.tone),
            target_length=request.target_length,
            target_audience=request.target_audience
        )

        article = await generator.generate(keyword=request.keyword, config=config)
        supabase.create_article(article)

        response = PipelineResponse(
            success=True,
            article_id=article.id,
            title=article.title,
            word_count=article.word_count,
            quality_score=article.quality_score,
            message="원고 생성 완료"
        )

        # STEP 2: 발행
        if request.blog_id:
            chrome_path = request.chrome_user_data_dir or get_default_chrome_user_data()

            publish_config = PublishConfig(
                blog_id=request.blog_id,
                category=request.category or "",
                tags=article.tags[:10] if article.tags else [],
                chrome_user_data_dir=chrome_path,
                headless=request.headless,
                slow_mo=150,
                screenshot_on_error=True
            )

            publisher = NaverPublisher()
            result = await publisher.publish(article.title, article.content, publish_config)

            supabase.create_publish_log_simple(
                article_id=article.id,
                blog_id=request.blog_id,
                success=result.success,
                blog_url=result.blog_url,
                error_message=result.error_message
            )

            if result.success:
                supabase.update_article(article.id, {
                    "status": "published",
                    "blog_url": result.blog_url,
                    "blog_post_id": result.post_id,
                    "published_at": datetime.now().isoformat()
                })

                response.published = True
                response.blog_url = result.blog_url
                response.message = "발행 완료"

                # STEP 3: 트래픽 트리거
                if request.campaign_id:
                    trigger_config = TrafficTriggerConfig(
                        api_base_url=request.traffic_api_url,
                        api_key="careon-traffic-engine-2026"
                    )
                    trigger = TrafficTrigger(config=trigger_config)

                    if await trigger.health_check():
                        traffic_result = await trigger.execute_ai(
                            campaign_id=request.campaign_id,
                            keyword=request.keyword,
                            blog_title=article.title,
                            blog_url=result.blog_url
                        )

                        response.traffic_triggered = traffic_result.success
                        response.traffic_execution_id = traffic_result.execution_id
                        if traffic_result.success:
                            response.message = "전체 파이프라인 완료"
            else:
                response.message = f"발행 실패: {result.error_message}"

        return response

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
