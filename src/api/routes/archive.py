"""
아카이브 관리 API

엔드포인트:
- POST /archive/import - 텍스트 파일 임포트
- GET /archive - 아카이브 목록
- GET /archive/stats - 아카이브 통계
- GET /archive/{id} - 아카이브 상세
- PATCH /archive/{id} - 아카이브 수정
"""

import logging
import uuid
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Query, UploadFile, File
from pydantic import BaseModel, Field

from src.core.config import get_settings
from src.shared.supabase_client import SupabaseClient
from src.archive.parser import BlogArchiveParser
from src.archive.classifier import PostClassifier

logger = logging.getLogger("blog_writer.api.archive")
router = APIRouter()


# ========== 요청/응답 모델 ==========


class ImportRequest(BaseModel):
    """임포트 요청 (파일 경로 지정)"""
    file_path: str = Field(..., description="텍스트 파일 경로")
    source_file: str = Field("blog-cctv.txt", description="소스 파일명")
    dry_run: bool = Field(False, description="파싱만 실행 (DB 저장 안 함)")


class ImportResponse(BaseModel):
    """임포트 응답"""
    success: bool
    batch_id: str = ""
    total_parsed: int = 0
    total_saved: int = 0
    stats: dict = {}
    distribution: dict = {}
    message: str = ""


class ArchiveItem(BaseModel):
    """아카이브 목록 아이템"""
    id: str
    original_title: str
    category: str
    primary_keyword: Optional[str] = None
    word_count: int
    view_count: int
    original_date: Optional[str] = None
    has_seo_memo: bool
    migration_status: str
    tags: List[str] = []


class ArchiveDetail(BaseModel):
    """아카이브 상세"""
    id: str
    original_title: str
    original_content: str
    seo_memo: Optional[str] = None
    clean_content: str
    photo_count: int
    original_date: Optional[str] = None
    view_count: int
    category: str
    tags: List[str] = []
    primary_keyword: Optional[str] = None
    word_count: int
    has_seo_memo: bool
    migration_status: str
    source_file: str
    parse_order: Optional[int] = None
    created_at: Optional[str] = None


class UpdateArchiveRequest(BaseModel):
    """아카이브 수정 요청"""
    category: Optional[str] = None
    primary_keyword: Optional[str] = None
    tags: Optional[List[str]] = None
    migration_status: Optional[str] = None


class ArchiveStatsResponse(BaseModel):
    """아카이브 통계 응답"""
    total: int
    by_category: dict = {}
    by_migration_status: dict = {}


# ========== 엔드포인트 ==========


@router.post("/import", response_model=ImportResponse)
async def import_archive(request: ImportRequest):
    """
    텍스트 파일에서 블로그 아카이브 임포트

    파싱 → 분류 → DB 저장
    """
    try:
        # 파싱
        archive_parser = BlogArchiveParser(source_file=request.source_file)
        posts = archive_parser.parse_file(request.file_path)

        # 분류
        classifier = PostClassifier()
        posts = classifier.classify_batch(posts)

        # 배치 ID
        batch_id = str(uuid.uuid4())[:8]
        for post in posts:
            post.import_batch_id = batch_id

        # 통계
        stats = archive_parser.get_stats(posts)
        distribution = classifier.get_distribution(posts)

        if request.dry_run:
            return ImportResponse(
                success=True,
                batch_id=batch_id,
                total_parsed=len(posts),
                total_saved=0,
                stats=stats,
                distribution=distribution,
                message="dry-run 완료 (DB 저장 안 함)",
            )

        # DB 저장
        settings = get_settings()
        db = SupabaseClient(
            url=settings.supabase_url, key=settings.supabase_service_key
        )
        saved = db.bulk_create_archives(posts)

        return ImportResponse(
            success=True,
            batch_id=batch_id,
            total_parsed=len(posts),
            total_saved=saved,
            stats=stats,
            distribution=distribution,
            message=f"{saved}개 포스트 임포트 완료",
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Archive import failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[ArchiveItem])
async def list_archives(
    category: Optional[str] = Query(None, description="카테고리 필터"),
    migration_status: Optional[str] = Query(None, description="마이그레이션 상태"),
    limit: int = Query(20, ge=1, le=100, description="최대 조회 개수"),
    offset: int = Query(0, ge=0, description="오프셋"),
):
    """아카이브 목록 조회"""
    settings = get_settings()

    try:
        db = SupabaseClient(
            url=settings.supabase_url, key=settings.supabase_service_key
        )

        archives = db.list_archives(
            category=category,
            migration_status=migration_status,
            limit=limit,
            offset=offset,
        )

        return [
            ArchiveItem(
                id=a.id,
                original_title=a.original_title,
                category=a.category,
                primary_keyword=a.primary_keyword,
                word_count=a.word_count,
                view_count=a.view_count,
                original_date=a.original_date.isoformat() if a.original_date else None,
                has_seo_memo=a.has_seo_memo,
                migration_status=a.migration_status,
                tags=a.tags or [],
            )
            for a in archives
        ]

    except Exception as e:
        logger.error(f"Failed to list archives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=ArchiveStatsResponse)
async def get_archive_stats():
    """아카이브 통계"""
    settings = get_settings()

    try:
        db = SupabaseClient(
            url=settings.supabase_url, key=settings.supabase_service_key
        )
        stats = db.get_archive_stats()
        return ArchiveStatsResponse(**stats)

    except Exception as e:
        logger.error(f"Failed to get archive stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{archive_id}", response_model=ArchiveDetail)
async def get_archive(archive_id: str):
    """아카이브 상세 조회"""
    settings = get_settings()

    try:
        db = SupabaseClient(
            url=settings.supabase_url, key=settings.supabase_service_key
        )

        archive = db.get_archive(archive_id)
        if not archive:
            raise HTTPException(status_code=404, detail="Archive not found")

        return ArchiveDetail(
            id=archive.id,
            original_title=archive.original_title,
            original_content=archive.original_content,
            seo_memo=archive.seo_memo,
            clean_content=archive.clean_content,
            photo_count=archive.photo_count,
            original_date=archive.original_date.isoformat()
            if archive.original_date
            else None,
            view_count=archive.view_count,
            category=archive.category,
            tags=archive.tags or [],
            primary_keyword=archive.primary_keyword,
            word_count=archive.word_count,
            has_seo_memo=archive.has_seo_memo,
            migration_status=archive.migration_status,
            source_file=archive.source_file,
            parse_order=archive.parse_order,
            created_at=archive.created_at.isoformat()
            if archive.created_at
            else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get archive: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{archive_id}")
async def update_archive(archive_id: str, request: UpdateArchiveRequest):
    """아카이브 수정 (카테고리, 태그, 마이그레이션 상태 등)"""
    settings = get_settings()

    try:
        db = SupabaseClient(
            url=settings.supabase_url, key=settings.supabase_service_key
        )

        update_data = {k: v for k, v in request.model_dump().items() if v is not None}

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        result = db.update_archive(archive_id, update_data)

        if not result:
            raise HTTPException(status_code=404, detail="Archive not found")

        return {"success": True, "message": "아카이브가 수정되었습니다."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update archive: {e}")
        raise HTTPException(status_code=500, detail=str(e))
