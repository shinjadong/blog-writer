"""
AdaptivePublisher - AI 기반 적응형 네이버 블로그 발행기

각 동작마다 DOM 파싱 + 스크린샷을 AI에 전송하여
동적으로 UI 요소를 파악하고 상호작용합니다.

Manus/Browser-Use 워크플로우 패턴 적용.
"""

import asyncio
import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from playwright.async_api import async_playwright, Page

from .ai import AIUIAnalyzer, UIMap, compress_screenshot

logger = logging.getLogger("blog_writer.adaptive_publisher")


@dataclass
class PublishConfig:
    """발행 설정"""
    blog_id: str
    cdp_url: str = "http://localhost:9222"
    deepseek_api_key: Optional[str] = None
    screenshot_dir: str = "data/adaptive_screenshots"
    max_retries: int = 3


@dataclass
class PublishResult:
    """발행 결과"""
    success: bool
    blog_url: Optional[str] = None
    error_message: Optional[str] = None
    screenshots: List[str] = field(default_factory=list)


class AdaptivePublisher:
    """
    AI 기반 적응형 블로그 발행기

    매 동작마다:
    1. DOM 스냅샷 추출 (기존 파싱 로직)
    2. 스크린샷 캡처
    3. DeepSeek에 전송하여 분석
    4. AI 응답 기반으로 행동 결정

    사용 예시:
        publisher = AdaptivePublisher(config)
        result = await publisher.publish(
            title="제목",
            sections=[
                {"type": "text", "content": "내용"},
                {"type": "image", "path": "/path/to/img.jpg"},
                {"type": "oglink", "url": "https://example.com"}
            ]
        )
    """

    def __init__(self, config: PublishConfig):
        self.config = config
        self.page: Optional[Page] = None
        self.cdp = None
        self._playwright = None

        # AI 분석기
        self.analyzer = AIUIAnalyzer(api_key=config.deepseek_api_key)

        # UI 캐시 (세션 중 재사용)
        self._ui_cache: Optional[UIMap] = None

        # 스크린샷 저장
        self.screenshot_dir = Path(config.screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)

    async def _init_browser(self):
        """브라우저 초기화"""
        self._playwright = await async_playwright().start()

        try:
            browser = await self._playwright.chromium.connect_over_cdp(self.config.cdp_url)
            logger.info(f"CDP 연결 성공: {self.config.cdp_url}")
        except Exception as e:
            raise RuntimeError(f"CDP 연결 실패: {e}")

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()
        self.page = await context.new_page()

        # CDP 세션
        self.cdp = await self.page.context.new_cdp_session(self.page)
        await self.cdp.send("DOM.enable")
        await self.cdp.send("Runtime.enable")

    async def _close_browser(self):
        """브라우저 정리"""
        try:
            if self.page:
                await self.page.close()
            if self._playwright:
                await self._playwright.stop()
        except:
            pass

    async def _get_dom_snapshot(self) -> Dict[str, Any]:
        """DOM 스냅샷 추출 (기존 파싱 로직)"""
        snapshot = await self._evaluate_js("""
            (() => {
                const result = {
                    url: window.location.href,
                    title: document.title,
                    editor: {},
                    toolbar: {},
                    modals: [],
                    inputs: []
                };

                // 에디터 상태
                const titleEl = document.querySelector('.se-documentTitle .se-text-paragraph');
                if (titleEl) {
                    const rect = titleEl.getBoundingClientRect();
                    result.editor.title = {
                        found: true,
                        text: titleEl.innerText || '',
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                    };
                }

                // 본문 영역
                const bodyEl = document.querySelector('.se-component.se-text .se-text-paragraph');
                if (bodyEl) {
                    const rect = bodyEl.getBoundingClientRect();
                    result.editor.body = {
                        found: true,
                        coords: [rect.x + 50, rect.y + 20]
                    };
                }

                // 툴바 버튼들
                const toolButtons = [
                    'image', 'oglink', 'quotation', 'horizontal-line',
                    'bold', 'italic', 'underline', 'font-size'
                ];

                for (const name of toolButtons) {
                    const btn = document.querySelector(`[data-name="${name}"]`);
                    if (btn) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {
                            result.toolbar[name] = {
                                found: true,
                                text: btn.innerText?.trim() || '',
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                            };
                        }
                    }
                }

                // 글감 버튼 (텍스트로 찾기)
                const allBtns = document.querySelectorAll('button');
                for (const btn of allBtns) {
                    const text = btn.innerText?.trim() || '';
                    if (text.includes('글감')) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {
                            result.toolbar['material'] = {
                                found: true,
                                text: text,
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                            };
                        }
                    }
                    if (text === '발행') {
                        const rect = btn.getBoundingClientRect();
                        result.toolbar['publish'] = {
                            found: true,
                            text: text,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        };
                    }
                }

                // 팝업/모달
                const popups = document.querySelectorAll('.se-popup, [class*="modal"], [class*="layer"]');
                for (const popup of popups) {
                    const rect = popup.getBoundingClientRect();
                    const style = getComputedStyle(popup);
                    if (rect.width > 100 && style.display !== 'none') {
                        result.modals.push({
                            className: popup.className,
                            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                        });
                    }
                }

                // 입력 필드
                const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea');
                for (const inp of inputs) {
                    const rect = inp.getBoundingClientRect();
                    if (rect.width > 50) {
                        result.inputs.push({
                            type: inp.type || 'text',
                            placeholder: inp.placeholder || '',
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        });
                    }
                }

                return result;
            })()
        """)

        return snapshot or {}

    async def _capture_screenshot(self) -> str:
        """스크린샷 캡처 및 Base64 인코딩"""
        screenshot_bytes = await self.page.screenshot(type='jpeg', quality=85)
        return base64.b64encode(screenshot_bytes).decode('utf-8')

    async def _save_screenshot(self, name: str) -> str:
        """스크린샷 저장"""
        timestamp = datetime.now().strftime("%H%M%S")
        path = self.screenshot_dir / f"{timestamp}_{name}.png"
        await self.page.screenshot(path=str(path))
        return str(path)

    async def _analyze_current_state(self, task_context: str = "", use_ai: bool = False) -> Dict[str, Any]:
        """현재 상태 분석 (DOM 기반, 선택적 AI)

        매 동작마다 호출되어 현재 UI 상태를 파악합니다.

        Args:
            task_context: 현재 작업 설명
            use_ai: AI 분석 사용 여부 (기본: False - DOM만 사용)
        """
        # 1. DOM 스냅샷 (항상 수행)
        dom_snapshot = await self._get_dom_snapshot()

        result = {
            "dom": dom_snapshot,
            "ai_decision": {},
            "screenshot_b64": None
        }

        # 2. AI 분석 (선택적)
        if use_ai:
            screenshot_b64 = await self._capture_screenshot()
            result["screenshot_b64"] = screenshot_b64

            context = f"""DOM 스냅샷:
{json.dumps(dom_snapshot, ensure_ascii=False, indent=2)}

현재 작업: {task_context}"""

            logger.info(f"AI 분석 요청: {task_context}")

            # 텍스트 기반 AI 분석 (비전 없이)
            action_decision = await self._get_ai_decision_text_only(
                task=task_context,
                dom_context=context
            )
            result["ai_decision"] = action_decision

        return result

    async def _get_ai_decision_text_only(self, task: str, dom_context: str) -> Dict[str, Any]:
        """텍스트 기반 AI 의사결정 (비전 없이)"""
        try:
            import aiohttp

            prompt = f"""현재 수행하려는 작업: {task}

{dom_context}

DOM 정보를 분석하여 다음 단계를 결정해주세요.

JSON 형식으로 응답:
{{
    "current_state": "현재 상태 설명",
    "can_proceed": true/false,
    "next_action": {{
        "type": "click" | "input" | "wait" | "escape",
        "target": "대상 설명",
        "dom_key": "DOM에서 찾을 키 (예: toolbar.oglink)",
        "value": "입력할 값 (input인 경우)"
    }},
    "confidence": 0.0-1.0
}}"""

            payload = {
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "당신은 네이버 블로그 에디터 자동화 전문가입니다. DOM 정보를 분석하여 다음 행동을 결정합니다."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1024,
                "temperature": 0.1
            }

            headers = {
                "Authorization": f"Bearer {self.config.deepseek_api_key}",
                "Content-Type": "application/json"
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        return {"error": await response.text(), "can_proceed": False}

                    result = await response.json()
                    content = result["choices"][0]["message"]["content"]

                    # JSON 파싱
                    if "```json" in content:
                        start = content.find("```json") + 7
                        end = content.find("```", start)
                        json_str = content[start:end].strip()
                    elif "```" in content:
                        start = content.find("```") + 3
                        end = content.find("```", start)
                        json_str = content[start:end].strip()
                    else:
                        json_str = content.strip()

                    return json.loads(json_str)

        except Exception as e:
            logger.error(f"AI 의사결정 실패: {e}")
            return {"error": str(e), "can_proceed": False}

    async def _execute_action(self, action: Dict[str, Any]) -> bool:
        """AI가 결정한 행동 실행"""
        action_type = action.get("type")
        coords = action.get("coords")
        value = action.get("value")

        if action_type == "click" and coords:
            await self._click_at(coords[0], coords[1])
            logger.info(f"클릭: ({coords[0]}, {coords[1]})")
            return True

        elif action_type == "input" and coords and value:
            await self._click_at(coords[0], coords[1])
            await asyncio.sleep(0.2)
            await self._type_text(value)
            logger.info(f"입력: {value[:30]}...")
            return True

        elif action_type == "wait":
            wait_time = action.get("duration", 1.0)
            await asyncio.sleep(wait_time)
            return True

        elif action_type == "escape":
            await self._press_escape()
            return True

        elif action_type == "scroll":
            direction = action.get("direction", "down")
            await self._scroll(direction)
            return True

        return False

    async def _click_at(self, x: float, y: float):
        """좌표 클릭"""
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved", "x": x, "y": y
        })
        await asyncio.sleep(0.05)
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed", "x": x, "y": y,
            "button": "left", "clickCount": 1
        })
        await asyncio.sleep(0.05)
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased", "x": x, "y": y,
            "button": "left", "clickCount": 1
        })

    async def _type_text(self, text: str, delay_ms: int = 18):
        """텍스트 입력 (Browser-Use 방식)"""
        for char in text:
            if char == '\n':
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Enter",
                    "code": "Enter", "windowsVirtualKeyCode": 13
                })
                await asyncio.sleep(0.001)
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "char", "text": "\r", "key": "Enter"
                })
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Enter",
                    "code": "Enter", "windowsVirtualKeyCode": 13
                })
            else:
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": char
                })
                await asyncio.sleep(0.001)
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "char", "text": char, "key": char
                })
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": char
                })
            await asyncio.sleep(delay_ms / 1000)

    async def _press_escape(self):
        """ESC 키"""
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "Escape",
            "code": "Escape", "windowsVirtualKeyCode": 27
        })
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Escape",
            "code": "Escape", "windowsVirtualKeyCode": 27
        })

    async def _scroll(self, direction: str = "down", amount: int = 300):
        """스크롤"""
        delta_y = amount if direction == "down" else -amount
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseWheel", "x": 500, "y": 400,
            "deltaX": 0, "deltaY": delta_y
        })

    async def _dismiss_temp_save_popup(self) -> bool:
        """임시저장 팝업 닫기"""
        popup_info = await self._evaluate_js("""
            (() => {
                const popups = document.querySelectorAll('.se-popup-alert, .se-popup, [class*="popup"]');
                for (const popup of popups) {
                    const text = popup.innerText || '';
                    if (text.includes('작성 중인 글') || text.includes('임시저장')) {
                        const buttons = popup.querySelectorAll('button');
                        for (const btn of buttons) {
                            const btnText = btn.innerText?.trim() || '';
                            if (btnText === '취소') {
                                const rect = btn.getBoundingClientRect();
                                return {
                                    found: true,
                                    coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                                };
                            }
                        }
                    }
                }
                return { found: false };
            })()
        """)
        if popup_info and popup_info.get("found"):
            await self._click_at(*popup_info["coords"])
            await asyncio.sleep(0.3)
            logger.info("임시저장 팝업 닫음")
            return True
        return False

    async def _evaluate_js(self, expression: str) -> Any:
        """JavaScript 평가"""
        result = await self.cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("value")

    async def _smart_click(self, task: str) -> bool:
        """AI 기반 스마트 클릭

        DOM 정보를 먼저 확인하고, 없으면 AI에게 물어봄
        """
        # 1. DOM에서 먼저 찾기
        dom = await self._get_dom_snapshot()

        # 작업별 매핑
        task_to_dom_key = {
            "이미지": "image",
            "글감": "material",
            "인용구": "quotation",
            "구분선": "horizontal-line",
            "볼드": "bold",
            "발행": "publish"
        }

        for keyword, dom_key in task_to_dom_key.items():
            if keyword in task:
                tool_info = dom.get("toolbar", {}).get(dom_key)
                if tool_info and tool_info.get("found"):
                    coords = tool_info.get("coords")
                    if coords:
                        await self._click_at(coords[0], coords[1])
                        logger.info(f"DOM 기반 클릭: {dom_key} @ {coords}")
                        return True

        # 2. DOM에서 못 찾으면 AI에게 물어봄
        state = await self._analyze_current_state(task)
        ai_decision = state.get("ai_decision", {})

        if ai_decision.get("can_proceed"):
            next_action = ai_decision.get("next_action", {})
            return await self._execute_action(next_action)

        logger.warning(f"작업 수행 불가: {ai_decision.get('blockers')}")
        return False

    async def publish(
        self,
        title: str,
        sections: List[Dict[str, Any]]
    ) -> PublishResult:
        """
        적응형 블로그 발행

        Args:
            title: 블로그 제목
            sections: 콘텐츠 섹션 리스트

        Returns:
            PublishResult
        """
        screenshots = []

        try:
            await self._init_browser()

            # 글쓰기 페이지 이동
            write_url = f"https://blog.naver.com/{self.config.blog_id}/postwrite"
            await self.page.goto(write_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            screenshots.append(await self._save_screenshot("01_initial"))

            # 임시저장 팝업 처리 (여러 번 시도)
            for _ in range(3):
                dismissed = await self._dismiss_temp_save_popup()
                if not dismissed:
                    break
                await asyncio.sleep(0.3)

            # 초기 상태 분석
            state = await self._analyze_current_state("에디터 페이지 진입")
            logger.info(f"페이지 타입: {state.get('dom', {}).get('title', 'unknown')}")

            # 추가 팝업 처리
            if state.get("dom", {}).get("modals"):
                logger.info("팝업 감지 - 처리 중...")
                await self._dismiss_temp_save_popup()
                await asyncio.sleep(0.3)

            # 제목 입력
            logger.info("제목 입력 중...")
            title_info = state.get("dom", {}).get("editor", {}).get("title")
            if title_info and title_info.get("coords"):
                await self._click_at(*title_info["coords"])
                await asyncio.sleep(0.3)
                await self._type_text(title)
            else:
                # AI에게 물어봄
                await self._smart_click("제목 입력 영역 클릭")
                await self._type_text(title)

            screenshots.append(await self._save_screenshot("02_title"))

            # 본문으로 이동
            logger.info("본문으로 이동...")
            body_info = state.get("dom", {}).get("editor", {}).get("body")
            if body_info and body_info.get("coords"):
                await self._click_at(*body_info["coords"])
            else:
                await self._smart_click("본문 영역 클릭")

            await asyncio.sleep(0.5)

            # 팝업 다시 확인 후 처리
            await self._dismiss_temp_save_popup()

            # 섹션별 처리
            for i, section in enumerate(sections):
                section_type = section.get("type", "text")
                logger.info(f"섹션 {i+1}/{len(sections)}: {section_type}")

                if section_type == "text":
                    content = section.get("content", "")
                    formats = section.get("format", [])

                    for fmt in formats:
                        await self._smart_click(f"{fmt} 버튼")
                        await asyncio.sleep(0.2)

                    await self._type_text(content)

                    for fmt in formats:
                        await self._smart_click(f"{fmt} 버튼")

                    await self._type_text("\n\n")

                elif section_type == "image":
                    # 이미지 업로드 (링크 포함 가능)
                    file_path = section.get("path")
                    link_url = section.get("link") or section.get("url")

                    if file_path and Path(file_path).exists():
                        if link_url:
                            # 이미지 + 링크
                            await self._handle_image_with_link(file_path, link_url)
                        else:
                            # 이미지만
                            await self._handle_image_upload(file_path)

                        if section.get("caption"):
                            await self._type_text(f"\n{section['caption']}\n")

                elif section_type == "oglink" or section_type == "link":
                    # 링크 삽입 (하이퍼링크)
                    url = section.get("url")
                    link_text = section.get("text") or section.get("link_text")
                    if url:
                        await self._handle_oglink(url, link_text)

                elif section_type == "quote":
                    await self._smart_click("인용구 버튼")
                    await asyncio.sleep(0.3)
                    await self._type_text(section.get("content", ""))
                    await self._type_text("\n")

                elif section_type == "divider":
                    await self._smart_click("구분선 버튼")
                    await asyncio.sleep(0.3)

            screenshots.append(await self._save_screenshot("03_content"))

            # 발행 프로세스
            logger.info("발행 버튼 클릭...")
            await self._click_publish_button()
            await asyncio.sleep(2)

            screenshots.append(await self._save_screenshot("04_publish_panel"))

            # 최종 발행 버튼 클릭
            logger.info("최종 발행 버튼 클릭...")
            await self._click_final_publish_button()

            await asyncio.sleep(5)

            screenshots.append(await self._save_screenshot("05_published"))

            # URL 확인
            current_url = self.page.url
            if "PostView" in current_url or "logNo" in current_url:
                return PublishResult(
                    success=True,
                    blog_url=current_url,
                    screenshots=screenshots
                )

            return PublishResult(
                success=False,
                error_message="발행 후 URL 확인 실패",
                screenshots=screenshots
            )

        except Exception as e:
            logger.error(f"발행 실패: {e}")
            import traceback
            traceback.print_exc()
            return PublishResult(
                success=False,
                error_message=str(e),
                screenshots=screenshots
            )

        finally:
            await self._close_browser()

    async def _handle_image_upload(self, file_path: str) -> bool:
        """이미지 업로드 처리 (expect_file_chooser 방식)

        네이버 에디터의 이미지 버튼은 OS 파일 다이얼로그를 직접 열기 때문에
        Playwright의 expect_file_chooser를 사용하여 파일 다이얼로그를 인터셉트합니다.

        Args:
            file_path: 업로드할 이미지 파일 경로

        Returns:
            성공 여부
        """
        # 파일 존재 확인
        abs_path = str(Path(file_path).absolute())
        if not Path(abs_path).exists():
            logger.error(f"이미지 파일이 존재하지 않음: {abs_path}")
            return False

        # 이미지 버튼 좌표 찾기
        image_btn = await self._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="image"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                }
                return { found: false };
            })()
        """)

        if not image_btn or not image_btn.get("found"):
            logger.warning("이미지 버튼을 찾을 수 없음")
            return False

        try:
            # expect_file_chooser로 파일 다이얼로그 인터셉트
            async with self.page.expect_file_chooser(timeout=5000) as fc_info:
                await self._click_at(*image_btn["coords"])
                logger.info(f"이미지 버튼 클릭: {image_btn['coords']}")

            file_chooser = await fc_info.value
            await file_chooser.set_files(abs_path)
            logger.info(f"이미지 파일 선택 완료: {abs_path}")

            # 업로드 완료 대기
            await asyncio.sleep(3)

            # 업로드 성공 확인
            image_check = await self._evaluate_js("""
                (() => {
                    const imageComponents = document.querySelectorAll('.se-component.se-image, .se-image-resource');
                    return { count: imageComponents.length, found: imageComponents.length > 0 };
                })()
            """)

            if image_check and image_check.get("found"):
                logger.info(f"이미지 업로드 성공 (에디터 내 이미지: {image_check.get('count')}개)")
                return True
            else:
                logger.warning("이미지 업로드 후 에디터에서 이미지를 찾을 수 없음")
                return True  # 파일은 선택되었으므로 True 반환

        except Exception as e:
            logger.error(f"이미지 업로드 실패: {e}")
            return False

    async def _add_link_to_image(self, link_url: str) -> bool:
        """현재 선택된 이미지에 링크 추가

        이미지가 이미 선택된 상태에서 호출해야 합니다.
        이미지 선택 시 나타나는 프로퍼티 툴바의 image-link 버튼을 사용합니다.

        Args:
            link_url: 이미지 클릭 시 이동할 URL

        Returns:
            성공 여부
        """
        # 1. image-link 버튼 찾기
        image_link_btn = await self._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="image-link"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            found: true,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        };
                    }
                }
                return { found: false };
            })()
        """)

        if not image_link_btn or not image_link_btn.get("found"):
            logger.warning("image-link 버튼을 찾을 수 없음 - 이미지가 선택되지 않았을 수 있음")
            return False

        # 2. image-link 버튼 클릭
        await self._click_at(*image_link_btn["coords"])
        logger.info(f"image-link 버튼 클릭: {image_link_btn['coords']}")
        await asyncio.sleep(0.5)

        # 3. URL 입력 필드 찾기
        url_input = await self._evaluate_js("""
            (() => {
                // URL 입력 필드 찾기 (type="url" 또는 placeholder에 URL 포함)
                const inputs = document.querySelectorAll('input[type="url"], input[placeholder*="URL"], input[placeholder*="http"]');
                for (const input of inputs) {
                    const rect = input.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 0) {
                        return {
                            found: true,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        };
                    }
                }

                // 레이어 내 input 찾기
                const layers = document.querySelectorAll('.se-custom-layer, .se-layer, [class*="link-layer"]');
                for (const layer of layers) {
                    const rect = layer.getBoundingClientRect();
                    const style = getComputedStyle(layer);
                    if (rect.width > 50 && style.display !== 'none') {
                        const input = layer.querySelector('input');
                        if (input) {
                            const inputRect = input.getBoundingClientRect();
                            if (inputRect.width > 50) {
                                return {
                                    found: true,
                                    coords: [inputRect.x + inputRect.width/2, inputRect.y + inputRect.height/2]
                                };
                            }
                        }
                    }
                }

                return { found: false };
            })()
        """)

        if not url_input or not url_input.get("found"):
            logger.warning("이미지 링크 URL 입력 필드를 찾을 수 없음")
            await self._press_escape()
            return False

        # 4. URL 입력
        await self._click_at(*url_input["coords"])
        await asyncio.sleep(0.1)

        # 기존 내용 지우기
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "a", "code": "KeyA",
            "modifiers": 2  # Ctrl
        })
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "a", "code": "KeyA"
        })
        await asyncio.sleep(0.05)

        # URL 입력
        await self._type_text(link_url)
        await asyncio.sleep(0.3)

        # 5. Enter 키로 확인
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "Enter",
            "code": "Enter", "windowsVirtualKeyCode": 13
        })
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "Enter",
            "code": "Enter", "windowsVirtualKeyCode": 13
        })
        await asyncio.sleep(0.5)

        logger.info(f"이미지 링크 추가 완료: {link_url}")
        return True

    async def _handle_image_with_link(self, file_path: str, link_url: str) -> bool:
        """이미지 업로드 후 링크 추가

        Args:
            file_path: 업로드할 이미지 파일 경로
            link_url: 이미지 클릭 시 이동할 URL

        Returns:
            성공 여부
        """
        # 1. 이미지 업로드
        upload_result = await self._handle_image_upload(file_path)
        if not upload_result:
            return False

        # 2. 업로드된 이미지 클릭하여 선택
        await asyncio.sleep(0.5)

        image_element = await self._evaluate_js("""
            (() => {
                // 최근 추가된 이미지 컴포넌트 찾기
                const images = document.querySelectorAll('.se-component.se-image');
                if (images.length > 0) {
                    // 마지막 이미지 선택
                    const lastImage = images[images.length - 1];
                    const rect = lastImage.getBoundingClientRect();
                    return {
                        found: true,
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                    };
                }

                // 대체: img 태그로 찾기
                const imgTags = document.querySelectorAll('.se-image-resource img');
                if (imgTags.length > 0) {
                    const lastImg = imgTags[imgTags.length - 1];
                    const rect = lastImg.getBoundingClientRect();
                    return {
                        found: true,
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                    };
                }

                return { found: false };
            })()
        """)

        if not image_element or not image_element.get("found"):
            logger.warning("업로드된 이미지를 찾을 수 없음")
            return False

        # 이미지 클릭하여 선택
        await self._click_at(*image_element["coords"])
        logger.info(f"이미지 선택: {image_element['coords']}")
        await asyncio.sleep(0.5)

        # 3. 이미지에 링크 추가
        return await self._add_link_to_image(link_url)

    async def _handle_oglink(self, url: str, link_text: str = None) -> bool:
        """링크 삽입 처리 - text-link 버튼 사용 (하이퍼링크)

        네이버 에디터의 링크 삽입 방법:
        text-link 버튼 클릭 후 URL 입력 방식을 사용합니다.

        Args:
            url: 링크할 URL
            link_text: 링크 텍스트 (없으면 URL 자체를 텍스트로 사용)
        """
        display_text = link_text or url

        # 0. 먼저 일반 텍스트 컨텍스트로 이동 (인용구 등에서 벗어나기)
        # ESC로 현재 컨텍스트 해제 후 본문 클릭
        await self._press_escape()
        await asyncio.sleep(0.2)

        # 본문 영역 클릭하여 일반 텍스트 모드로
        body_click = await self._evaluate_js("""
            (() => {
                // 일반 텍스트 영역 찾기 (인용구 외부)
                const textParagraphs = document.querySelectorAll('.se-component.se-text .se-text-paragraph');
                for (const p of textParagraphs) {
                    const rect = p.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 0) {
                        return { found: true, coords: [rect.x + 50, rect.y + rect.height + 10] };
                    }
                }
                // 에디터 본문 영역
                const editor = document.querySelector('.se-content, .se-component-content');
                if (editor) {
                    const rect = editor.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height - 50] };
                }
                return { found: false };
            })()
        """)

        if body_click and body_click.get("found"):
            await self._click_at(*body_click["coords"])
            await asyncio.sleep(0.3)

        # 1. 링크 텍스트 입력
        await self._type_text(display_text)
        await asyncio.sleep(0.3)

        # 2. text-link 버튼 찾기 (세컨더리 툴바)
        textlink_info = await self._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="text-link"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        return {
                            found: true,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        };
                    }
                }
                return { found: false };
            })()
        """)

        if not textlink_info or not textlink_info.get("found"):
            logger.warning("text-link 버튼을 찾을 수 없음")
            await self._type_text("\n")
            return False

        # 3. text-link 버튼 클릭
        await self._click_at(*textlink_info["coords"])
        logger.info(f"text-link 버튼 클릭: {textlink_info['coords']}")
        await asyncio.sleep(0.5)

        # 4. URL 입력 필드 찾기 (placeholder로 찾기)
        url_input = await self._evaluate_js("""
            (() => {
                // URL 입력 필드 직접 찾기
                const inputs = document.querySelectorAll('input[type="url"], input[placeholder*="URL"]');
                for (const input of inputs) {
                    const rect = input.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 0) {
                        return {
                            found: true,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        };
                    }
                }
                return { found: false };
            })()
        """)

        if url_input and url_input.get("found"):
            # 6. URL 입력
            await self._click_at(*url_input["coords"])
            await asyncio.sleep(0.1)

            # 기존 내용 지우고 URL 입력
            await self.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "a", "code": "KeyA",
                "modifiers": 2  # Ctrl
            })
            await self.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "a", "code": "KeyA"
            })
            await asyncio.sleep(0.05)

            await self._type_text(url)
            await asyncio.sleep(0.3)

            # 7. Enter 키로 확인
            await self.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "Enter",
                "code": "Enter", "windowsVirtualKeyCode": 13
            })
            await self.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "Enter",
                "code": "Enter", "windowsVirtualKeyCode": 13
            })
            await asyncio.sleep(0.5)

            logger.info(f"링크 삽입 완료: {display_text} -> {url}")

            # 링크 뒤로 커서 이동 후 줄바꿈
            await self.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "End", "code": "End"
            })
            await self.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "End", "code": "End"
            })
            await self._type_text("\n")
            return True

        logger.warning("URL 입력 필드를 찾을 수 없음")
        await self._press_escape()
        await self._type_text("\n")
        return False

    async def _click_publish_button(self) -> bool:
        """헤더의 발행 버튼 클릭"""
        publish_btn = await self._evaluate_js("""
            (() => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.innerText?.trim() === '발행') {
                        const rect = btn.getBoundingClientRect();
                        // 헤더 영역의 발행 버튼 (y < 100)
                        if (rect.y < 100) {
                            return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                        }
                    }
                }
                return { found: false };
            })()
        """)

        if publish_btn and publish_btn.get("found"):
            await self._click_at(*publish_btn["coords"])
            logger.info(f"발행 버튼 클릭: {publish_btn['coords']}")
            return True

        logger.warning("발행 버튼을 찾을 수 없음")
        return False

    async def _click_final_publish_button(self) -> bool:
        """발행 패널의 최종 발행 버튼 클릭

        발행 패널이 열린 후 우측 하단의 녹색 발행 버튼을 클릭합니다.
        """
        final_publish = await self._evaluate_js("""
            (() => {
                const allBtns = document.querySelectorAll('button');
                let candidates = [];

                for (const btn of allBtns) {
                    const text = btn.innerText?.trim() || '';
                    const rect = btn.getBoundingClientRect();

                    // "발행" 텍스트를 포함하고, 화면 우측(x > 1000)이며 헤더 아래(y > 100)
                    if (text.includes('발행') && rect.x > 1000 && rect.y > 100) {
                        candidates.push({
                            text: text,
                            x: rect.x,
                            y: rect.y,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        });
                    }
                }

                // y 좌표가 가장 큰 것 (가장 아래쪽) 선택
                if (candidates.length > 0) {
                    candidates.sort((a, b) => b.y - a.y);
                    return { found: true, ...candidates[0] };
                }

                return { found: false };
            })()
        """)

        if final_publish and final_publish.get("found"):
            await self._click_at(*final_publish["coords"])
            logger.info(f"최종 발행 버튼 클릭: {final_publish['coords']}")
            return True

        logger.warning("최종 발행 버튼을 찾을 수 없음")
        return False


async def adaptive_publish(
    title: str,
    sections: List[Dict[str, Any]],
    config: PublishConfig
) -> PublishResult:
    """
    적응형 발행 헬퍼 함수

    사용 예시:
        result = await adaptive_publish(
            title="테스트 포스트",
            sections=[
                {"type": "text", "content": "안녕하세요"},
                {"type": "image", "path": "/path/to/img.jpg"},
                {"type": "oglink", "url": "https://naver.com"}
            ],
            config=PublishConfig(
                blog_id="myblog",
                deepseek_api_key="sk-..."
            )
        )
    """
    publisher = AdaptivePublisher(config)
    return await publisher.publish(title, sections)
