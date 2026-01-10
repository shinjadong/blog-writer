"""
트래픽 트리거

ai-project와 연동하여 발행된 블로그에 트래픽을 유입시킵니다.

Author: CareOn Blog Writer
Created: 2026-01-10
"""

import logging
import aiohttp
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("blog_writer.traffic")


@dataclass
class TrafficTriggerConfig:
    """트래픽 트리거 설정"""
    # ai-project API 설정
    api_base_url: str = "http://localhost:8000"
    api_key: str = "careon-traffic-engine-2026"

    # 실행 설정
    timeout: int = 30  # 요청 타임아웃 (초)


@dataclass
class TrafficTriggerResult:
    """트래픽 트리거 결과"""
    success: bool
    execution_id: Optional[str] = None
    message: str = ""
    campaign_id: Optional[str] = None
    error: Optional[str] = None


class TrafficTrigger:
    """
    ai-project 트래픽 엔진 트리거

    발행된 블로그 포스트에 대해 ai-project의 트래픽 자동화를 실행합니다.

    사용 예시:
        trigger = TrafficTrigger(config=TrafficTriggerConfig(
            api_base_url="http://localhost:8000",
            api_key="careon-traffic-engine-2026"
        ))

        # AI 모드로 트래픽 실행 (권장)
        result = await trigger.execute_ai(
            campaign_id="xxx",
            keyword="CCTV설치비용",
            blog_title="매장CCTV설치비용 완벽 가이드"
        )

        # 기본 모드로 트래픽 실행
        result = await trigger.execute(campaign_id="xxx")
    """

    def __init__(self, config: TrafficTriggerConfig = None):
        self.config = config or TrafficTriggerConfig()

    async def execute(
        self,
        campaign_id: str,
        persona_id: Optional[str] = None,
        device_serial: Optional[str] = None
    ) -> TrafficTriggerResult:
        """
        기본 트래픽 실행 (Pipeline 모드)

        Args:
            campaign_id: 캠페인 UUID
            persona_id: 사용할 페르소나 ID (없으면 자동 선택)
            device_serial: 사용할 디바이스 (없으면 자동 선택)

        Returns:
            TrafficTriggerResult
        """
        payload = {
            "campaign_id": campaign_id
        }
        if persona_id:
            payload["persona_id"] = persona_id
        if device_serial:
            payload["device_serial"] = device_serial

        return await self._post("/traffic/execute", payload)

    async def execute_ai(
        self,
        campaign_id: str,
        keyword: Optional[str] = None,
        blog_title: Optional[str] = None,
        blogger_name: Optional[str] = None,
        blog_url: Optional[str] = None,
        device_serial: Optional[str] = None
    ) -> TrafficTriggerResult:
        """
        AI 모드 트래픽 실행 (권장)

        동적 UI 탐지를 통해 더 안정적인 트래픽 생성

        Args:
            campaign_id: 캠페인 UUID
            keyword: 검색 키워드 (없으면 캠페인에서 조회)
            blog_title: 타겟 블로그 포스트 제목
            blogger_name: 블로거 이름
            blog_url: 폴백용 블로그 URL
            device_serial: 사용할 디바이스

        Returns:
            TrafficTriggerResult
        """
        payload = {
            "campaign_id": campaign_id
        }
        if keyword:
            payload["keyword"] = keyword
        if blog_title:
            payload["blog_title"] = blog_title
        if blogger_name:
            payload["blogger_name"] = blogger_name
        if blog_url:
            payload["blog_url"] = blog_url
        if device_serial:
            payload["device_serial"] = device_serial

        return await self._post("/traffic/execute-ai", payload)

    async def batch_execute(
        self,
        campaign_id: str,
        count: int = 1
    ) -> TrafficTriggerResult:
        """
        배치 트래픽 실행

        Args:
            campaign_id: 캠페인 UUID
            count: 실행 횟수 (1-10)

        Returns:
            TrafficTriggerResult
        """
        payload = {
            "campaign_id": campaign_id,
            "count": min(max(count, 1), 10)
        }

        return await self._post("/traffic/batch", payload)

    async def get_campaign(self, campaign_id: str) -> Optional[Dict[str, Any]]:
        """
        캠페인 정보 조회

        Args:
            campaign_id: 캠페인 UUID

        Returns:
            캠페인 정보 딕셔너리 또는 None
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-API-Key": self.config.api_key,
                    "Content-Type": "application/json"
                }

                url = f"{self.config.api_base_url}/campaigns/{campaign_id}"

                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Failed to get campaign: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Campaign fetch error: {e}")
            return None

    async def list_campaigns(self, limit: int = 10) -> list:
        """
        캠페인 목록 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            캠페인 목록
        """
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-API-Key": self.config.api_key,
                    "Content-Type": "application/json"
                }

                url = f"{self.config.api_base_url}/campaigns?limit={limit}"

                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.warning(f"Failed to list campaigns: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"Campaign list error: {e}")
            return []

    async def health_check(self) -> bool:
        """
        ai-project 서버 상태 확인

        Returns:
            서버 정상 여부
        """
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.config.api_base_url}/health"

                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    return response.status == 200

        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def _post(self, endpoint: str, payload: Dict[str, Any]) -> TrafficTriggerResult:
        """POST 요청 헬퍼"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-API-Key": self.config.api_key,
                    "Content-Type": "application/json"
                }

                url = f"{self.config.api_base_url}{endpoint}"
                logger.info(f"POST {url} with payload: {payload}")

                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config.timeout)
                ) as response:
                    data = await response.json()

                    if response.status == 200:
                        return TrafficTriggerResult(
                            success=data.get("success", False),
                            execution_id=data.get("execution_id"),
                            message=data.get("message", ""),
                            campaign_id=data.get("campaign_id")
                        )
                    else:
                        return TrafficTriggerResult(
                            success=False,
                            error=data.get("detail", f"HTTP {response.status}"),
                            message=data.get("message", "요청 실패")
                        )

        except aiohttp.ClientError as e:
            logger.error(f"HTTP request failed: {e}")
            return TrafficTriggerResult(
                success=False,
                error=str(e),
                message="ai-project 서버 연결 실패"
            )
        except Exception as e:
            logger.error(f"Traffic trigger error: {e}")
            return TrafficTriggerResult(
                success=False,
                error=str(e),
                message="트래픽 트리거 오류"
            )
