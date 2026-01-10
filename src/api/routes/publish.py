"""
네이버 발행 API

엔드포인트:
- POST /publish/{article_id} - 네이버 발행
- POST /publish/test-connection - 연결 테스트
"""

import logging
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.shared.supabase_client import SupabaseClient
from src.publisher.naver_publisher import NaverPublisher, PublishConfig, PublishResult

logger = logging.getLogger("blog_writer.api.publish")
router = APIRouter()


# ========== 요청/응답 모델 ==========

class PublishRequest(BaseModel):
    """발행 요청"""
    blog_id: str = Field(..., description="네이버 블로그 ID")
    category: Optional[str] = Field(None, description="카테고리 이름")
    tags: List[str] = Field(default_factory=list, description="태그 목록")
    chrome_user_data_dir: Optional[str] = Field(None, description="Chrome 유저 데이터 경로")
    headless: bool = Field(True, description="headless 모드")


class PublishResponse(BaseModel):
    """발행 응답"""
    success: bool
    article_id: str = ""
    blog_url: Optional[str] = None
    post_id: Optional[str] = None
    error_message: Optional[str] = None
    screenshots: List[str] = []


class ConnectionTestRequest(BaseModel):
    """연결 테스트 요청"""
    blog_id: str
    chrome_user_data_dir: Optional[str] = None


class ConnectionTestResponse(BaseModel):
    """연결 테스트 응답"""
    success: bool
    message: str


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
    win_path = home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    if win_path.exists():
        return str(win_path)
    return str(linux_path)


# ========== 백그라운드 작업 ==========

async def publish_article_task(
    article_id: str,
    title: str,
    content: str,
    config: PublishConfig,
    supabase: SupabaseClient
):
    """백그라운드 발행 작업"""
    try:
        publisher = NaverPublisher()
        result = await publisher.publish(title, content, config)

        # 발행 로그 저장
        supabase.create_publish_log_simple(
            article_id=article_id,
            blog_id=config.blog_id,
            success=result.success,
            blog_url=result.blog_url,
            error_message=result.error_message
        )

        # 원고 상태 업데이트
        if result.success:
            supabase.update_article(article_id, {
                "status": "published",
                "blog_url": result.blog_url,
                "blog_post_id": result.post_id,
                "published_at": datetime.now().isoformat()
            })

        logger.info(f"Publish task completed: {article_id} - success={result.success}")

    except Exception as e:
        logger.error(f"Background publish failed: {e}")

        # 에러 로그 저장
        supabase.create_publish_log_simple(
            article_id=article_id,
            blog_id=config.blog_id,
            success=False,
            error_message=str(e)
        )


# ========== 엔드포인트 ==========

@router.post("/{article_id}", response_model=PublishResponse)
async def publish_article(
    article_id: str,
    request: PublishRequest,
    background_tasks: BackgroundTasks,
    background: bool = Query(False, description="백그라운드 실행")
):
    """
    원고를 네이버 블로그에 발행

    Chrome 유저 데이터를 사용하여 로그인된 상태로 발행합니다.
    """
    settings = get_settings()

    try:
        # Supabase에서 원고 조회
        supabase = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_service_key
        )

        article = supabase.get_article(article_id)
        if not article:
            raise HTTPException(status_code=404, detail="Article not found")

        # Chrome 유저 데이터 경로
        chrome_path = request.chrome_user_data_dir or get_default_chrome_user_data()

        # 발행 설정
        config = PublishConfig(
            blog_id=request.blog_id,
            category=request.category or "",
            tags=request.tags or article.tags[:10] if article.tags else [],
            chrome_user_data_dir=chrome_path,
            headless=request.headless,
            slow_mo=150,
            screenshot_on_error=True
        )

        if background:
            # 백그라운드 실행
            background_tasks.add_task(
                publish_article_task,
                article_id,
                article.title,
                article.content,
                config,
                supabase
            )
            return PublishResponse(
                success=True,
                article_id=article_id,
                error_message="백그라운드에서 발행 중..."
            )

        # 동기 발행
        publisher = NaverPublisher()
        result = await publisher.publish(
            title=article.title,
            content=article.content,
            config=config
        )

        # 발행 로그 저장
        supabase.create_publish_log_simple(
            article_id=article_id,
            blog_id=request.blog_id,
            success=result.success,
            blog_url=result.blog_url,
            error_message=result.error_message
        )

        # 원고 상태 업데이트
        if result.success:
            supabase.update_article(article_id, {
                "status": "published",
                "blog_url": result.blog_url,
                "blog_post_id": result.post_id,
                "published_at": datetime.now().isoformat()
            })

        return PublishResponse(
            success=result.success,
            article_id=article_id,
            blog_url=result.blog_url,
            post_id=result.post_id,
            error_message=result.error_message,
            screenshots=result.screenshots
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Publish failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test-connection", response_model=ConnectionTestResponse)
async def test_connection(request: ConnectionTestRequest):
    """
    네이버 블로그 연결 테스트

    Chrome 유저 데이터로 로그인 상태를 확인합니다.
    """
    chrome_path = request.chrome_user_data_dir or get_default_chrome_user_data()

    config = PublishConfig(
        blog_id=request.blog_id,
        chrome_user_data_dir=chrome_path,
        headless=True
    )

    try:
        publisher = NaverPublisher()
        result = await publisher.test_connection(config)

        if result:
            return ConnectionTestResponse(
                success=True,
                message="연결 성공! 로그인 상태가 확인되었습니다."
            )
        else:
            return ConnectionTestResponse(
                success=False,
                message="로그인이 필요합니다. Chrome에서 네이버에 로그인 후 다시 시도하세요."
            )

    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return ConnectionTestResponse(
            success=False,
            message=f"연결 테스트 실패: {str(e)}"
        )
