#!/usr/bin/env python3
"""
리치 콘텐츠 발행 테스트

이미지, 글감, 서식이 포함된 콘텐츠 발행을 테스트합니다.

사용법:
    # 개별 기능 테스트 (발행 없이)
    python scripts/test_rich_content.py

    # 이미지만 테스트
    python scripts/test_rich_content.py --image-only

    # 글감만 테스트
    python scripts/test_rich_content.py --oglink-only

    # 전체 리치 콘텐츠 발행
    python scripts/test_rich_content.py --publish
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from publisher.naver_publisher import NaverPublisher, PublishConfig, publish_with_rich_content
from publisher.components import ImageHandler, OGLinkHandler
from publisher.watchdogs import PopupWatchdog, EditorPopupWatchdog


SCREENSHOT_DIR = Path("data/rich_content_test")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def test_image_upload():
    """이미지 업로드 테스트 (발행 없이)"""

    print("\n" + "="*60)
    print("🖼️ 이미지 업로드 테스트")
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
        print("✅ 에디터 준비 완료")

        # 제목 입력
        await publisher._enter_title("이미지 업로드 테스트")
        await asyncio.sleep(0.5)

        # 본문으로 이동
        await publisher._move_to_body()
        await asyncio.sleep(0.5)

        # 텍스트 입력
        await publisher._type_text("이미지 업로드 테스트입니다.\n\n")

        # ImageHandler 초기화
        image_handler = ImageHandler(publisher.cdp, publisher.page)

        # 테스트 이미지 경로 (실제 이미지로 변경 필요)
        test_image = Path("data/test_image.jpg")

        if test_image.exists():
            print(f"\n📤 이미지 업로드 시도: {test_image}")
            success = await image_handler.upload_image(str(test_image))

            if success:
                print("   ✅ 이미지 업로드 성공!")
            else:
                print("   ❌ 이미지 업로드 실패")
        else:
            print(f"\n⚠️ 테스트 이미지가 없습니다: {test_image}")
            print("   테스트할 이미지를 data/test_image.jpg 에 저장해주세요")

            # 이미지 버튼 클릭만 테스트
            print("\n📷 이미지 버튼 클릭 테스트...")
            result = await image_handler._click_image_button()
            print(f"   버튼 클릭: {'성공' if result else '실패'}")

            if result:
                await asyncio.sleep(0.5)
                # 숨겨진 file input 찾기
                file_input = await image_handler._find_file_input()
                if file_input:
                    print(f"   ✅ 숨겨진 file input 발견! backendNodeId={file_input.get('backendNodeId')}")
                else:
                    print("   ❌ file input을 찾을 수 없습니다")

        # 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_image_test.png"))
        print(f"\n📸 스크린샷 저장: {SCREENSHOT_DIR}")

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


async def test_oglink():
    """글감(OGLink) 삽입 테스트 (발행 없이)"""

    print("\n" + "="*60)
    print("🔗 글감(OGLink) 삽입 테스트")
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
        print("✅ 에디터 준비 완료")

        # 제목 입력
        await publisher._enter_title("글감 테스트")
        await asyncio.sleep(0.5)

        # 본문으로 이동
        await publisher._move_to_body()
        await asyncio.sleep(0.5)

        # 텍스트 입력
        await publisher._type_text("글감 삽입 테스트입니다.\n\n")

        # OGLinkHandler 초기화
        oglink_handler = OGLinkHandler(publisher.cdp, publisher.page)

        # 테스트 URL
        test_url = "https://www.naver.com"

        print(f"\n🔗 글감 삽입 시도: {test_url}")
        success = await oglink_handler.insert_oglink(test_url)

        if success:
            print("   ✅ 글감 삽입 성공!")
        else:
            print("   ❌ 글감 삽입 실패")

        await asyncio.sleep(1)

        # 추가 텍스트
        await publisher._type_text("\n\n글감 삽입 후 텍스트입니다.")

        # 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_oglink_test.png"))
        print(f"\n📸 스크린샷 저장: {SCREENSHOT_DIR}")

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


async def test_all_features():
    """모든 기능 테스트 (발행 없이)"""

    print("\n" + "="*60)
    print("🧪 전체 기능 테스트 (이미지 + 글감 + 서식)")
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

        # Watchdog 초기화
        popup_watchdog = PopupWatchdog(publisher.cdp, publisher.page)
        editor_popup_watchdog = EditorPopupWatchdog(publisher.cdp, publisher.page)
        await popup_watchdog.attach()
        print("✅ Watchdog 연결됨")

        # 팝업 처리
        if await editor_popup_watchdog.check_for_popup('temp_save'):
            await editor_popup_watchdog.dismiss_temp_save_popup()
            print("✅ 임시저장 팝업 처리됨")
        else:
            await publisher._handle_popup()

        await asyncio.sleep(1)

        # 도구 위치 탐색
        await publisher._discover_tool_positions()
        print("✅ 에디터 준비 완료")

        # 핸들러 초기화
        image_handler = ImageHandler(publisher.cdp, publisher.page)
        oglink_handler = OGLinkHandler(publisher.cdp, publisher.page)

        # 제목 입력
        await publisher._enter_title("리치 콘텐츠 종합 테스트")
        await asyncio.sleep(0.5)

        # 본문으로 이동
        await publisher._move_to_body()
        await asyncio.sleep(0.5)

        # 1. 일반 텍스트
        print("\n📄 1. 일반 텍스트 입력...")
        await publisher._type_text("안녕하세요! 리치 콘텐츠 테스트입니다.\n\n")

        # 2. 인용구
        print("💬 2. 인용구 삽입...")
        await publisher.insert_quote()
        await asyncio.sleep(0.3)
        await publisher._type_text("이것은 인용구입니다.")
        await publisher._type_text("\n\n")

        # 3. 구분선
        print("➖ 3. 구분선 삽입...")
        await publisher.insert_divider()
        await asyncio.sleep(0.3)

        # 4. 볼드 텍스트
        print("🅱️ 4. 볼드 텍스트...")
        await publisher.apply_bold()
        await publisher._type_text("볼드 텍스트입니다.")
        await publisher.apply_bold()
        await publisher._type_text("\n\n")

        # 5. 글감
        print("🔗 5. 글감 삽입...")
        success = await oglink_handler.insert_oglink("https://www.naver.com")
        print(f"   글감 삽입: {'성공' if success else '실패'}")
        await asyncio.sleep(0.5)

        # 6. 구분선
        print("➖ 6. 구분선 삽입...")
        await publisher.insert_divider()
        await asyncio.sleep(0.3)

        # 7. 이미지 (있으면)
        test_image = Path("data/test_image.jpg")
        if test_image.exists():
            print("🖼️ 7. 이미지 업로드...")
            success = await image_handler.upload_image(str(test_image))
            print(f"   이미지 업로드: {'성공' if success else '실패'}")
        else:
            print("⚠️ 7. 테스트 이미지 없음 (스킵)")

        # 8. 마무리 텍스트
        await publisher._type_text("\n\n감사합니다!")

        # 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_all_features.png"))
        print(f"\n📸 스크린샷 저장: {SCREENSHOT_DIR}")

        print("\n" + "="*60)
        print("✅ 전체 기능 테스트 완료!")
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


async def test_rich_publish():
    """리치 콘텐츠 실제 발행 테스트"""

    print("\n" + "="*60)
    print("🚀 리치 콘텐츠 발행 테스트")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222"
    )

    sections = [
        {"type": "text", "content": "안녕하세요! 리치 콘텐츠 발행 테스트입니다."},
        {"type": "quote", "content": "인용구는 중요한 내용을 강조할 때 사용합니다."},
        {"type": "divider"},
        {"type": "text", "content": "볼드 텍스트입니다.", "format": ["bold"]},
        {"type": "oglink", "url": "https://www.naver.com"},
        {"type": "divider"},
        {"type": "text", "content": "감사합니다!"},
    ]

    # 테스트 이미지가 있으면 추가
    test_image = Path("data/test_image.jpg")
    if test_image.exists():
        sections.insert(3, {
            "type": "image",
            "path": str(test_image),
            "caption": "테스트 이미지입니다."
        })

    result = await publish_with_rich_content(
        title=f"리치 콘텐츠 테스트 - {datetime.now().strftime('%H:%M')}",
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

    parser = argparse.ArgumentParser(description="리치 콘텐츠 기능 테스트")
    parser.add_argument("--image-only", "-i", action="store_true",
                        help="이미지 업로드만 테스트")
    parser.add_argument("--oglink-only", "-o", action="store_true",
                        help="글감 삽입만 테스트")
    parser.add_argument("--publish", "-p", action="store_true",
                        help="리치 콘텐츠 실제 발행")

    args = parser.parse_args()

    if args.image_only:
        asyncio.run(test_image_upload())
    elif args.oglink_only:
        asyncio.run(test_oglink())
    elif args.publish:
        asyncio.run(test_rich_publish())
    else:
        asyncio.run(test_all_features())
