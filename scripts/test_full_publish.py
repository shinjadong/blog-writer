#!/usr/bin/env python3
"""
전체 발행 테스트

모든 콘텐츠 타입을 포함한 발행 테스트
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import (
    AdaptivePublisher,
    PublishConfig,
    adaptive_publish
)


async def test_full_publish():
    """전체 발행 테스트"""

    print("\n" + "="*60)
    print("전체 발행 테스트")
    print(f"시작 시간: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        screenshot_dir="data/adaptive_test"
    )

    # 테스트 이미지 경로
    test_image = "/home/tlswkehd/projects/cctv/OpenManus/assets/logo.jpg"

    # 테스트 콘텐츠 (이미지 포함)
    sections = [
        {
            "type": "text",
            "content": "안녕하세요! 이것은 AI 기반 적응형 발행 테스트입니다."
        },
        {
            "type": "image",
            "path": test_image
        },
        {
            "type": "divider"
        },
        {
            "type": "quote",
            "content": "AI가 동적으로 UI를 분석하여 요소 위치를 파악합니다."
        },
        {
            "type": "text",
            "content": "굵은 텍스트",
            "format": ["bold"]
        },
        {
            "type": "link",
            "url": "https://naver.com",
            "text": "네이버 바로가기"
        },
        {
            "type": "text",
            "content": "감사합니다!"
        }
    ]

    title = f"AI 적응형 발행 테스트 - {datetime.now().strftime('%m/%d %H:%M')}"

    print(f"\n제목: {title}")
    print(f"섹션 수: {len(sections)}")
    for i, section in enumerate(sections):
        print(f"  {i+1}. {section.get('type')}: {str(section.get('content', section.get('url', '')))[:30]}...")

    # 발행 실행
    print("\n발행 시작...")
    result = await adaptive_publish(
        title=title,
        sections=sections,
        config=config
    )

    print("\n" + "="*60)
    print("발행 결과")
    print("="*60)

    if result.success:
        print(f"상태: 성공")
        print(f"URL: {result.blog_url}")
    else:
        print(f"상태: 실패")
        print(f"오류: {result.error_message}")

    print(f"스크린샷: {len(result.screenshots)}개")
    for ss in result.screenshots:
        print(f"  - {ss}")

    print("="*60)


if __name__ == "__main__":
    asyncio.run(test_full_publish())
