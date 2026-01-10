"""
AI UI Analyzer - DeepSeek 기반 동적 UI 분석

스크린샷과 DOM 정보를 DeepSeek에 전송하여
현재 UI 상태를 분석하고 요소 위치를 동적으로 파악합니다.

Manus/Browser-Use 워크플로우 패턴 참조.
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from io import BytesIO

import aiohttp
from PIL import Image

logger = logging.getLogger("blog_writer.ai.ui_analyzer")


@dataclass
class UIElement:
    """발견된 UI 요소"""
    name: str
    description: str
    selector: Optional[str] = None
    coords: Optional[tuple] = None  # (x, y)
    rect: Optional[Dict] = None  # {x, y, width, height}
    interaction: str = "click"  # click, input, hover
    confidence: float = 0.0


@dataclass
class UIMap:
    """분석된 UI 맵"""
    elements: Dict[str, UIElement] = field(default_factory=dict)
    page_type: str = "unknown"
    analysis_timestamp: float = 0.0
    raw_response: str = ""

    def get(self, name: str) -> Optional[UIElement]:
        return self.elements.get(name)

    def has(self, name: str) -> bool:
        return name in self.elements


class DeepSeekVisionClient:
    """DeepSeek Vision API 클라이언트

    Note: deepseek-chat은 비전을 지원하지 않습니다.
    비전 분석이 필요하면 deepseek-vl2 모델을 사용하세요.
    또는 텍스트(DOM) 기반 분석만 사용할 수 있습니다.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",  # 비전: deepseek-vl2
        timeout: int = 60,
        use_vision: bool = False  # 비전 사용 여부
    ):
        import os
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url
        self.model = model
        self.use_vision = use_vision
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY 환경변수가 필요합니다")

    async def analyze_image(
        self,
        image_base64: str,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.1
    ) -> str:
        """이미지 분석 요청"""

        messages = []

        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt
            })

        # 이미지 포함 메시지
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        })

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise RuntimeError(f"DeepSeek API 에러: {response.status} - {error_text}")

                result = await response.json()
                return result["choices"][0]["message"]["content"]

    async def analyze_with_json(
        self,
        image_base64: str,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> Dict:
        """이미지 분석 후 JSON 파싱"""

        response = await self.analyze_image(
            image_base64=image_base64,
            prompt=prompt + "\n\n반드시 JSON 형식으로만 응답하세요.",
            system_prompt=system_prompt
        )

        # JSON 추출
        try:
            # ```json ... ``` 블록 추출
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                json_str = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                json_str = response[start:end].strip()
            else:
                # 전체가 JSON이라고 가정
                json_str = response.strip()

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 실패: {e}\n응답: {response[:500]}")
            return {"error": str(e), "raw": response}


class AIUIAnalyzer:
    """
    AI 기반 UI 분석기

    스크린샷을 DeepSeek에 전송하여 UI 요소를 동적으로 분석합니다.

    사용 예시:
        analyzer = AIUIAnalyzer()
        ui_map = await analyzer.analyze_editor(screenshot_base64)

        # 요소 찾기
        image_btn = ui_map.get("image_button")
        if image_btn and image_btn.coords:
            await click_at(*image_btn.coords)
    """

    SYSTEM_PROMPT = """당신은 네이버 블로그 스마트에디터 UI 분석 전문가입니다.
스크린샷을 분석하여 UI 요소들의 위치와 상호작용 방법을 정확하게 파악합니다.

응답 규칙:
1. 반드시 JSON 형식으로만 응답
2. 좌표는 픽셀 단위의 정수로 제공
3. 확신도(confidence)는 0.0~1.0 사이 값
4. 보이지 않는 요소는 포함하지 않음"""

    ANALYSIS_PROMPT = """이 네이버 블로그 에디터 스크린샷을 분석해주세요.

다음 UI 요소들을 찾아 위치와 정보를 JSON으로 반환하세요:

1. title_input: 제목 입력 영역
2. body_area: 본문 입력 영역
3. image_button: 이미지 업로드 버튼 (사진/이미지 아이콘)
4. oglink_button: 글감/링크 버튼
5. quote_button: 인용구 버튼
6. divider_button: 구분선 버튼
7. bold_button: 볼드(B) 버튼
8. publish_button: 발행 버튼
9. temp_save_popup: 임시저장 팝업 (있으면)
10. active_modal: 현재 열린 모달 (있으면)

JSON 형식:
{
    "page_type": "editor" | "login" | "other",
    "elements": {
        "element_name": {
            "found": true/false,
            "description": "요소 설명",
            "coords": [x, y],  // 클릭 좌표 (중앙점)
            "rect": {"x": 0, "y": 0, "width": 0, "height": 0},
            "text_label": "버튼에 보이는 텍스트",
            "interaction": "click" | "input" | "hover",
            "confidence": 0.0-1.0
        }
    },
    "observations": ["현재 화면 상태에 대한 관찰"]
}"""

    def __init__(self, api_key: Optional[str] = None):
        self.client = DeepSeekVisionClient(api_key=api_key)
        self._last_analysis: Optional[UIMap] = None

    async def analyze_editor(
        self,
        screenshot_base64: str,
        additional_context: Optional[str] = None
    ) -> UIMap:
        """에디터 UI 분석

        Args:
            screenshot_base64: Base64 인코딩된 스크린샷
            additional_context: 추가 컨텍스트 (예: DOM 정보)

        Returns:
            UIMap 객체
        """
        import time

        prompt = self.ANALYSIS_PROMPT
        if additional_context:
            prompt += f"\n\n추가 컨텍스트:\n{additional_context}"

        logger.info("DeepSeek에 UI 분석 요청 중...")

        try:
            result = await self.client.analyze_with_json(
                image_base64=screenshot_base64,
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT
            )

            if "error" in result:
                logger.error(f"분석 실패: {result.get('error')}")
                return UIMap(raw_response=result.get("raw", ""))

            # UIMap 구성
            ui_map = UIMap(
                page_type=result.get("page_type", "unknown"),
                analysis_timestamp=time.time(),
                raw_response=json.dumps(result, ensure_ascii=False)
            )

            # 요소 파싱
            elements = result.get("elements", {})
            for name, info in elements.items():
                if not info.get("found", False):
                    continue

                coords = info.get("coords")
                if coords and len(coords) == 2:
                    coords = tuple(coords)
                else:
                    coords = None

                ui_map.elements[name] = UIElement(
                    name=name,
                    description=info.get("description", ""),
                    coords=coords,
                    rect=info.get("rect"),
                    interaction=info.get("interaction", "click"),
                    confidence=info.get("confidence", 0.0)
                )

            logger.info(f"UI 분석 완료: {len(ui_map.elements)}개 요소 발견")
            for name, elem in ui_map.elements.items():
                logger.debug(f"  - {name}: {elem.coords} (confidence={elem.confidence:.2f})")

            self._last_analysis = ui_map
            return ui_map

        except Exception as e:
            logger.error(f"UI 분석 중 오류: {e}")
            import traceback
            traceback.print_exc()
            return UIMap()

    async def analyze_modal(
        self,
        screenshot_base64: str,
        modal_type: str = "unknown"
    ) -> Dict[str, Any]:
        """모달/팝업 분석

        Args:
            screenshot_base64: Base64 인코딩된 스크린샷
            modal_type: 예상되는 모달 타입 (oglink, image, temp_save 등)

        Returns:
            모달 분석 결과
        """
        prompt = f"""현재 화면에 모달/팝업이 열려있습니다.
예상 타입: {modal_type}

다음 정보를 JSON으로 반환하세요:
{{
    "modal_found": true/false,
    "modal_type": "실제 모달 타입",
    "title": "모달 제목",
    "input_fields": [
        {{"name": "필드명", "placeholder": "...", "coords": [x, y]}}
    ],
    "buttons": [
        {{"text": "버튼 텍스트", "type": "confirm/cancel/other", "coords": [x, y]}}
    ],
    "recommended_action": "취해야 할 행동 설명"
}}"""

        try:
            result = await self.client.analyze_with_json(
                image_base64=screenshot_base64,
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT
            )
            return result
        except Exception as e:
            logger.error(f"모달 분석 실패: {e}")
            return {"error": str(e)}

    async def find_element(
        self,
        screenshot_base64: str,
        element_description: str
    ) -> Optional[UIElement]:
        """특정 요소 찾기

        Args:
            screenshot_base64: Base64 인코딩된 스크린샷
            element_description: 찾을 요소 설명 (예: "이미지 업로드 버튼")

        Returns:
            발견된 UIElement 또는 None
        """
        prompt = f"""다음 UI 요소를 찾아주세요: "{element_description}"

JSON 형식으로 응답:
{{
    "found": true/false,
    "description": "요소 설명",
    "coords": [x, y],
    "confidence": 0.0-1.0,
    "alternative_elements": [  // 비슷한 요소들
        {{"description": "...", "coords": [x, y]}}
    ]
}}"""

        try:
            result = await self.client.analyze_with_json(
                image_base64=screenshot_base64,
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT
            )

            if result.get("found"):
                coords = result.get("coords")
                return UIElement(
                    name=element_description,
                    description=result.get("description", ""),
                    coords=tuple(coords) if coords else None,
                    confidence=result.get("confidence", 0.0)
                )
            return None

        except Exception as e:
            logger.error(f"요소 찾기 실패: {e}")
            return None

    async def decide_action(
        self,
        screenshot_base64: str,
        task: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """현재 상황에서 취해야 할 행동 결정

        Args:
            screenshot_base64: Base64 인코딩된 스크린샷
            task: 수행하려는 작업 (예: "이미지 업로드", "글감 삽입")
            context: 추가 컨텍스트

        Returns:
            행동 결정 결과
        """
        prompt = f"""현재 수행하려는 작업: {task}
{f'추가 컨텍스트: {context}' if context else ''}

현재 화면 상태를 분석하고 다음 단계를 결정해주세요.

JSON 형식으로 응답:
{{
    "current_state": "현재 화면 상태 설명",
    "can_proceed": true/false,
    "next_action": {{
        "type": "click" | "input" | "wait" | "escape" | "scroll",
        "target": "대상 설명",
        "coords": [x, y],  // 클릭/입력 위치
        "value": "입력할 값 (input인 경우)"
    }},
    "blockers": ["진행을 막는 요소들"],
    "confidence": 0.0-1.0
}}"""

        try:
            result = await self.client.analyze_with_json(
                image_base64=screenshot_base64,
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT
            )
            return result
        except Exception as e:
            logger.error(f"행동 결정 실패: {e}")
            return {"error": str(e), "can_proceed": False}

    def get_last_analysis(self) -> Optional[UIMap]:
        """마지막 분석 결과 반환"""
        return self._last_analysis


def compress_screenshot(
    image_data: bytes,
    max_size: tuple = (1920, 1080),
    quality: int = 85
) -> str:
    """스크린샷 압축 및 Base64 인코딩

    Browser-Use/OpenManus의 이미지 압축 로직 참조
    """
    img = Image.open(BytesIO(image_data))

    # RGBA → RGB 변환
    if img.mode in ('RGBA', 'LA', 'P'):
        img = img.convert('RGB')

    # 리사이즈
    if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
        img.thumbnail(max_size, Image.Resampling.LANCZOS)

    # JPEG 압축
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=quality, optimize=True)
    buffer.seek(0)

    return base64.b64encode(buffer.read()).decode('utf-8')


async def capture_and_analyze(page, analyzer: AIUIAnalyzer) -> UIMap:
    """페이지 캡처 및 분석 헬퍼"""
    screenshot_bytes = await page.screenshot(type='jpeg', quality=85)
    screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
    return await analyzer.analyze_editor(screenshot_b64)
