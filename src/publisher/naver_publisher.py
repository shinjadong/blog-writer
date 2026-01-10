"""
네이버 블로그 자동 발행기 - CDP 기반

CDP(Chrome DevTools Protocol)를 사용하여 네이버 블로그에 원고를 자동 발행합니다.
- Browser-Use 방식의 정확한 키 입력 (keyDown → char → keyUp)
- 클릭 기반 포커스 관리
- 고급 서식 도구 지원 (인용구, 구분선, 링크, 폰트 등)

Author: CareOn Blog Writer
Created: 2026-01-10
"""

import asyncio
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger("blog_writer.publisher")


class FormatType(Enum):
    """서식 유형"""
    BOLD = "bold"
    ITALIC = "italic"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    QUOTE = "quotation"
    DIVIDER = "horizontal-line"
    LINK = "text-link"
    FONT_SIZE = "font-size"
    FONT_COLOR = "font-color"
    ALIGN = "align"
    LIST = "list"


@dataclass
class EditorToolPositions:
    """에디터 도구 위치 (동적 탐색 결과)"""
    # 상단 컴포넌트 툴바
    quote: tuple = (232, 64)
    divider: tuple = (282, 64)
    oglink: tuple = (337, 74)
    image: tuple = (36, 74)

    # 하단 서식 툴바
    bold: tuple = (270, 122)
    italic: tuple = (295, 122)
    underline: tuple = (323, 122)
    strikethrough: tuple = (351, 122)
    font_size: tuple = (202, 122)
    font_color: tuple = (379, 122)
    align: tuple = (457, 122)
    list: tuple = (513, 122)
    link: tuple = (675, 122)


@dataclass
class PublishResult:
    """발행 결과"""
    success: bool
    blog_url: Optional[str] = None
    post_id: Optional[str] = None
    error_message: Optional[str] = None
    published_at: Optional[datetime] = None
    screenshots: List[str] = field(default_factory=list)


@dataclass
class PublishConfig:
    """발행 설정"""
    blog_id: str  # 네이버 블로그 ID
    category: str = ""  # 카테고리 이름
    tags: List[str] = field(default_factory=list)
    is_public: bool = True

    # CDP 연결 설정
    cdp_url: str = "http://localhost:9222"

    # 디버그
    headless: bool = False  # CDP 연결 시 headless는 의미 없음
    screenshot_on_error: bool = True
    screenshot_dir: str = "data/publish_screenshots"


class NaverPublisher:
    """
    네이버 블로그 자동 발행기 (CDP 기반)

    CDP(Chrome DevTools Protocol)를 사용하여 네이버 스마트에디터를 제어합니다.
    Browser-Use 라이브러리의 입력 방식을 적용하여 안정적인 텍스트 입력을 보장합니다.

    지원 기능:
    - 제목/본문 입력
    - 인용구 삽입
    - 구분선 삽입
    - 링크 추가
    - 볼드/이탤릭/밑줄 서식
    - 폰트 크기/색상 변경

    사용 예시:
        publisher = NaverPublisher()
        result = await publisher.publish(
            title="블로그 제목",
            content="블로그 내용",
            config=PublishConfig(
                blog_id="myblog",
                cdp_url="http://localhost:9222"
            )
        )
        print(result.blog_url)
    """

    NAVER_BLOG_WRITE_URL = "https://blog.naver.com/{blog_id}/postwrite"
    NAVER_BLOG_URL = "https://blog.naver.com/{blog_id}"

    def __init__(self):
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cdp = None
        self._playwright = None
        self.tool_positions = EditorToolPositions()

    async def _get_cdp_session(self):
        """Playwright 페이지에서 CDP 세션 획득"""
        if not self.page:
            raise RuntimeError("Page not initialized")
        self.cdp = await self.page.context.new_cdp_session(self.page)
        await self.cdp.send("DOM.enable")
        await self.cdp.send("Runtime.enable")
        return self.cdp

    async def _evaluate_js(self, expression: str) -> Any:
        """JavaScript 평가"""
        result = await self.cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("value")

    async def _click_at(self, x: float, y: float):
        """좌표에 마우스 클릭"""
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseMoved",
            "x": x,
            "y": y
        })
        await asyncio.sleep(0.05)
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mousePressed",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": 1
        })
        await asyncio.sleep(0.05)
        await self.cdp.send("Input.dispatchMouseEvent", {
            "type": "mouseReleased",
            "x": x,
            "y": y,
            "button": "left",
            "clickCount": 1
        })

    async def _type_text(self, text: str, delay_ms: int = 18):
        """CDP를 통해 텍스트 입력 (Browser-Use 방식)

        핵심: keyDown에는 text 없음, char에만 text 있음
        """
        for char in text:
            if char == '\n':
                # Enter 키
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown",
                    "key": "Enter",
                    "code": "Enter",
                    "windowsVirtualKeyCode": 13
                })
                await asyncio.sleep(0.001)
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "char",
                    "text": "\r",
                    "key": "Enter"
                })
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp",
                    "key": "Enter",
                    "code": "Enter",
                    "windowsVirtualKeyCode": 13
                })
            else:
                # 일반 문자 - keyDown에는 text 없음!
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown",
                    "key": char
                })
                await asyncio.sleep(0.001)
                # char 이벤트에만 text
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "char",
                    "text": char,
                    "key": char
                })
                await self.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp",
                    "key": char
                })

            await asyncio.sleep(delay_ms / 1000)

    async def _find_element_by_selector(self, selector: str) -> Optional[Dict]:
        """CSS 셀렉터로 요소의 BackendNodeId 찾기"""
        doc = await self.cdp.send("DOM.getDocument")
        root_id = doc["root"]["nodeId"]

        result = await self.cdp.send("DOM.querySelector", {
            "nodeId": root_id,
            "selector": selector
        })

        if result.get("nodeId", 0) == 0:
            return None

        node_info = await self.cdp.send("DOM.describeNode", {
            "nodeId": result["nodeId"]
        })

        return {
            "nodeId": result["nodeId"],
            "backendNodeId": node_info["node"]["backendNodeId"]
        }

    async def _click_element(self, backend_node_id: int) -> bool:
        """BackendNodeId로 요소 클릭"""
        try:
            await self.cdp.send("DOM.scrollIntoViewIfNeeded", {
                "backendNodeId": backend_node_id
            })
            await asyncio.sleep(0.1)
        except:
            pass

        try:
            quads = await self.cdp.send("DOM.getContentQuads", {
                "backendNodeId": backend_node_id
            })

            if quads.get("quads") and len(quads["quads"]) > 0:
                quad = quads["quads"][0]
                center_x = sum(quad[i] for i in range(0, 8, 2)) / 4
                center_y = sum(quad[i] for i in range(1, 8, 2)) / 4
                await self._click_at(center_x, center_y)
                return True
        except Exception as e:
            logger.debug(f"좌표 클릭 실패: {e}")

        # JavaScript 폴백
        try:
            result = await self.cdp.send("DOM.resolveNode", {
                "backendNodeId": backend_node_id
            })
            object_id = result["object"]["objectId"]

            await self.cdp.send("Runtime.callFunctionOn", {
                "functionDeclaration": "function() { this.click(); }",
                "objectId": object_id
            })
            return True
        except Exception as e:
            logger.debug(f"JS 클릭 실패: {e}")
            return False

    async def _focus_element(self, backend_node_id: int) -> bool:
        """요소에 포커스"""
        try:
            result = await self.cdp.send("DOM.resolveNode", {
                "backendNodeId": backend_node_id
            })
            object_id = result["object"]["objectId"]

            await self.cdp.send("Runtime.callFunctionOn", {
                "functionDeclaration": "function() { this.focus(); }",
                "objectId": object_id
            })
            return True
        except Exception as e:
            logger.debug(f"포커스 실패: {e}")
            return False

    async def _click_tool(self, data_name: str) -> bool:
        """data-name 속성으로 도구 버튼 클릭"""
        btn_info = await self._evaluate_js(f"""
            (() => {{
                const btn = document.querySelector('[data-name="{data_name}"]');
                if (btn) {{
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0) {{
                        return {{ x: rect.x + rect.width/2, y: rect.y + rect.height/2 }};
                    }}
                }}
                return null;
            }})()
        """)

        if btn_info:
            await self._click_at(btn_info['x'], btn_info['y'])
            return True
        return False

    async def _discover_tool_positions(self):
        """도구 위치 동적 탐색"""
        positions = await self._evaluate_js("""
            (() => {
                const findTool = (dataName) => {
                    const btn = document.querySelector(`[data-name="${dataName}"]`);
                    if (btn) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {
                            return { x: rect.x + rect.width/2, y: rect.y + rect.height/2 };
                        }
                    }
                    return null;
                };

                return {
                    quote: findTool('quotation') || findTool('insert-quotation'),
                    divider: findTool('horizontal-line') || findTool('insert-horizontal-line'),
                    oglink: findTool('oglink'),
                    bold: findTool('bold'),
                    italic: findTool('italic'),
                    underline: findTool('underline'),
                    strikethrough: findTool('strikethrough'),
                    fontSize: findTool('font-size'),
                    fontColor: findTool('font-color'),
                    align: findTool('align'),
                    list: findTool('list'),
                    link: findTool('text-link')
                };
            })()
        """)

        if positions:
            if positions.get('quote'):
                self.tool_positions.quote = (positions['quote']['x'], positions['quote']['y'])
            if positions.get('divider'):
                self.tool_positions.divider = (positions['divider']['x'], positions['divider']['y'])
            # ... 나머지 도구들도 업데이트

    async def _find_body_element(self) -> Optional[Dict]:
        """본문 영역 요소 찾기 (제목 제외)"""
        result = await self._evaluate_js("""
            (() => {
                const paragraphs = document.querySelectorAll('.se-text-paragraph');
                const titleArea = document.querySelector('.se-documentTitle');

                for (const p of paragraphs) {
                    if (titleArea && titleArea.contains(p)) continue;

                    const rect = p.getBoundingClientRect();
                    return {
                        found: true,
                        selector: '.se-component.se-text .se-text-paragraph',
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                    };
                }

                return { found: false };
            })()
        """)
        return result

    async def _capture_state(self, step_name: str, config: PublishConfig) -> Dict:
        """현재 상태 캡처"""
        timestamp = datetime.now().strftime("%H%M%S")
        screenshot_dir = Path(config.screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)

        screenshot_path = screenshot_dir / f"{timestamp}_{step_name}.png"
        await self.page.screenshot(path=str(screenshot_path))

        state = await self._evaluate_js("""
            (() => {
                const result = { title: '', body: '', focusedIn: 'unknown' };

                const titleEl = document.querySelector('.se-title-text');
                if (titleEl) result.title = titleEl.innerText || '';

                const paragraphs = document.querySelectorAll('.se-text-paragraph');
                const titleArea = document.querySelector('.se-documentTitle');
                for (const p of paragraphs) {
                    if (titleArea && titleArea.contains(p)) continue;
                    result.body = p.innerText || '';
                    break;
                }

                const fontBtn = document.querySelector('[data-name="fontSize"]');
                if (fontBtn) {
                    const size = fontBtn.innerText?.trim();
                    result.focusedIn = size === '32' ? 'title' : 'body';
                }

                return result;
            })()
        """)

        logger.info(f"📸 {step_name}: 제목={state.get('title', '')[:30]}, 본문={state.get('body', '')[:30]}")
        return state or {}

    # ==================== 서식 도구 API ====================

    async def insert_quote(self):
        """인용구 삽입"""
        return await self._click_tool("quotation")

    async def insert_divider(self):
        """구분선 삽입"""
        return await self._click_tool("horizontal-line")

    async def apply_bold(self):
        """볼드 적용"""
        return await self._click_tool("bold")

    async def apply_italic(self):
        """이탤릭 적용"""
        return await self._click_tool("italic")

    async def apply_underline(self):
        """밑줄 적용"""
        return await self._click_tool("underline")

    async def insert_link(self, url: str, text: Optional[str] = None):
        """링크 삽입

        1. 텍스트 선택 (있는 경우)
        2. 링크 버튼 클릭
        3. URL 입력
        4. 확인
        """
        # 링크 버튼 클릭
        if not await self._click_tool("text-link"):
            logger.warning("링크 버튼을 찾을 수 없습니다")
            return False

        await asyncio.sleep(0.5)

        # 링크 입력 필드 찾기 (팝업)
        link_input = await self._find_element_by_selector('input[placeholder*="링크"], input[type="url"], .se-link-input input')
        if link_input:
            await self._click_element(link_input["backendNodeId"])
            await asyncio.sleep(0.2)
            await self._type_text(url)

            # 확인 버튼 클릭
            await asyncio.sleep(0.3)
            confirm_btn = await self._evaluate_js("""
                (() => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        if (btn.innerText?.includes('확인') || btn.innerText?.includes('적용')) {
                            const rect = btn.getBoundingClientRect();
                            if (rect.width > 0) {
                                return { x: rect.x + rect.width/2, y: rect.y + rect.height/2 };
                            }
                        }
                    }
                    return null;
                })()
            """)
            if confirm_btn:
                await self._click_at(confirm_btn['x'], confirm_btn['y'])
                return True

        return False

    async def set_font_size(self, size: int):
        """폰트 크기 설정 (11, 13, 15, 18, 24, 28, 32, 40)"""
        # 폰트 크기 드롭다운 클릭
        if not await self._click_tool("font-size"):
            return False

        await asyncio.sleep(0.3)

        # 크기 옵션 클릭
        size_option = await self._evaluate_js(f"""
            (() => {{
                const options = document.querySelectorAll('.se-drop-down-item, [class*="font-size"] li');
                for (const opt of options) {{
                    if (opt.innerText?.trim() === '{size}' || opt.innerText?.includes('{size}')) {{
                        const rect = opt.getBoundingClientRect();
                        if (rect.width > 0) {{
                            return {{ x: rect.x + rect.width/2, y: rect.y + rect.height/2 }};
                        }}
                    }}
                }}
                return null;
            }})()
        """)

        if size_option:
            await self._click_at(size_option['x'], size_option['y'])
            return True

        return False

    # ==================== 메인 발행 메서드 ====================

    async def publish(
        self,
        title: str,
        content: str,
        config: PublishConfig
    ) -> PublishResult:
        """
        블로그 발행 메인 메서드 (CDP 기반)

        Args:
            title: 블로그 제목
            content: 블로그 내용
            config: 발행 설정

        Returns:
            PublishResult 객체
        """
        screenshots = []

        try:
            logger.info(f"Starting publish to blog: {config.blog_id}")

            # CDP 연결로 브라우저 초기화
            await self._init_browser_cdp(config)

            # 글쓰기 페이지로 이동
            write_url = self.NAVER_BLOG_WRITE_URL.format(blog_id=config.blog_id)
            logger.info(f"Navigating to: {write_url}")

            await self.page.goto(write_url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # 로그인 상태 확인
            if not await self._check_login_status():
                return PublishResult(
                    success=False,
                    error_message="로그인이 필요합니다. Chrome이 로그인된 상태로 실행되어야 합니다."
                )

            logger.info("Login status confirmed")

            # 팝업 처리 (임시저장 글 있음 등)
            await self._handle_popup()

            # 도구 위치 동적 탐색
            await self._discover_tool_positions()

            # 스크린샷
            await self._capture_state("01_initial", config)

            # 제목 입력
            await self._enter_title(title)
            logger.info(f"Title entered: {title[:30]}...")

            await self._capture_state("02_title", config)

            # 본문 영역으로 이동
            await self._move_to_body()

            await self._capture_state("03_body_focus", config)

            # 본문 입력
            await self._enter_content(content)
            logger.info("Content entered")

            await self._capture_state("04_content", config)

            # 발행
            blog_url = await self._click_publish()

            await self._capture_state("05_published", config)

            if blog_url:
                post_id = self._extract_post_id(blog_url)

                logger.info(f"Published successfully: {blog_url}")
                return PublishResult(
                    success=True,
                    blog_url=blog_url,
                    post_id=post_id,
                    published_at=datetime.now(),
                    screenshots=screenshots
                )
            else:
                return PublishResult(
                    success=False,
                    error_message="발행 후 URL을 찾을 수 없습니다.",
                    screenshots=screenshots
                )

        except Exception as e:
            logger.error(f"Publish failed: {e}")

            if config.screenshot_on_error and self.page:
                try:
                    screenshot_path = f"{config.screenshot_dir}/error_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                    await self.page.screenshot(path=screenshot_path)
                    screenshots.append(screenshot_path)
                except:
                    pass

            return PublishResult(
                success=False,
                error_message=str(e),
                screenshots=screenshots
            )

        finally:
            await self._close_browser()

    async def _init_browser_cdp(self, config: PublishConfig):
        """CDP로 브라우저 연결"""
        self._playwright = await async_playwright().start()

        try:
            self.browser = await self._playwright.chromium.connect_over_cdp(config.cdp_url)
            logger.info(f"Connected to Chrome via CDP: {config.cdp_url}")
        except Exception as e:
            raise RuntimeError(
                f"CDP 연결 실패: {e}\n"
                "Chrome을 다음 명령으로 실행하세요:\n"
                "google-chrome --remote-debugging-port=9222"
            )

        contexts = self.browser.contexts
        self.context = contexts[0] if contexts else await self.browser.new_context()
        self.page = await self.context.new_page()

        # CDP 세션 획득
        await self._get_cdp_session()

    async def _close_browser(self):
        """브라우저 리소스 정리"""
        try:
            if self.page:
                await self.page.close()
            if self._playwright:
                await self._playwright.stop()
        except:
            pass

    async def _check_login_status(self) -> bool:
        """로그인 상태 확인"""
        try:
            current_url = self.page.url

            if "nid.naver.com" in current_url or "login" in current_url.lower():
                return False

            # 에디터 로드 확인
            editor = await self._evaluate_js("""
                document.querySelector('.se-content, .se-documentTitle') !== null
            """)

            return editor or "postwrite" in current_url

        except Exception as e:
            logger.error(f"Login check failed: {e}")
            return False

    async def _handle_popup(self):
        """팝업 처리 (임시저장 글 복원 등)"""
        try:
            popup = await self._find_element_by_selector('.se-popup-alert-confirm button')
            if popup:
                # '취소' 버튼 클릭 (새로 시작)
                cancel_btn = await self._find_element_by_selector('.se-popup-alert-confirm button:first-child')
                if cancel_btn:
                    await self._click_element(cancel_btn["backendNodeId"])
                    logger.info("임시저장 팝업 닫기")
                    await asyncio.sleep(1)
        except:
            pass

    async def _enter_title(self, title: str):
        """제목 입력"""
        title_el = await self._find_element_by_selector('.se-documentTitle .se-text-paragraph')
        if not title_el:
            title_el = await self._find_element_by_selector('.se-title-text')

        if title_el:
            await self._click_element(title_el["backendNodeId"])
            await asyncio.sleep(0.3)
            await self._focus_element(title_el["backendNodeId"])
            await asyncio.sleep(0.3)

            await self._type_text(title, delay_ms=30)
            logger.info(f"제목 입력 완료: {title[:30]}...")
        else:
            raise RuntimeError("제목 영역을 찾을 수 없습니다")

    async def _move_to_body(self):
        """본문 영역으로 포커스 이동"""
        body_info = await self._find_body_element()

        if body_info and body_info.get('found'):
            rect = body_info.get('rect', {})
            x = rect.get('x', 700) + 50
            y = rect.get('y', 400) + 20

            logger.debug(f"본문 영역 클릭: ({x:.0f}, {y:.0f})")
            await self._click_at(x, y)
        else:
            # 본문 요소 직접 클릭
            body_el = await self._find_element_by_selector('.se-component.se-text .se-text-paragraph')
            if body_el:
                await self._click_element(body_el["backendNodeId"])
            else:
                # 고정 좌표 폴백
                await self._click_at(700, 400)

        await asyncio.sleep(1)

        # 포커스 확인
        state = await self._evaluate_js("""
            (() => {
                const fontBtn = document.querySelector('[data-name="fontSize"]');
                if (fontBtn) {
                    return fontBtn.innerText?.trim();
                }
                return null;
            })()
        """)

        if state == '32':  # 아직 제목 영역
            logger.warning("아직 제목에 포커스! 재시도...")
            await self._click_at(700, 450)
            await asyncio.sleep(0.5)

    async def _enter_content(self, content: str):
        """본문 입력"""
        # 마크다운을 일반 텍스트로 변환
        plain_content = self._markdown_to_plain(content)

        # 문단별로 입력
        paragraphs = plain_content.split('\n\n')
        for i, para in enumerate(paragraphs):
            if not para.strip():
                continue

            await self._type_text(para.strip(), delay_ms=10)

            if i < len(paragraphs) - 1:
                await self._type_text('\n\n', delay_ms=50)

            logger.debug(f"문단 {i+1}/{len(paragraphs)} 입력 완료")

    def _markdown_to_plain(self, markdown: str) -> str:
        """마크다운을 일반 텍스트로 변환"""
        text = markdown

        # 헤딩 제거
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # 볼드/이탤릭 제거
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'__(.+?)__', r'\1', text)
        text = re.sub(r'_(.+?)_', r'\1', text)

        # 링크 텍스트만 남기기
        text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)

        # 이미지 태그 제거
        text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
        text = re.sub(r'\[이미지:.*?\]', '', text)

        # 인용 제거
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

        # 코드 블록 제거
        text = re.sub(r'```[\s\S]*?```', '', text)
        text = re.sub(r'`(.+?)`', r'\1', text)

        # 수평선 제거
        text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)

        # 여러 줄바꿈 정리
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    async def _click_publish(self) -> Optional[str]:
        """발행 버튼 클릭 및 URL 반환"""

        # 1단계: 헤더의 발행 버튼 클릭
        publish_btn = await self._evaluate_js("""
            (() => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.innerText?.trim() === '발행') {
                        const rect = btn.getBoundingClientRect();
                        return { x: rect.x + rect.width/2, y: rect.y + rect.height/2 };
                    }
                }
                return null;
            })()
        """)

        if publish_btn:
            logger.info(f"발행 버튼 클릭: ({publish_btn['x']:.0f}, {publish_btn['y']:.0f})")
            await self._click_at(publish_btn['x'], publish_btn['y'])
        else:
            logger.error("발행 버튼을 찾을 수 없습니다")
            return None

        await asyncio.sleep(2)

        # 2단계: 발행 설정 패널의 최종 발행 버튼 클릭
        final_publish_btn = await self._evaluate_js("""
            (() => {
                const btns = document.querySelectorAll('button');
                let candidates = [];

                for (const btn of btns) {
                    const text = btn.innerText?.trim();
                    if (text === '발행' || text.includes('발행')) {
                        const rect = btn.getBoundingClientRect();
                        candidates.push({
                            x: rect.x + rect.width/2,
                            y: rect.y + rect.height/2,
                            text: text
                        });
                    }
                }

                // y > 300인 버튼만 (패널 내 버튼)
                if (candidates.length > 0) {
                    candidates.sort((a, b) => b.y - a.y);
                    const panelBtn = candidates.find(b => b.y > 300);
                    if (panelBtn) return panelBtn;
                }

                return null;
            })()
        """)

        if final_publish_btn:
            logger.info(f"최종 발행 버튼 클릭: ({final_publish_btn['x']:.0f}, {final_publish_btn['y']:.0f})")
            await self._click_at(final_publish_btn['x'], final_publish_btn['y'])
        else:
            logger.warning("최종 발행 버튼을 찾을 수 없습니다")

        await asyncio.sleep(5)

        # URL 확인
        current_url = self.page.url

        if "PostView" in current_url or "logNo" in current_url:
            return current_url

        # 페이지 이동 대기
        try:
            await self.page.wait_for_url("**/PostView**", timeout=10000)
            return self.page.url
        except:
            pass

        return None

    def _extract_post_id(self, url: str) -> Optional[str]:
        """URL에서 post_id 추출"""
        match = re.search(r'/(\d{10,})', url)
        if match:
            return match.group(1)

        match = re.search(r'logNo=(\d+)', url)
        if match:
            return match.group(1)

        return None

    async def test_connection(self, config: PublishConfig) -> bool:
        """연결 테스트"""
        try:
            await self._init_browser_cdp(config)

            blog_url = self.NAVER_BLOG_URL.format(blog_id=config.blog_id)
            await self.page.goto(blog_url, wait_until="networkidle", timeout=15000)

            write_btn = await self._evaluate_js("""
                document.querySelector('a[href*="postwrite"]') !== null
            """)

            return bool(write_btn)

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
        finally:
            await self._close_browser()


# ==================== 고급 서식 지원 발행 ====================

async def publish_with_formatting(
    title: str,
    sections: List[Dict[str, Any]],
    config: PublishConfig
) -> PublishResult:
    """
    서식 정보가 포함된 콘텐츠 발행

    sections 예시:
    [
        {"type": "text", "content": "서론 내용..."},
        {"type": "quote", "content": "인용구 내용"},
        {"type": "divider"},
        {"type": "text", "content": "본론 내용...", "format": ["bold"]},
        {"type": "link", "text": "참고 링크", "url": "https://..."}
    ]
    """
    publisher = NaverPublisher()

    try:
        await publisher._init_browser_cdp(config)

        write_url = publisher.NAVER_BLOG_WRITE_URL.format(blog_id=config.blog_id)
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        await publisher._handle_popup()
        await publisher._discover_tool_positions()

        # 제목 입력
        await publisher._enter_title(title)

        # 본문으로 이동
        await publisher._move_to_body()

        # 섹션별 입력
        for section in sections:
            section_type = section.get("type", "text")

            if section_type == "text":
                content = section.get("content", "")
                formats = section.get("format", [])

                # 서식 적용
                for fmt in formats:
                    if fmt == "bold":
                        await publisher.apply_bold()
                    elif fmt == "italic":
                        await publisher.apply_italic()
                    elif fmt == "underline":
                        await publisher.apply_underline()

                await publisher._type_text(content)

                # 서식 해제
                for fmt in formats:
                    if fmt == "bold":
                        await publisher.apply_bold()
                    elif fmt == "italic":
                        await publisher.apply_italic()
                    elif fmt == "underline":
                        await publisher.apply_underline()

                await publisher._type_text('\n\n')

            elif section_type == "quote":
                await publisher.insert_quote()
                await asyncio.sleep(0.3)
                await publisher._type_text(section.get("content", ""))
                await publisher._type_text('\n')

            elif section_type == "divider":
                await publisher.insert_divider()
                await asyncio.sleep(0.3)

            elif section_type == "link":
                await publisher.insert_link(
                    url=section.get("url", ""),
                    text=section.get("text")
                )

        # 발행
        blog_url = await publisher._click_publish()

        return PublishResult(
            success=bool(blog_url),
            blog_url=blog_url,
            post_id=publisher._extract_post_id(blog_url) if blog_url else None,
            published_at=datetime.now() if blog_url else None
        )

    except Exception as e:
        logger.error(f"Formatted publish failed: {e}")
        return PublishResult(success=False, error_message=str(e))

    finally:
        await publisher._close_browser()


# ==================== 리치 콘텐츠 발행 (이미지/글감 포함) ====================

async def publish_with_rich_content(
    title: str,
    sections: List[Dict[str, Any]],
    config: PublishConfig
) -> PublishResult:
    """
    리치 콘텐츠 발행 (이미지, 글감, 서식 모두 포함)

    sections 예시:
    [
        {"type": "text", "content": "서론 내용..."},
        {"type": "image", "path": "/path/to/image.jpg", "caption": "이미지 설명"},
        {"type": "quote", "content": "인용구 내용"},
        {"type": "oglink", "url": "https://example.com/article"},
        {"type": "divider"},
        {"type": "text", "content": "볼드 텍스트", "format": ["bold"]},
        {"type": "link", "text": "참고 링크", "url": "https://..."}
    ]

    지원 타입:
    - text: 일반 텍스트 (format 옵션: bold, italic, underline)
    - image: 이미지 업로드 (path: 파일 경로, caption: 설명)
    - quote: 인용구
    - oglink: 글감/링크 카드 (url: 대상 URL)
    - divider: 구분선
    - link: 인라인 링크

    Args:
        title: 블로그 제목
        sections: 콘텐츠 섹션 리스트
        config: 발행 설정

    Returns:
        PublishResult 객체
    """
    from .components import ImageHandler, OGLinkHandler
    from .watchdogs import PopupWatchdog, EditorPopupWatchdog

    publisher = NaverPublisher()

    try:
        await publisher._init_browser_cdp(config)

        write_url = publisher.NAVER_BLOG_WRITE_URL.format(blog_id=config.blog_id)
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # Watchdog 초기화 및 연결
        popup_watchdog = PopupWatchdog(publisher.cdp, publisher.page)
        editor_popup_watchdog = EditorPopupWatchdog(publisher.cdp, publisher.page)
        await popup_watchdog.attach()

        # 팝업 처리 (Watchdog 사용)
        if await editor_popup_watchdog.check_for_popup('temp_save'):
            await editor_popup_watchdog.dismiss_temp_save_popup()
            await asyncio.sleep(0.5)
        else:
            await publisher._handle_popup()

        await publisher._discover_tool_positions()

        # 컴포넌트 핸들러 초기화
        image_handler = ImageHandler(publisher.cdp, publisher.page)
        oglink_handler = OGLinkHandler(publisher.cdp, publisher.page)

        # 제목 입력
        await publisher._enter_title(title)

        # 본문으로 이동
        await publisher._move_to_body()

        # 섹션별 입력
        for i, section in enumerate(sections):
            section_type = section.get("type", "text")
            logger.debug(f"Processing section {i+1}/{len(sections)}: {section_type}")

            if section_type == "text":
                content = section.get("content", "")
                formats = section.get("format", [])

                # 서식 적용
                for fmt in formats:
                    if fmt == "bold":
                        await publisher.apply_bold()
                    elif fmt == "italic":
                        await publisher.apply_italic()
                    elif fmt == "underline":
                        await publisher.apply_underline()

                await publisher._type_text(content)

                # 서식 해제
                for fmt in formats:
                    if fmt == "bold":
                        await publisher.apply_bold()
                    elif fmt == "italic":
                        await publisher.apply_italic()
                    elif fmt == "underline":
                        await publisher.apply_underline()

                await publisher._type_text('\n\n')

            elif section_type == "image":
                # 이미지 업로드
                file_path = section.get("path")
                if file_path:
                    success = await image_handler.upload_image(file_path)
                    if success:
                        logger.info(f"Image uploaded: {file_path}")
                        # 캡션 추가
                        caption = section.get("caption")
                        if caption:
                            await asyncio.sleep(0.5)
                            await publisher._type_text(f"\n{caption}\n")
                    else:
                        logger.warning(f"Failed to upload image: {file_path}")

                await asyncio.sleep(0.5)

            elif section_type == "quote":
                await publisher.insert_quote()
                await asyncio.sleep(0.3)
                await publisher._type_text(section.get("content", ""))
                await publisher._type_text('\n')

            elif section_type == "oglink":
                # 글감(OGLink) 삽입
                url = section.get("url")
                if url:
                    success = await oglink_handler.insert_oglink(url)
                    if success:
                        logger.info(f"OGLink inserted: {url}")
                    else:
                        logger.warning(f"Failed to insert OGLink: {url}")

                await asyncio.sleep(0.5)

            elif section_type == "divider":
                await publisher.insert_divider()
                await asyncio.sleep(0.3)

            elif section_type == "link":
                await publisher.insert_link(
                    url=section.get("url", ""),
                    text=section.get("text")
                )

        # 발행
        blog_url = await publisher._click_publish()

        return PublishResult(
            success=bool(blog_url),
            blog_url=blog_url,
            post_id=publisher._extract_post_id(blog_url) if blog_url else None,
            published_at=datetime.now() if blog_url else None
        )

    except Exception as e:
        logger.error(f"Rich content publish failed: {e}")
        import traceback
        traceback.print_exc()
        return PublishResult(success=False, error_message=str(e))

    finally:
        await publisher._close_browser()
