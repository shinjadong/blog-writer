"""
Blog Writer FastAPI 서버

엔드포인트:
- POST /articles/generate - 원고 생성
- GET /articles - 원고 목록
- GET /articles/{id} - 원고 상세
- POST /publish/{article_id} - 네이버 발행
- POST /pipeline/execute - 전체 파이프라인 실행
- GET /health - 헬스체크

Author: CareOn Blog Writer
Created: 2026-01-10
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.core.config import get_settings
from src.api.routes import articles, publish, pipeline, archive

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("blog_writer.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 이벤트"""
    logger.info("Blog Writer API starting...")
    yield
    logger.info("Blog Writer API shutting down...")


# FastAPI 앱 생성
app = FastAPI(
    title="Blog Writer API",
    description="CareOn 블로그 원고 생성 및 발행 자동화 API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인만 허용
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 라우터 등록
app.include_router(articles.router, prefix="/articles", tags=["Articles"])
app.include_router(publish.router, prefix="/publish", tags=["Publish"])
app.include_router(pipeline.router, prefix="/pipeline", tags=["Pipeline"])
app.include_router(archive.router, prefix="/archive", tags=["Archive"])


@app.get("/")
async def root():
    """루트 엔드포인트"""
    settings = get_settings()
    return {
        "service": "Blog Writer API",
        "version": "1.0.0",
        "status": "running",
        "port": settings.api_port
    }


@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "service": "blog-writer"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """전역 예외 핸들러"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": str(exc),
            "message": "Internal server error"
        }
    )
