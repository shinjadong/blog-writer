"""
BaseWatchdog - CDP 이벤트 감시 베이스 클래스

Browser-Use 라이브러리의 Watchdog 패턴을 참조하여 구현.
CDP 이벤트를 구독하고 자동으로 핸들러를 호출합니다.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional
from abc import ABC

logger = logging.getLogger("blog_writer.watchdog")


class BaseWatchdog(ABC):
    """
    에디터 이벤트 감시 베이스 클래스

    CDP 이벤트를 구독하고 자동으로 핸들러를 호출합니다.
    핸들러 메서드는 on_EventName 형식으로 정의합니다.

    사용 예시:
        class MyWatchdog(BaseWatchdog):
            LISTENS_TO = ['Page.javascriptDialogOpening']

            async def on_Page_javascriptDialogOpening(self, event):
                # 이벤트 처리
                pass

        watchdog = MyWatchdog(cdp, page)
        await watchdog.attach()
    """

    # 구독할 CDP 이벤트 목록 (서브클래스에서 오버라이드)
    LISTENS_TO: List[str] = []

    # 발생시키는 이벤트 (문서화 용도)
    EMITS: List[str] = []

    def __init__(self, cdp_session, page):
        """
        Args:
            cdp_session: Playwright CDP 세션
            page: Playwright 페이지 객체
        """
        self.cdp = cdp_session
        self.page = page
        self._handlers: Dict[str, Callable] = {}
        self._attached = False
        self._event_history: List[Dict] = []

    async def attach(self):
        """CDP 이벤트 핸들러 등록"""
        if self._attached:
            logger.warning(f"{self.__class__.__name__} already attached")
            return

        # LISTENS_TO에 정의된 이벤트에 대해 핸들러 등록
        for event_name in self.LISTENS_TO:
            handler_name = f"on_{event_name.replace('.', '_')}"
            handler = getattr(self, handler_name, None)

            if handler and callable(handler):
                await self._register_handler(event_name, handler)
                logger.debug(f"{self.__class__.__name__}: Registered {handler_name}")
            else:
                logger.warning(
                    f"{self.__class__.__name__}: Handler {handler_name} not found"
                )

        self._attached = True
        logger.info(f"{self.__class__.__name__} attached")

    async def detach(self):
        """이벤트 핸들러 해제"""
        # Playwright CDP 세션은 명시적 해제가 필요 없음
        self._handlers.clear()
        self._attached = False
        logger.info(f"{self.__class__.__name__} detached")

    async def _register_handler(self, event_name: str, handler: Callable):
        """CDP 이벤트 핸들러 등록

        Args:
            event_name: CDP 이벤트 이름 (예: Page.javascriptDialogOpening)
            handler: 이벤트 핸들러 함수
        """
        # 이벤트 이름에서 도메인과 이벤트 분리
        # 예: Page.javascriptDialogOpening -> Page, javascriptDialogOpening
        parts = event_name.split('.')
        if len(parts) != 2:
            logger.error(f"Invalid event name format: {event_name}")
            return

        domain, event = parts

        # 도메인 활성화
        try:
            await self.cdp.send(f"{domain}.enable")
        except Exception as e:
            logger.debug(f"Domain {domain} enable failed (may already be enabled): {e}")

        # 이벤트 핸들러 래핑
        async def wrapped_handler(params):
            try:
                # 이벤트 히스토리 기록
                self._event_history.append({
                    'event': event_name,
                    'params': params
                })

                # 핸들러 실행
                result = await handler(params)
                return result

            except Exception as e:
                logger.error(f"Handler error for {event_name}: {e}")
                raise

        # Playwright CDP 세션의 on 메서드로 등록
        self.cdp.on(event_name, wrapped_handler)
        self._handlers[event_name] = wrapped_handler

    async def evaluate_js(self, expression: str) -> Any:
        """JavaScript 평가 헬퍼"""
        result = await self.cdp.send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True
        })
        return result.get("result", {}).get("value")

    async def click_at(self, x: float, y: float):
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

    async def find_element_by_selector(self, selector: str) -> Optional[Dict]:
        """CSS 셀렉터로 요소 찾기"""
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

    async def wait_for_selector(
        self,
        selector: str,
        timeout: float = 5.0,
        interval: float = 0.2
    ) -> Optional[Dict]:
        """셀렉터가 나타날 때까지 대기"""
        import time
        start = time.time()

        while time.time() - start < timeout:
            element = await self.find_element_by_selector(selector)
            if element:
                return element
            await asyncio.sleep(interval)

        return None

    def get_event_history(self) -> List[Dict]:
        """이벤트 히스토리 반환"""
        return self._event_history.copy()

    def clear_event_history(self):
        """이벤트 히스토리 초기화"""
        self._event_history.clear()
