"""
OGLinkHandler - 네이버 스마트에디터 글감(OGLink) 삽입

URL을 입력하면 Open Graph 메타데이터를 추출하여
링크 카드 형태로 에디터에 삽입합니다.
"""

import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger("blog_writer.oglink_handler")


class OGLinkHandler:
    """
    글감(OGLink) 삽입 핸들러

    네이버 스마트에디터의 글감 기능을 자동화합니다.
    URL을 입력하면 OG 메타데이터를 추출하여 링크 카드를 생성합니다.

    사용 예시:
        handler = OGLinkHandler(cdp_session, page)
        await handler.insert_oglink("https://example.com/article")
    """

    # 글감 버튼 셀렉터
    OGLINK_BUTTON_SELECTOR = '[data-name="oglink"]'

    # 모달 관련 셀렉터
    MODAL_SELECTORS = {
        'popup': '.se-popup',
        'url_input': 'input[type="text"], input[placeholder*="링크"], input[placeholder*="URL"]',
        'confirm_button': 'button',
        'preview': '.se-oglink-preview, .se-link-preview, [class*="preview"]',
    }

    # 버튼 텍스트
    CONFIRM_TEXTS = ['확인', '적용', '추가', 'OK']
    CANCEL_TEXTS = ['취소', '닫기', 'Cancel']

    # 타임아웃 설정
    MODAL_TIMEOUT = 3.0
    PREVIEW_TIMEOUT = 10.0

    def __init__(self, cdp_session, page):
        """
        Args:
            cdp_session: Playwright CDP 세션
            page: Playwright 페이지 객체
        """
        self.cdp = cdp_session
        self.page = page
        self._inserted_count = 0

    async def insert_oglink(self, url: str, wait_for_preview: bool = True) -> bool:
        """글감(OGLink) 삽입

        Args:
            url: 삽입할 URL
            wait_for_preview: OG 프리뷰 로딩 대기 여부

        Returns:
            성공 여부
        """
        if not url or not url.startswith(('http://', 'https://')):
            logger.error(f"Invalid URL: {url}")
            return False

        logger.info(f"Inserting OGLink: {url}")

        try:
            # 1. 글감 버튼 클릭
            if not await self._click_oglink_button():
                logger.error("Failed to click oglink button")
                return False

            await asyncio.sleep(0.5)

            # 2. 모달 대기
            modal = await self._wait_for_modal(timeout=self.MODAL_TIMEOUT)
            if not modal:
                logger.error("OGLink modal not found")
                return False

            logger.debug(f"Modal found: {modal.get('selector')}")

            # 3. URL 입력 필드 찾기 및 입력
            if not await self._enter_url(url):
                logger.error("Failed to enter URL")
                await self._close_modal()
                return False

            # 4. 프리뷰 로딩 대기 (OG 메타데이터 추출)
            if wait_for_preview:
                preview_loaded = await self._wait_for_preview(timeout=self.PREVIEW_TIMEOUT)
                if not preview_loaded:
                    logger.warning("Preview may not have loaded completely")

            await asyncio.sleep(0.5)

            # 5. 확인 버튼 클릭
            if not await self._click_confirm_button():
                logger.error("Failed to click confirm button")
                await self._close_modal()
                return False

            self._inserted_count += 1
            logger.info(f"OGLink inserted successfully. Total: {self._inserted_count}")
            return True

        except Exception as e:
            logger.error(f"OGLink insertion failed: {e}")
            await self._close_modal()
            return False

    async def _click_oglink_button(self) -> bool:
        """글감 버튼 클릭"""
        result = await self._evaluate_js(f"""
            (() => {{
                const btn = document.querySelector('{self.OGLINK_BUTTON_SELECTOR}');
                if (btn) {{
                    const rect = btn.getBoundingClientRect();
                    return {{
                        found: true,
                        x: rect.x + rect.width / 2,
                        y: rect.y + rect.height / 2
                    }};
                }}
                return {{ found: false }};
            }})()
        """)

        if not result or not result.get('found'):
            return False

        await self._click_at(result['x'], result['y'])
        logger.debug("OGLink button clicked")
        return True

    async def _wait_for_modal(self, timeout: float = 3.0) -> Optional[Dict]:
        """모달 출현 대기"""
        import time
        start = time.time()

        while time.time() - start < timeout:
            result = await self._evaluate_js(f"""
                (() => {{
                    const popup = document.querySelector('{self.MODAL_SELECTORS["popup"]}');
                    if (popup) {{
                        const style = getComputedStyle(popup);
                        const rect = popup.getBoundingClientRect();

                        if (rect.width > 100 && rect.height > 50 &&
                            style.display !== 'none' && style.visibility !== 'hidden') {{
                            return {{
                                found: true,
                                selector: '{self.MODAL_SELECTORS["popup"]}',
                                rect: {{ x: rect.x, y: rect.y, w: rect.width, h: rect.height }}
                            }};
                        }}
                    }}
                    return {{ found: false }};
                }})()
            """)

            if result and result.get('found'):
                return result

            await asyncio.sleep(0.2)

        return None

    async def _enter_url(self, url: str) -> bool:
        """URL 입력 필드에 URL 입력"""
        # 모달 내 입력 필드 찾기
        input_info = await self._evaluate_js(f"""
            (() => {{
                const popup = document.querySelector('{self.MODAL_SELECTORS["popup"]}');
                if (!popup) return {{ found: false }};

                // 다양한 셀렉터로 입력 필드 찾기
                const selectors = [
                    'input[type="text"]',
                    'input[placeholder*="링크"]',
                    'input[placeholder*="URL"]',
                    'input[placeholder*="http"]',
                    '.se-oglink-url-input',
                    'input'
                ];

                for (const sel of selectors) {{
                    const input = popup.querySelector(sel);
                    if (input && input.type !== 'hidden') {{
                        const rect = input.getBoundingClientRect();
                        if (rect.width > 50) {{
                            return {{
                                found: true,
                                x: rect.x + rect.width / 2,
                                y: rect.y + rect.height / 2,
                                selector: sel
                            }};
                        }}
                    }}
                }}

                return {{ found: false }};
            }})()
        """)

        if not input_info or not input_info.get('found'):
            logger.error("URL input field not found in modal")
            return False

        logger.debug(f"URL input found: {input_info.get('selector')}")

        # 입력 필드 클릭
        await self._click_at(input_info['x'], input_info['y'])
        await asyncio.sleep(0.2)

        # URL 입력 (CDP Input.insertText)
        await self.cdp.send("Input.insertText", {"text": url})
        logger.debug(f"URL entered: {url}")

        # Enter 키를 눌러 URL 검증 트리거 (일부 에디터에서 필요)
        await asyncio.sleep(0.3)
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13
        })
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "Enter",
            "code": "Enter",
            "windowsVirtualKeyCode": 13
        })

        return True

    async def _wait_for_preview(self, timeout: float = 10.0) -> bool:
        """OG 프리뷰 로딩 대기"""
        import time
        start = time.time()

        while time.time() - start < timeout:
            # 프리뷰 요소 확인
            preview_found = await self._evaluate_js(f"""
                (() => {{
                    const popup = document.querySelector('{self.MODAL_SELECTORS["popup"]}');
                    if (!popup) return false;

                    // 프리뷰 요소 찾기
                    const previewSelectors = [
                        '.se-oglink-preview',
                        '.se-link-preview',
                        '[class*="preview"]',
                        '.se-oglink-content',
                        'img[src*="http"]'  // OG 이미지
                    ];

                    for (const sel of previewSelectors) {{
                        const preview = popup.querySelector(sel);
                        if (preview) {{
                            const rect = preview.getBoundingClientRect();
                            if (rect.width > 50 && rect.height > 30) {{
                                return true;
                            }}
                        }}
                    }}

                    return false;
                }})()
            """)

            if preview_found:
                logger.debug("OG preview loaded")
                return True

            # 로딩 스피너 확인
            is_loading = await self._evaluate_js("""
                (() => {
                    const spinners = document.querySelectorAll(
                        '.se-loading, [class*="spinner"], [class*="loading"]'
                    );
                    for (const s of spinners) {
                        if (getComputedStyle(s).display !== 'none') {
                            return true;
                        }
                    }
                    return false;
                })()
            """)

            if is_loading:
                logger.debug("OG metadata loading...")

            await asyncio.sleep(0.5)

        return False

    async def _click_confirm_button(self) -> bool:
        """확인 버튼 클릭"""
        # 확인 버튼 텍스트 JS 배열
        confirm_texts_js = ', '.join(f'"{t}"' for t in self.CONFIRM_TEXTS)

        button_info = await self._evaluate_js(f"""
            (() => {{
                const popup = document.querySelector('{self.MODAL_SELECTORS["popup"]}');
                if (!popup) return {{ found: false }};

                const buttons = popup.querySelectorAll('button');
                const confirmTexts = [{confirm_texts_js}];

                for (const btn of buttons) {{
                    const text = btn.innerText?.trim() || '';
                    if (confirmTexts.some(t => text.includes(t))) {{
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {{
                            return {{
                                found: true,
                                text: text,
                                x: rect.x + rect.width / 2,
                                y: rect.y + rect.height / 2
                            }};
                        }}
                    }}
                }}

                return {{ found: false }};
            }})()
        """)

        if not button_info or not button_info.get('found'):
            logger.error("Confirm button not found")
            return False

        logger.debug(f"Clicking confirm button: '{button_info.get('text')}'")
        await self._click_at(button_info['x'], button_info['y'])
        return True

    async def _close_modal(self):
        """모달 닫기 (ESC 키)"""
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": "Escape",
            "code": "Escape",
            "windowsVirtualKeyCode": 27
        })
        await self.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "Escape",
            "code": "Escape",
            "windowsVirtualKeyCode": 27
        })
        logger.debug("Modal closed via ESC")

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

    async def _evaluate_js(self, expression: str):
        """JavaScript 평가"""
        result = await self.cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("value")

    def get_inserted_count(self) -> int:
        """현재 세션에서 삽입한 글감 수"""
        return self._inserted_count
