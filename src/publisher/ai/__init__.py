"""
AI 기반 UI 분석 모듈

DeepSeek Vision을 사용하여 동적으로 UI를 분석합니다.
"""

from .ui_analyzer import (
    AIUIAnalyzer,
    UIElement,
    UIMap,
    DeepSeekVisionClient,
    compress_screenshot,
    capture_and_analyze,
)

__all__ = [
    "AIUIAnalyzer",
    "UIElement",
    "UIMap",
    "DeepSeekVisionClient",
    "compress_screenshot",
    "capture_and_analyze",
]
