"""
네이버 검색 API 클라이언트

네이버 블로그 검색 API를 통해 키워드 관련 상위 블로그 글을 수집합니다.
"""

import aiohttp
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger("blog_writer.naver_search")


@dataclass
class BlogSearchResult:
    """블로그 검색 결과 단일 항목"""
    rank: int
    title: str
    link: str
    description: str
    bloggername: str
    bloggerlink: str
    postdate: str


@dataclass
class NaverSearchResponse:
    """네이버 검색 API 응답"""
    keyword: str
    search_date: str
    total: int
    blogs: List[BlogSearchResult]


class NaverSearchClient:
    """
    네이버 검색 API 클라이언트

    네이버 오픈 API를 사용하여 블로그 검색 결과를 가져옵니다.

    사용 예시:
        client = NaverSearchClient(client_id="...", client_secret="...")
        result = await client.search_blog("CCTV 설치 비용")
    """

    BASE_URL = "https://openapi.naver.com/v1/search/blog.json"

    def __init__(self, client_id: str, client_secret: str):
        """
        Args:
            client_id: 네이버 개발자 센터 Client ID
            client_secret: 네이버 개발자 센터 Client Secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.headers = {
            "X-Naver-Client-Id": client_id,
            "X-Naver-Client-Secret": client_secret
        }

    async def search_blog(
        self,
        query: str,
        display: int = 10,
        start: int = 1,
        sort: str = "sim"
    ) -> NaverSearchResponse:
        """
        네이버 블로그 검색

        Args:
            query: 검색 키워드
            display: 검색 결과 개수 (1-100, 기본 10)
            start: 검색 시작 위치 (1-1000, 기본 1)
            sort: 정렬 방식 (sim: 정확도순, date: 날짜순)

        Returns:
            NaverSearchResponse 객체
        """
        params = {
            "query": query,
            "display": display,
            "start": start,
            "sort": sort
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.BASE_URL,
                    headers=self.headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"Naver API error: {response.status} - {error_text}")
                        raise Exception(f"Naver API error: {response.status}")

                    data = await response.json()

                    blogs = []
                    for idx, item in enumerate(data.get("items", []), start=1):
                        # HTML 태그 제거
                        title = self._strip_html(item.get("title", ""))
                        description = self._strip_html(item.get("description", ""))

                        blogs.append(BlogSearchResult(
                            rank=idx,
                            title=title,
                            link=item.get("link", ""),
                            description=description,
                            bloggername=item.get("bloggername", ""),
                            bloggerlink=item.get("bloggerlink", ""),
                            postdate=item.get("postdate", "")
                        ))

                    logger.info(f"Naver search for '{query}': {len(blogs)} results")

                    return NaverSearchResponse(
                        keyword=query,
                        search_date=datetime.now().strftime("%Y-%m-%d"),
                        total=data.get("total", 0),
                        blogs=blogs
                    )

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            raise
        except Exception as e:
            logger.error(f"Naver search failed: {e}")
            raise

    def _strip_html(self, text: str) -> str:
        """HTML 태그 제거"""
        import re
        clean = re.sub(r'<[^>]+>', '', text)
        return clean.strip()

    async def search_and_analyze(
        self,
        query: str,
        display: int = 10
    ) -> Dict:
        """
        검색 결과를 딕셔너리로 반환 (JSON 저장용)

        Args:
            query: 검색 키워드
            display: 검색 결과 개수

        Returns:
            JSON 저장 가능한 딕셔너리
        """
        result = await self.search_blog(query, display)

        return {
            "keyword": result.keyword,
            "search_date": result.search_date,
            "total_results": result.total,
            "top_blogs": [
                {
                    "rank": blog.rank,
                    "title": blog.title,
                    "url": blog.link,
                    "description": blog.description,
                    "bloggername": blog.bloggername,
                    "postdate": blog.postdate
                }
                for blog in result.blogs
            ]
        }

    async def health_check(self) -> bool:
        """API 연결 상태 확인"""
        try:
            result = await self.search_blog("테스트", display=1)
            return len(result.blogs) > 0
        except Exception as e:
            logger.error(f"Naver API health check failed: {e}")
            return False
