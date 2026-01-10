"""
Supabase 클라이언트

원고, 키워드, 발행 로그 데이터를 관리합니다.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from supabase import create_client, Client

from .models import Article, Keyword, PublishLog

logger = logging.getLogger("blog_writer.supabase")


class SupabaseClient:
    """
    Blog Writer용 Supabase 클라이언트

    사용 예시:
        client = SupabaseClient(url, key)
        article = await client.create_article(article_data)
        articles = await client.list_articles(status="draft")
    """

    _instance: Optional["SupabaseClient"] = None

    def __init__(self, url: str, key: str):
        """
        Args:
            url: Supabase 프로젝트 URL
            key: Supabase API 키 (anon 또는 service_role)
        """
        self.url = url
        self.key = key
        self.client: Client = create_client(url, key)

    @classmethod
    def get_instance(cls, url: str = None, key: str = None) -> "SupabaseClient":
        """싱글톤 인스턴스 반환"""
        if cls._instance is None:
            if url is None or key is None:
                raise ValueError("First call must provide url and key")
            cls._instance = cls(url, key)
        return cls._instance

    # ==================== Articles ====================

    def create_article(self, article: Article) -> Article:
        """원고 생성"""
        data = article.to_dict()
        # id는 DB에서 자동 생성
        if data.get("id") == "":
            del data["id"]
        # created_at, updated_at 제거 (DB에서 자동)
        data.pop("created_at", None)
        data.pop("updated_at", None)

        result = self.client.table("articles").insert(data).execute()

        if result.data:
            return Article.from_dict(result.data[0])
        raise Exception("Failed to create article")

    def get_article(self, article_id: str) -> Optional[Article]:
        """원고 조회"""
        result = self.client.table("articles").select("*").eq("id", article_id).execute()

        if result.data:
            return Article.from_dict(result.data[0])
        return None

    def list_articles(
        self,
        status: str = None,
        keyword: str = None,
        domain: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Article]:
        """원고 목록 조회"""
        query = self.client.table("articles").select("*")

        if status:
            query = query.eq("status", status)
        if keyword:
            query = query.ilike("keyword", f"%{keyword}%")
        if domain:
            query = query.eq("domain", domain)

        query = query.order("created_at", desc=True).range(offset, offset + limit - 1)

        result = query.execute()

        return [Article.from_dict(item) for item in result.data]

    def update_article(self, article_id: str, updates: Dict[str, Any]) -> Optional[Article]:
        """원고 업데이트"""
        updates["updated_at"] = datetime.now().isoformat()

        result = self.client.table("articles").update(updates).eq("id", article_id).execute()

        if result.data:
            return Article.from_dict(result.data[0])
        return None

    def update_article_status(self, article_id: str, status: str) -> Optional[Article]:
        """원고 상태 업데이트"""
        return self.update_article(article_id, {"status": status})

    def update_article_published(
        self,
        article_id: str,
        blog_url: str,
        blog_post_id: str = None
    ) -> Optional[Article]:
        """원고 발행 정보 업데이트"""
        return self.update_article(article_id, {
            "status": "published",
            "blog_url": blog_url,
            "blog_post_id": blog_post_id,
            "published_at": datetime.now().isoformat()
        })

    def delete_article(self, article_id: str) -> bool:
        """원고 삭제"""
        result = self.client.table("articles").delete().eq("id", article_id).execute()
        return len(result.data) > 0

    # ==================== Keywords ====================

    def create_keyword(self, keyword: Keyword) -> Keyword:
        """키워드 생성"""
        data = keyword.to_dict()
        if data.get("id") == "":
            del data["id"]
        data.pop("created_at", None)

        result = self.client.table("keywords").insert(data).execute()

        if result.data:
            return Keyword(
                id=result.data[0]["id"],
                keyword=result.data[0]["keyword"],
                domain=result.data[0].get("domain", "cctv"),
                category=result.data[0].get("category"),
                search_volume=result.data[0].get("search_volume"),
                competition_level=result.data[0].get("competition_level"),
                articles_count=result.data[0].get("articles_count", 0),
                is_active=result.data[0].get("is_active", True),
                priority=result.data[0].get("priority", 0),
            )
        raise Exception("Failed to create keyword")

    def get_keyword(self, keyword_id: str) -> Optional[Keyword]:
        """키워드 조회"""
        result = self.client.table("keywords").select("*").eq("id", keyword_id).execute()

        if result.data:
            d = result.data[0]
            return Keyword(
                id=d["id"],
                keyword=d["keyword"],
                domain=d.get("domain", "cctv"),
                category=d.get("category"),
                search_volume=d.get("search_volume"),
                competition_level=d.get("competition_level"),
                articles_count=d.get("articles_count", 0),
                is_active=d.get("is_active", True),
                priority=d.get("priority", 0),
            )
        return None

    def list_keywords(
        self,
        domain: str = None,
        is_active: bool = True,
        limit: int = 100
    ) -> List[Keyword]:
        """키워드 목록 조회"""
        query = self.client.table("keywords").select("*")

        if domain:
            query = query.eq("domain", domain)
        if is_active is not None:
            query = query.eq("is_active", is_active)

        query = query.order("priority", desc=True).limit(limit)

        result = query.execute()

        return [
            Keyword(
                id=d["id"],
                keyword=d["keyword"],
                domain=d.get("domain", "cctv"),
                category=d.get("category"),
                search_volume=d.get("search_volume"),
                competition_level=d.get("competition_level"),
                articles_count=d.get("articles_count", 0),
                is_active=d.get("is_active", True),
                priority=d.get("priority", 0),
            )
            for d in result.data
        ]

    def get_unused_keyword(self, domain: str = "cctv") -> Optional[Keyword]:
        """미사용 키워드 조회 (우선순위 높은 순)"""
        result = (
            self.client.table("keywords")
            .select("*")
            .eq("domain", domain)
            .eq("is_active", True)
            .eq("articles_count", 0)
            .order("priority", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            d = result.data[0]
            return Keyword(
                id=d["id"],
                keyword=d["keyword"],
                domain=d.get("domain", "cctv"),
                priority=d.get("priority", 0),
            )
        return None

    def increment_keyword_usage(self, keyword_id: str) -> None:
        """키워드 사용 횟수 증가"""
        # RPC 함수 사용 또는 직접 업데이트
        keyword = self.get_keyword(keyword_id)
        if keyword:
            self.client.table("keywords").update({
                "articles_count": keyword.articles_count + 1,
                "last_used_at": datetime.now().isoformat()
            }).eq("id", keyword_id).execute()

    def bulk_import_keywords(self, keywords: List[str], domain: str = "cctv") -> int:
        """키워드 일괄 등록"""
        data = [
            {"keyword": kw.strip(), "domain": domain, "is_active": True}
            for kw in keywords
            if kw.strip()
        ]

        if not data:
            return 0

        # upsert로 중복 방지
        result = self.client.table("keywords").upsert(
            data,
            on_conflict="keyword"
        ).execute()

        return len(result.data)

    # ==================== Publish Logs ====================

    def create_publish_log(self, log: PublishLog) -> PublishLog:
        """발행 로그 생성"""
        data = log.to_dict()
        if data.get("id") == "":
            del data["id"]
        data.pop("started_at", None)
        data.pop("completed_at", None)

        result = self.client.table("publish_logs").insert(data).execute()

        if result.data:
            d = result.data[0]
            return PublishLog(
                id=d["id"],
                article_id=d["article_id"],
                blog_id=d["blog_id"],
                status=d["status"],
                success=d.get("success", False),
                blog_url=d.get("blog_url"),
                error_message=d.get("error_message"),
            )
        raise Exception("Failed to create publish log")

    def update_publish_log(
        self,
        log_id: str,
        status: str,
        success: bool = False,
        blog_url: str = None,
        error_message: str = None
    ) -> None:
        """발행 로그 업데이트"""
        updates = {
            "status": status,
            "success": success,
            "completed_at": datetime.now().isoformat()
        }
        if blog_url:
            updates["blog_url"] = blog_url
        if error_message:
            updates["error_message"] = error_message

        self.client.table("publish_logs").update(updates).eq("id", log_id).execute()

    def get_publish_logs(self, article_id: str) -> List[PublishLog]:
        """원고의 발행 로그 조회"""
        result = (
            self.client.table("publish_logs")
            .select("*")
            .eq("article_id", article_id)
            .order("started_at", desc=True)
            .execute()
        )

        return [
            PublishLog(
                id=d["id"],
                article_id=d["article_id"],
                blog_id=d["blog_id"],
                status=d["status"],
                success=d.get("success", False),
                blog_url=d.get("blog_url"),
                error_message=d.get("error_message"),
            )
            for d in result.data
        ]

    # ==================== Stats ====================

    def get_article_stats(self) -> Dict[str, Any]:
        """원고 통계"""
        # 전체 수
        total = self.client.table("articles").select("id", count="exact").execute()

        # 상태별 수
        by_status = {}
        for status in ["draft", "reviewed", "approved", "published"]:
            result = self.client.table("articles").select("id", count="exact").eq("status", status).execute()
            by_status[status] = result.count or 0

        return {
            "total": total.count or 0,
            "by_status": by_status,
        }

    # ==================== Async Aliases (for FastAPI routes) ====================

    async def get_articles(
        self,
        status: str = None,
        keyword: str = None,
        domain: str = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Article]:
        """원고 목록 조회 (async alias)"""
        return self.list_articles(status=status, keyword=keyword, domain=domain, limit=limit, offset=offset)

    # ==================== Helper Methods ====================

    def create_publish_log_simple(
        self,
        article_id: str,
        blog_id: str,
        success: bool,
        blog_url: str = None,
        error_message: str = None
    ) -> PublishLog:
        """발행 로그 생성 (간단한 파라미터 버전)"""
        log = PublishLog(
            id="",
            article_id=article_id,
            blog_id=blog_id,
            status="completed" if success else "failed",
            success=success,
            blog_url=blog_url,
            error_message=error_message
        )
        return self.create_publish_log(log)
