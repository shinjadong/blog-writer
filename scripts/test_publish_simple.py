#!/usr/bin/env python3
"""
간단한 발행 테스트 스크립트

CDP로 연결된 Chrome에서 네이버 블로그에 테스트 포스트를 발행합니다.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# src 디렉토리를 path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from publisher.naver_publisher import NaverPublisher, PublishConfig


async def test_publish():
    """간단한 발행 테스트"""

    print("\n" + "=" * 60)
    print("네이버 블로그 발행 테스트")
    print(f"시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 설정
    blog_id = os.environ.get("NAVER_BLOG_ID", "tlsdntjd89")

    config = PublishConfig(
        blog_id=blog_id,
        cdp_url="http://localhost:9222",
        screenshot_dir="data/test_publish_simple"
    )

    # 스크린샷 폴더 생성
    Path(config.screenshot_dir).mkdir(parents=True, exist_ok=True)

    # 테스트 콘텐츠
    title = f"[자동발행테스트] {datetime.now().strftime('%m/%d %H:%M')}"
    content = """안녕하세요!

이 포스트는 blog-writer 시스템의 자동 발행 테스트입니다.

CDP(Chrome DevTools Protocol) 기반으로 네이버 블로그에 자동 발행됩니다.

테스트 완료 후 삭제해주세요.

감사합니다!"""

    print(f"\n블로그 ID: {blog_id}")
    print(f"제목: {title}")
    print(f"CDP URL: {config.cdp_url}")

    # 발행
    publisher = NaverPublisher()

    try:
        result = await publisher.publish(
            title=title,
            content=content,
            config=config
        )

        print("\n" + "=" * 60)
        if result.success:
            print("발행 성공!")
            print(f"URL: {result.blog_url}")
            print(f"Post ID: {result.post_id}")
        else:
            print("발행 실패!")
            print(f"오류: {result.error_message}")
        print("=" * 60)

        print(f"\n스크린샷: {config.screenshot_dir}/")

        return result

    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(test_publish())
    sys.exit(0 if result and result.success else 1)
