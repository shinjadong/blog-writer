#!/usr/bin/env python3
"""
네이버 스마트에디터 서식 기능 테스트

인용구, 구분선, 볼드 등 고급 서식을 테스트합니다.
"""

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from publisher.naver_publisher import NaverPublisher, PublishConfig


async def test_formatting_tools():
    """서식 도구들 개별 테스트 (발행 없이)"""

    print("\n" + "="*60)
    print("🧪 서식 도구 테스트")
    print("="*60)

    publisher = NaverPublisher()

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222"
    )

    try:
        # CDP 연결
        await publisher._init_browser_cdp(config)
        print("✅ CDP 연결 성공")

        # 글쓰기 페이지로 이동
        write_url = f"https://blog.naver.com/{config.blog_id}/postwrite"
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 팝업 처리
        await publisher._handle_popup()
        await asyncio.sleep(1)

        # 도구 위치 탐색
        await publisher._discover_tool_positions()
        print("✅ 도구 위치 탐색 완료")

        # 제목 입력
        print("\n📝 제목 입력...")
        await publisher._enter_title("서식 테스트 포스트")
        await asyncio.sleep(0.5)

        # 본문으로 이동
        print("\n🎯 본문 영역으로 이동...")
        await publisher._move_to_body()
        await asyncio.sleep(0.5)

        # 1. 일반 텍스트
        print("\n📄 일반 텍스트 입력...")
        await publisher._type_text("안녕하세요. 서식 테스트입니다.\n\n")
        await asyncio.sleep(0.3)

        # 2. 인용구 테스트
        print("\n💬 인용구 삽입...")
        if await publisher.insert_quote():
            await asyncio.sleep(0.5)
            await publisher._type_text("이것은 인용구 내용입니다.")
            print("   ✅ 인용구 삽입 성공")
        else:
            print("   ❌ 인용구 삽입 실패")

        await publisher._type_text("\n\n")
        await asyncio.sleep(0.3)

        # 3. 구분선 테스트
        print("\n➖ 구분선 삽입...")
        if await publisher.insert_divider():
            await asyncio.sleep(0.5)
            print("   ✅ 구분선 삽입 성공")
        else:
            print("   ❌ 구분선 삽입 실패")

        await asyncio.sleep(0.3)

        # 4. 볼드 텍스트
        print("\n🅱️ 볼드 텍스트...")
        await publisher.apply_bold()
        await asyncio.sleep(0.2)
        await publisher._type_text("이것은 볼드 텍스트입니다.")
        await publisher.apply_bold()  # 해제
        await publisher._type_text("\n\n")
        print("   ✅ 볼드 적용 완료")

        # 5. 이탤릭 텍스트
        print("\n📐 이탤릭 텍스트...")
        await publisher.apply_italic()
        await asyncio.sleep(0.2)
        await publisher._type_text("이것은 이탤릭 텍스트입니다.")
        await publisher.apply_italic()  # 해제
        await publisher._type_text("\n\n")
        print("   ✅ 이탤릭 적용 완료")

        # 스크린샷
        screenshot_path = Path("data/format_test_result.png")
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        await publisher.page.screenshot(path=str(screenshot_path))
        print(f"\n📸 스크린샷 저장: {screenshot_path}")

        print("\n" + "="*60)
        print("✅ 서식 테스트 완료!")
        print("   브라우저에서 결과를 확인하세요.")
        print("="*60)

        # 대기 (결과 확인용)
        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"\n❌ 테스트 실패: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


async def test_formatted_publish():
    """서식이 적용된 글 발행 테스트"""

    print("\n" + "="*60)
    print("🚀 서식 적용 발행 테스트")
    print("="*60)

    from publisher.naver_publisher import publish_with_formatting

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222"
    )

    sections = [
        {"type": "text", "content": "안녕하세요! 오늘은 서식 기능을 테스트해봅니다."},
        {"type": "quote", "content": "인용구는 중요한 내용을 강조할 때 사용합니다."},
        {"type": "divider"},
        {"type": "text", "content": "이것은 볼드 텍스트입니다.", "format": ["bold"]},
        {"type": "text", "content": "이것은 일반 텍스트입니다."},
        {"type": "divider"},
        {"type": "text", "content": "감사합니다!"},
    ]

    result = await publish_with_formatting(
        title="서식 테스트 발행",
        sections=sections,
        config=config
    )

    if result.success:
        print(f"\n✅ 발행 성공!")
        print(f"   URL: {result.blog_url}")
    else:
        print(f"\n❌ 발행 실패: {result.error_message}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="네이버 스마트에디터 서식 테스트")
    parser.add_argument("--publish", "-p", action="store_true",
                        help="서식 적용 후 실제 발행까지 진행")

    args = parser.parse_args()

    if args.publish:
        asyncio.run(test_formatted_publish())
    else:
        asyncio.run(test_formatting_tools())
