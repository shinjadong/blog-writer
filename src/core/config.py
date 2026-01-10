"""
Blog Writer 설정 관리

환경 변수를 로드하고 설정값을 관리합니다.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """애플리케이션 설정"""

    # DeepSeek API
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # Supabase
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""

    # Naver Blog
    naver_blog_id: str = ""
    naver_cookies_path: str = "data/naver_cookies.json"

    # ai-project 연동
    ai_project_url: str = "http://localhost:8000"
    ai_project_api_key: str = ""

    # FastAPI
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 5001
    fastapi_api_key: str = ""

    # 환경
    project_env: str = "development"
    log_level: str = "INFO"
    headless_browser: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()


# 전역 설정 인스턴스
settings = get_settings()
