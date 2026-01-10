#!/usr/bin/env python3
"""
전체 기능 통합 테스트

모든 기능 테스트:
- 텍스트
- 이미지 + 링크
- 하이퍼링크
- 인용구
- 구분선
- 굵은 텍스트
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import adaptive_publish, PublishConfig

TEST_IMAGE = "/home/tlswkehd/projects/cctv/OpenManus/assets/logo.jpg"


async def test_all_features():
    print("\n" + "="*60)
    print("전체 기능 통합 테스트")
    print(f"시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        screenshot_dir="data/all_features_test"
    )

    # 전체 기능 테스트 섹션
    sections = [
        # 1. 일반 텍스트
        {
            "type": "text",
            "content": "안녕하세요! AdaptivePublisher 전체 기능 통합 테스트입니다."
        },

        # 2. 구분선
        {
            "type": "divider"
        },

        # 3. 이미지 + 링크
        {
            "type": "image",
            "path": TEST_IMAGE,
            "link": "https://github.com/mannaandpoem/OpenManus",
            "caption": "OpenManus 로고 (클릭하면 GitHub으로 이동)"
        },

        # 4. 인용구
        {
            "type": "quote",
            "content": "AI 기반 자동화로 블로그 발행이 가능합니다!"
        },

        # 5. 굵은 텍스트
        {
            "type": "text",
            "content": "주요 기능:",
            "format": ["bold"]
        },

        # 6. 일반 텍스트 (목록처럼)
        {
            "type": "text",
            "content": "• 텍스트 입력\n• 이미지 업로드 및 링크 추가\n• 하이퍼링크 삽입\n• 인용구 삽입\n• 구분선 삽입"
        },

        # 7. 구분선
        {
            "type": "divider"
        },

        # 8. 하이퍼링크
        {
            "type": "link",
            "url": "https://naver.com",
            "text": "네이버 바로가기"
        },

        # 9. 마무리 텍스트
        {
            "type": "text",
            "content": "테스트 완료! 감사합니다."
        }
    ]

    title = f"전체 기능 통합 테스트 - {datetime.now().strftime('%m/%d %H:%M')}"

    print(f"\n제목: {title}")
    print(f"섹션 수: {len(sections)}개")
    for i, section in enumerate(sections, 1):
        section_type = section.get("type")
        preview = ""
        if section_type == "text":
            preview = section.get("content", "")[:30] + "..."
        elif section_type == "image":
            preview = f"이미지 + 링크({section.get('link', 'N/A')})"
        elif section_type == "link":
            preview = f"{section.get('text')} -> {section.get('url')}"
        elif section_type == "quote":
            preview = section.get("content", "")[:30] + "..."
        elif section_type == "divider":
            preview = "───────"
        print(f"  {i}. {section_type}: {preview}")

    print("\n발행 시작...")

    result = await adaptive_publish(
        title=title,
        sections=sections,
        config=config
    )

    print("\n" + "="*60)
    print("발행 결과")
    print("="*60)
    print(f"상태: {'성공' if result.success else '실패'}")

    if result.success:
        print(f"URL: {result.blog_url}")
    else:
        print(f"오류: {result.error_message}")

    print(f"스크린샷: {len(result.screenshots)}개")
    for ss in result.screenshots:
        print(f"  - {ss}")

    print("="*60)

    return result


if __name__ == "__main__":
    result = asyncio.run(test_all_features())

    if result.success:
        print(f"\n✅ 테스트 성공!")
        print(f"발행된 포스트: {result.blog_url}")
    else:
        print(f"\n❌ 테스트 실패: {result.error_message}")
