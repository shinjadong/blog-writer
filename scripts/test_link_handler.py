#!/usr/bin/env python3
"""
링크 핸들러 테스트

업데이트된 _handle_oglink 함수 테스트
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def test_link_handler():
    """링크 핸들러 테스트"""

    print("\n" + "="*60)
    print("링크 핸들러 테스트")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
    )

    publisher = AdaptivePublisher(config)

    try:
        await publisher._init_browser()
        print("브라우저 초기화 완료")

        write_url = f"https://blog.naver.com/{config.blog_id}/postwrite"
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 임시저장 팝업 처리
        popup_result = await publisher._evaluate_js("""
            (() => {
                const popups = document.querySelectorAll('.se-popup-alert, [class*="popup"]');
                for (const popup of popups) {
                    if (popup.innerText.includes('작성 중인 글')) {
                        for (const btn of popup.querySelectorAll('button')) {
                            if (btn.innerText.includes('취소')) {
                                const rect = btn.getBoundingClientRect();
                                return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                            }
                        }
                    }
                }
                return { found: false };
            })()
        """)
        if popup_result and popup_result.get("found"):
            await publisher._click_at(*popup_result["coords"])
            await asyncio.sleep(0.5)
            print("임시저장 팝업 닫음")

        # 본문 영역으로 이동
        print("\n1. 본문 영역으로 이동...")
        body_info = await publisher._evaluate_js("""
            (() => {
                const body = document.querySelector('.se-component.se-text .se-text-paragraph');
                if (body) {
                    const rect = body.getBoundingClientRect();
                    return { found: true, coords: [rect.x + 50, rect.y + 20] };
                }
                return { found: false };
            })()
        """)
        if body_info.get("found"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        # 테스트 1: 링크 텍스트와 URL 모두 제공
        print("\n2. 테스트 1: 링크 텍스트 + URL...")
        result1 = await publisher._handle_oglink("https://naver.com", "네이버 바로가기")
        print(f"   결과: {'성공' if result1 else '실패'}")

        await asyncio.sleep(0.5)

        # 테스트 2: URL만 제공 (텍스트로 URL 사용)
        print("\n3. 테스트 2: URL만 제공...")
        result2 = await publisher._handle_oglink("https://google.com")
        print(f"   결과: {'성공' if result2 else '실패'}")

        # 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_link_test.png")
        print(f"\n스크린샷 저장: {timestamp}_link_test.png")

        print("\n" + "="*60)
        print("테스트 완료")
        print(f"테스트 1 (텍스트+URL): {'성공' if result1 else '실패'}")
        print(f"테스트 2 (URL만): {'성공' if result2 else '실패'}")
        print("="*60)

        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"\n테스트 실패: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


if __name__ == "__main__":
    asyncio.run(test_link_handler())
