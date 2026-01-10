#!/usr/bin/env python3
"""
AdaptivePublisher 테스트

AI 기반 적응형 발행을 테스트합니다.
매 동작마다 DOM + 스크린샷을 DeepSeek에 전송하여 분석.

사용법:
    # 전체 테스트
    python scripts/test_adaptive_publish.py

    # AI 분석만 테스트
    python scripts/test_adaptive_publish.py --analyze-only

    # 실제 발행
    python scripts/test_adaptive_publish.py --publish
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# DeepSeek API 키 설정
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import (
    AdaptivePublisher,
    PublishConfig,
    adaptive_publish
)
from publisher.ai import AIUIAnalyzer


SCREENSHOT_DIR = Path("data/adaptive_test")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def test_ai_analyzer():
    """AI 분석기만 테스트"""

    print("\n" + "="*60)
    print("🤖 AI UI 분석기 테스트")
    print("="*60)

    from playwright.async_api import async_playwright
    import base64

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            print("✅ CDP 연결 성공")
        except Exception as e:
            print(f"❌ CDP 연결 실패: {e}")
            return

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()

        # 에디터 페이지 찾기
        page = None
        for pg in context.pages:
            if "blog.naver.com" in pg.url and "postwrite" in pg.url:
                page = pg
                break

        if not page:
            page = await context.new_page()
            await page.goto("https://blog.naver.com/tlswkehd_/postwrite", wait_until="networkidle")
            await asyncio.sleep(2)

        print(f"📍 페이지: {page.url}")

        # 스크린샷 캡처
        screenshot_bytes = await page.screenshot(type='jpeg', quality=85)
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')

        # AI 분석
        analyzer = AIUIAnalyzer()

        print("\n🔍 AI 분석 요청 중...")
        ui_map = await analyzer.analyze_editor(screenshot_b64)

        print(f"\n📊 분석 결과:")
        print(f"   페이지 타입: {ui_map.page_type}")
        print(f"   발견된 요소: {len(ui_map.elements)}개")

        for name, elem in ui_map.elements.items():
            print(f"\n   [{name}]")
            print(f"      설명: {elem.description}")
            print(f"      좌표: {elem.coords}")
            print(f"      확신도: {elem.confidence:.2f}")

        # 스크린샷 저장
        timestamp = datetime.now().strftime("%H%M%S")
        screenshot_path = SCREENSHOT_DIR / f"{timestamp}_analysis.png"
        await page.screenshot(path=str(screenshot_path))
        print(f"\n📸 스크린샷: {screenshot_path}")


async def test_adaptive_flow():
    """적응형 발행 플로우 테스트 (발행 없이)"""

    print("\n" + "="*60)
    print("🧪 적응형 발행 플로우 테스트")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY")
    )

    publisher = AdaptivePublisher(config)

    try:
        await publisher._init_browser()
        print("✅ 브라우저 초기화 완료")

        # 글쓰기 페이지 이동
        write_url = f"https://blog.naver.com/{config.blog_id}/postwrite"
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        print("✅ 에디터 페이지 로드 완료")

        # 1. 초기 상태 분석
        print("\n📊 1. 초기 상태 분석...")
        state = await publisher._analyze_current_state("에디터 초기 상태 파악")

        dom = state.get("dom", {})
        ai = state.get("ai_decision", {})

        print(f"   URL: {dom.get('url', 'N/A')}")
        print(f"   제목 영역: {dom.get('editor', {}).get('title', {}).get('found', False)}")
        print(f"   본문 영역: {dom.get('editor', {}).get('body', {}).get('found', False)}")
        print(f"   AI 분석: {ai.get('current_state', 'N/A')[:100]}")

        # 팝업 처리
        if dom.get("modals"):
            print("\n   ⚠️ 팝업 감지 - ESC로 닫기...")
            await publisher._press_escape()
            await asyncio.sleep(0.5)

        # 2. 제목 입력 테스트
        print("\n📝 2. 제목 입력 테스트...")
        title_info = dom.get("editor", {}).get("title")
        if title_info and title_info.get("coords"):
            await publisher._click_at(*title_info["coords"])
            await asyncio.sleep(0.3)
            await publisher._type_text("AI 적응형 테스트")
            print("   ✅ 제목 입력 완료")
        else:
            print("   ❌ 제목 영역 찾기 실패")

        # 3. 본문 이동 테스트
        print("\n📄 3. 본문 이동 테스트...")
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)
            await publisher._type_text("이것은 AI 기반 적응형 발행 테스트입니다.\n\n")
            print("   ✅ 본문 입력 완료")

        # 4. 툴바 버튼 테스트
        print("\n🔧 4. 툴바 버튼 테스트...")
        toolbar = dom.get("toolbar", {})

        for name, info in toolbar.items():
            if info.get("found"):
                print(f"   ✓ {name}: {info.get('coords')}")

        # 인용구 테스트
        if toolbar.get("quotation", {}).get("found"):
            print("\n   💬 인용구 삽입 테스트...")
            await publisher._click_at(*toolbar["quotation"]["coords"])
            await asyncio.sleep(0.3)
            await publisher._type_text("AI가 UI를 분석하여 요소를 찾습니다.")
            await publisher._type_text("\n")
            print("   ✅ 인용구 삽입 완료")

        # 구분선 테스트
        if toolbar.get("horizontal-line", {}).get("found"):
            print("\n   ➖ 구분선 삽입 테스트...")
            await publisher._click_at(*toolbar["horizontal-line"]["coords"])
            await asyncio.sleep(0.3)
            print("   ✅ 구분선 삽입 완료")

        # 5. 글감 버튼 테스트
        print("\n🔗 5. 글감 버튼 테스트...")
        if toolbar.get("material", {}).get("found"):
            material_coords = toolbar["material"]["coords"]
            print(f"   글감 버튼 위치: {material_coords}")

            # 글감 버튼 클릭
            await publisher._click_at(*material_coords)
            await asyncio.sleep(1)

            # 글감 모달 상태 분석 (AI 사용)
            print("   🤖 AI 분석 요청 중...")
            modal_state = await publisher._analyze_current_state(
                "글감 모달이 열렸습니다. URL 입력 필드를 찾아 https://naver.com을 입력해야 합니다.",
                use_ai=True
            )
            modal_ai = modal_state.get("ai_decision", {})

            if modal_ai.get("error"):
                print(f"   ⚠️ AI 오류: {modal_ai.get('error', '')[:100]}")
            else:
                print(f"   AI 상태: {modal_ai.get('current_state', 'N/A')[:100]}")
                print(f"   진행 가능: {modal_ai.get('can_proceed', False)}")

                if modal_ai.get("can_proceed"):
                    next_action = modal_ai.get("next_action", {})
                    print(f"   다음 행동: {next_action}")

            # ESC로 닫기
            await publisher._press_escape()
            print("   ✅ 글감 모달 테스트 완료")
        else:
            print("   ⚠️ 글감 버튼을 찾을 수 없음")

        # 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_flow_test.png"))

        print("\n" + "="*60)
        print("✅ 적응형 플로우 테스트 완료!")
        print(f"📁 스크린샷: {SCREENSHOT_DIR}")
        print("="*60)

        # 대기
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


async def test_adaptive_publish():
    """적응형 실제 발행 테스트"""

    print("\n" + "="*60)
    print("🚀 적응형 발행 테스트")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY")
    )

    sections = [
        {"type": "text", "content": "안녕하세요! AI 기반 적응형 발행 테스트입니다."},
        {"type": "quote", "content": "AI가 매 동작마다 화면을 분석하여 UI 요소를 찾습니다."},
        {"type": "divider"},
        {"type": "text", "content": "이것은 볼드 텍스트입니다.", "format": ["bold"]},
        {"type": "text", "content": "감사합니다!"},
    ]

    result = await adaptive_publish(
        title=f"AI 적응형 테스트 - {datetime.now().strftime('%H:%M')}",
        sections=sections,
        config=config
    )

    if result.success:
        print(f"\n✅ 발행 성공!")
        print(f"   URL: {result.blog_url}")
    else:
        print(f"\n❌ 발행 실패: {result.error_message}")

    print(f"\n📸 스크린샷: {result.screenshots}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="적응형 발행 테스트")
    parser.add_argument("--analyze-only", "-a", action="store_true",
                        help="AI 분석만 테스트")
    parser.add_argument("--publish", "-p", action="store_true",
                        help="실제 발행 테스트")

    args = parser.parse_args()

    if args.analyze_only:
        asyncio.run(test_ai_analyzer())
    elif args.publish:
        asyncio.run(test_adaptive_publish())
    else:
        asyncio.run(test_adaptive_flow())
