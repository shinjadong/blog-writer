"""
PopupWatchdog - 팝업/다이얼로그 자동 처리

JavaScript 다이얼로그(alert, confirm, prompt)와
네이버 에디터 웹 팝업을 자동으로 처리합니다.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable

from .base import BaseWatchdog

logger = logging.getLogger("blog_writer.watchdog.popup")


class PopupWatchdog(BaseWatchdog):
    """
    JavaScript 다이얼로그 자동 처리

    alert, confirm, prompt, beforeunload 다이얼로그를
    자동으로 수락하거나 거부합니다.
    """

    LISTENS_TO = ['Page.javascriptDialogOpening']

    # 자동 수락할 다이얼로그 타입
    AUTO_ACCEPT = ['alert', 'beforeunload']
    # 자동 거부할 다이얼로그 타입
    AUTO_DISMISS = ['confirm', 'prompt']

    def __init__(self, cdp_session, page):
        super().__init__(cdp_session, page)
        self._dialog_history: List[Dict] = []
        self._custom_handlers: Dict[str, Callable] = {}

    async def on_Page_javascriptDialogOpening(self, event: Dict):
        """JavaScript 다이얼로그 이벤트 핸들러"""
        dialog_type = event.get('type', 'alert')
        message = event.get('message', '')
        default_prompt = event.get('defaultPrompt', '')

        logger.info(f"Dialog opened: [{dialog_type}] {message[:50]}...")

        # 히스토리 기록
        self._dialog_history.append({
            'type': dialog_type,
            'message': message,
            'default_prompt': default_prompt
        })

        # 커스텀 핸들러 확인
        if dialog_type in self._custom_handlers:
            handler = self._custom_handlers[dialog_type]
            accept, prompt_text = await handler(message, default_prompt)
        else:
            # 기본 처리
            accept = dialog_type in self.AUTO_ACCEPT
            prompt_text = default_prompt if dialog_type == 'prompt' else None

        # 다이얼로그 처리
        params = {'accept': accept}
        if prompt_text is not None:
            params['promptText'] = prompt_text

        try:
            await self.cdp.send('Page.handleJavaScriptDialog', params)
            logger.info(f"Dialog handled: accept={accept}")
        except Exception as e:
            logger.error(f"Failed to handle dialog: {e}")

        return {'handled': True, 'type': dialog_type, 'accept': accept}

    def set_handler(self, dialog_type: str, handler: Callable):
        """특정 다이얼로그 타입에 대한 커스텀 핸들러 설정

        Args:
            dialog_type: 다이얼로그 타입 (alert, confirm, prompt, beforeunload)
            handler: async def handler(message, default_prompt) -> (accept, prompt_text)
        """
        self._custom_handlers[dialog_type] = handler

    def get_dialog_history(self) -> List[Dict]:
        """다이얼로그 히스토리 반환"""
        return self._dialog_history.copy()


class EditorPopupWatchdog(BaseWatchdog):
    """
    네이버 에디터 웹 팝업 처리

    임시저장 복원, 링크 입력 등 에디터 내 웹 팝업을
    감지하고 처리합니다.
    """

    # 에디터 팝업 셀렉터
    SELECTORS = {
        'temp_save': '.se-popup-alert-confirm',
        'oglink_modal': '.se-popup',
        'image_modal': '.se-image-selection-layer',
        'link_layer': '.se-link-toolbar-layer',
    }

    # 버튼 텍스트
    BUTTON_TEXTS = {
        'confirm': ['확인', '적용', '예', 'OK'],
        'cancel': ['취소', '닫기', '아니오', 'Cancel'],
    }

    def __init__(self, cdp_session, page):
        super().__init__(cdp_session, page)
        self._active_popup: Optional[str] = None

    async def check_for_popup(self, popup_type: str = None) -> Optional[Dict]:
        """팝업 출현 확인

        Args:
            popup_type: 특정 팝업 타입 (None이면 모든 팝업 검색)

        Returns:
            발견된 팝업 정보 또는 None
        """
        selectors_to_check = (
            {popup_type: self.SELECTORS[popup_type]}
            if popup_type and popup_type in self.SELECTORS
            else self.SELECTORS
        )

        for name, selector in selectors_to_check.items():
            result = await self.evaluate_js(f"""
                (() => {{
                    const popup = document.querySelector('{selector}');
                    if (popup) {{
                        const style = getComputedStyle(popup);
                        const rect = popup.getBoundingClientRect();

                        if (rect.width > 0 && rect.height > 0 &&
                            style.display !== 'none' && style.visibility !== 'hidden') {{
                            return {{
                                found: true,
                                type: '{name}',
                                selector: '{selector}',
                                rect: {{ x: rect.x, y: rect.y, w: rect.width, h: rect.height }}
                            }};
                        }}
                    }}
                    return {{ found: false }};
                }})()
            """)

            if result and result.get('found'):
                self._active_popup = name
                return result

        return None

    async def wait_for_popup(
        self,
        popup_type: str = None,
        timeout: float = 3.0
    ) -> Optional[Dict]:
        """팝업이 나타날 때까지 대기"""
        import time
        start = time.time()

        while time.time() - start < timeout:
            popup = await self.check_for_popup(popup_type)
            if popup:
                return popup
            await asyncio.sleep(0.2)

        return None

    async def find_button_in_popup(
        self,
        button_type: str = 'confirm',
        popup_selector: str = None
    ) -> Optional[Dict]:
        """팝업 내 버튼 찾기

        Args:
            button_type: 'confirm' 또는 'cancel'
            popup_selector: 팝업 셀렉터 (None이면 활성 팝업 사용)
        """
        selector = popup_selector or (
            self.SELECTORS.get(self._active_popup, '.se-popup')
        )
        button_texts = self.BUTTON_TEXTS.get(button_type, ['확인'])

        # JavaScript로 버튼 찾기
        texts_js = ', '.join(f'"{t}"' for t in button_texts)
        result = await self.evaluate_js(f"""
            (() => {{
                const popup = document.querySelector('{selector}');
                if (!popup) return {{ found: false }};

                const buttons = popup.querySelectorAll('button');
                const targetTexts = [{texts_js}];

                for (const btn of buttons) {{
                    const text = btn.innerText?.trim() || '';
                    if (targetTexts.some(t => text.includes(t))) {{
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {{
                            return {{
                                found: true,
                                text: text,
                                x: rect.x + rect.width/2,
                                y: rect.y + rect.height/2
                            }};
                        }}
                    }}
                }}

                return {{ found: false }};
            }})()
        """)

        return result if result and result.get('found') else None

    async def handle_popup(
        self,
        action: str = 'dismiss',
        popup_type: str = None,
        timeout: float = 3.0
    ) -> bool:
        """팝업 처리

        Args:
            action: 'confirm' (확인) 또는 'dismiss' (취소)
            popup_type: 특정 팝업 타입
            timeout: 팝업 대기 시간

        Returns:
            처리 성공 여부
        """
        # 팝업 대기
        popup = await self.wait_for_popup(popup_type, timeout)
        if not popup:
            logger.debug("No popup found")
            return False

        logger.info(f"Popup found: {popup.get('type')}")

        # 버튼 타입 결정
        button_type = 'confirm' if action == 'confirm' else 'cancel'

        # 버튼 찾기
        button = await self.find_button_in_popup(button_type)
        if not button:
            logger.warning(f"Button not found for action: {action}")
            return False

        # 버튼 클릭
        await self.click_at(button['x'], button['y'])
        logger.info(f"Clicked '{button.get('text')}' button")

        self._active_popup = None
        return True

    async def dismiss_temp_save_popup(self) -> bool:
        """임시저장 복원 팝업 닫기 (취소 클릭)"""
        return await self.handle_popup(
            action='dismiss',
            popup_type='temp_save',
            timeout=2.0
        )

    async def close_by_escape(self):
        """ESC 키로 팝업 닫기"""
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
        self._active_popup = None
