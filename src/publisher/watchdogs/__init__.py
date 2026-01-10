"""
Watchdog 모듈 - CDP 이벤트 감시

Browser-Use 라이브러리의 Watchdog 패턴을 참조하여 구현.
팝업, 다이얼로그 등을 자동으로 처리합니다.
"""

from .base import BaseWatchdog
from .popup_watchdog import PopupWatchdog, EditorPopupWatchdog

__all__ = [
    "BaseWatchdog",
    "PopupWatchdog",
    "EditorPopupWatchdog",
]
