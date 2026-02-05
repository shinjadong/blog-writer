"""
DeepSeek API 클라이언트

블로그 원고 생성을 위한 DeepSeek LLM API 통신 모듈입니다.

Author: CareOn Blog Writer
Created: 2026-01-10
"""

import aiohttp
import json
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger("blog_writer.deepseek_client")


class DeepSeekClient:
    """
    DeepSeek API 클라이언트

    블로그 원고 생성을 위한 채팅 완성 API를 사용합니다.

    사용 예시:
        client = DeepSeekClient(api_key="your_api_key")

        response = await client.chat(
            user_prompt="CCTV 설치 비용에 대한 블로그 글을 작성해주세요",
            system_prompt=BLOG_SYSTEM_PROMPT,
            response_format="text"
        )
    """

    BASE_URL = "https://api.deepseek.com/v1"

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = None
    ):
        """
        Args:
            api_key: DeepSeek API 키
            model: 사용할 모델 (기본: deepseek-chat)
            base_url: API 베이스 URL (기본: https://api.deepseek.com/v1)
        """
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or self.BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async def chat(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        response_format: str = "text",
        temperature: float = 0.7,
        max_tokens: int = 8192,
        top_p: float = 0.9,
        presence_penalty: float = 0.0,
        frequency_penalty: float = 0.0
    ) -> str:
        """
        채팅 완성 요청

        Args:
            user_prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택)
            response_format: 응답 형식 ("text" 또는 "json")
            temperature: 생성 온도 (0.0-2.0)
            max_tokens: 최대 토큰 수
            top_p: Top-p 샘플링
            presence_penalty: 존재 페널티
            frequency_penalty: 빈도 페널티

        Returns:
            생성된 텍스트 또는 JSON 문자열
        """
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        messages.append({
            "role": "user",
            "content": user_prompt
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
        }

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)  # 블로그 생성은 시간이 오래 걸릴 수 있음
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"DeepSeek API error: {response.status} - {error_text}")
                        raise Exception(f"DeepSeek API error: {response.status}")

                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]

                    # 토큰 사용량 로깅
                    usage = result.get("usage", {})
                    logger.info(
                        f"DeepSeek usage - prompt: {usage.get('prompt_tokens', 0)}, "
                        f"completion: {usage.get('completion_tokens', 0)}, "
                        f"total: {usage.get('total_tokens', 0)}"
                    )

                    return content

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            raise
        except Exception as e:
            logger.error(f"DeepSeek API call failed: {e}")
            raise

    async def chat_with_history(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        response_format: str = "text",
        temperature: float = 0.7,
        max_tokens: int = 8192
    ) -> str:
        """
        대화 히스토리와 함께 채팅

        Args:
            messages: 대화 히스토리 [{"role": "user/assistant", "content": "..."}]
            system_prompt: 시스템 프롬프트
            response_format: 응답 형식
            temperature: 생성 온도
            max_tokens: 최대 토큰 수

        Returns:
            생성된 응답
        """
        full_messages = []

        if system_prompt:
            full_messages.append({
                "role": "system",
                "content": system_prompt
            })

        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"DeepSeek API error: {response.status} - {error_text}")

                    result = await response.json()
                    return result["choices"][0]["message"]["content"]

        except Exception as e:
            logger.error(f"DeepSeek chat with history failed: {e}")
            raise

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.5
    ) -> Dict[str, Any]:
        """
        JSON 응답 생성 (파싱 포함)

        Args:
            prompt: 프롬프트
            system_prompt: 시스템 프롬프트
            temperature: 생성 온도

        Returns:
            파싱된 JSON 딕셔너리
        """
        response = await self.chat(
            user_prompt=prompt,
            system_prompt=system_prompt,
            response_format="json",
            temperature=temperature
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.debug(f"Raw response: {response}")

            # JSON 부분만 추출 시도
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(response[start:end])
                except:
                    pass

            raise

    async def generate_blog_content(
        self,
        prompt: str,
        system_prompt: str,
        temperature: float = 0.8
    ) -> str:
        """
        블로그 콘텐츠 생성 (마크다운 형식)

        Args:
            prompt: 콘텐츠 생성 프롬프트
            system_prompt: 시스템 프롬프트
            temperature: 생성 온도 (0.8 - 창의적 글쓰기용)

        Returns:
            생성된 마크다운 콘텐츠
        """
        return await self.chat(
            user_prompt=prompt,
            system_prompt=system_prompt,
            response_format="text",
            temperature=temperature,
            max_tokens=8192,  # 긴 블로그 글을 위해 토큰 수 증가
            presence_penalty=0.1,  # 반복 감소
            frequency_penalty=0.1
        )

    async def reason(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 16384
    ) -> Dict[str, Any]:
        """
        DeepSeek Reasoner 모델 호출 (thinking 기능)

        Reasoner 모델은 복잡한 분석과 추론이 필요한 작업에 사용됩니다.
        temperature, top_p 파라미터를 지원하지 않습니다.

        Args:
            user_prompt: 사용자 프롬프트
            system_prompt: 시스템 프롬프트 (선택)
            max_tokens: 최대 토큰 수 (기본 16384)

        Returns:
            {
                "reasoning_content": str,  # 추론 과정
                "content": str,            # 최종 응답
                "usage": dict              # 토큰 사용량
            }
        """
        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        messages.append({
            "role": "user",
            "content": user_prompt
        })

        payload = {
            "model": "deepseek-reasoner",
            "messages": messages,
            "max_tokens": max_tokens
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300)  # Reasoner는 더 오래 걸릴 수 있음
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(f"DeepSeek Reasoner API error: {response.status} - {error_text}")
                        raise Exception(f"DeepSeek Reasoner API error: {response.status}")

                    result = await response.json()
                    message = result["choices"][0]["message"]

                    # 토큰 사용량 로깅
                    usage = result.get("usage", {})
                    logger.info(
                        f"DeepSeek Reasoner usage - prompt: {usage.get('prompt_tokens', 0)}, "
                        f"completion: {usage.get('completion_tokens', 0)}, "
                        f"reasoning: {usage.get('reasoning_tokens', 0)}, "
                        f"total: {usage.get('total_tokens', 0)}"
                    )

                    return {
                        "reasoning_content": message.get("reasoning_content", ""),
                        "content": message.get("content", ""),
                        "usage": usage
                    }

        except aiohttp.ClientError as e:
            logger.error(f"HTTP client error: {e}")
            raise
        except Exception as e:
            logger.error(f"DeepSeek Reasoner API call failed: {e}")
            raise

    async def reason_json(
        self,
        user_prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 16384
    ) -> Dict[str, Any]:
        """
        Reasoner로 JSON 응답 생성 (파싱 포함)

        Args:
            user_prompt: 프롬프트 (JSON 형식 응답 요청 포함)
            system_prompt: 시스템 프롬프트
            max_tokens: 최대 토큰 수

        Returns:
            {
                "reasoning_content": str,
                "data": dict,  # 파싱된 JSON
                "usage": dict
            }
        """
        result = await self.reason(user_prompt, system_prompt, max_tokens)

        content = result["content"]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # JSON 부분만 추출 시도
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                try:
                    data = json.loads(content[start:end])
                except:
                    logger.error(f"Failed to parse JSON from Reasoner: {content[:500]}")
                    data = {"raw_content": content}
            else:
                data = {"raw_content": content}

        return {
            "reasoning_content": result["reasoning_content"],
            "data": data,
            "usage": result["usage"]
        }

    async def health_check(self) -> bool:
        """API 연결 상태 확인"""
        try:
            response = await self.chat(
                user_prompt="Hello, respond with 'OK'",
                max_tokens=10,
                temperature=0
            )
            return "OK" in response or len(response) > 0
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
