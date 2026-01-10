#!/usr/bin/env python3
"""이미지 + 링크 기능 테스트"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig

TEST_IMAGE = "/home/tlswkehd/projects/cctv/OpenManus/assets/logo.jpg"


async def test_image_with_link():
    print("\n" + "="*60)
    print("이미지 + 링크 기능 테스트")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        screenshot_dir="data/image_with_link"
    )
    Path(config.screenshot_dir).mkdir(parents=True, exist_ok=True)

    publisher = AdaptivePublisher(config)

    try:
        await publisher._init_browser()
        print("브라우저 초기화 완료")

        write_url = f"https://blog.naver.com/{config.blog_id}/postwrite"
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 임시저장 팝업 처리
        for _ in range(3):
            dismissed = await publisher._dismiss_temp_save_popup()
            if not dismissed:
                break
            await asyncio.sleep(0.3)

        timestamp = datetime.now().strftime("%H%M%S")

        # 제목 입력
        print("\n1. 제목 입력...")
        dom = await publisher._get_dom_snapshot()
        title_info = dom.get("editor", {}).get("title")
        if title_info and title_info.get("coords"):
            await publisher._click_at(*title_info["coords"])
            await asyncio.sleep(0.3)
            await publisher._type_text(f"이미지 링크 테스트 - {datetime.now().strftime('%m/%d %H:%M')}")

        # 본문 영역 클릭
        print("\n2. 본문 영역 클릭...")
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        await publisher._type_text("아래 이미지를 클릭하면 네이버로 이동합니다.\n\n")
        await asyncio.sleep(0.3)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_01_before_image.png")

        # 이미지 + 링크 업로드
        print("\n3. 이미지 + 링크 업로드...")
        result = await publisher._handle_image_with_link(TEST_IMAGE, "https://naver.com")
        print(f"   결과: {'성공' if result else '실패'}")

        await asyncio.sleep(1)
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_02_after_image_link.png")

        # 마무리 텍스트
        print("\n4. 마무리 텍스트...")
        await publisher._press_escape()
        await asyncio.sleep(0.3)

        # 본문 하단으로 이동
        body_click = await publisher._evaluate_js("""
            (() => {
                const editor = document.querySelector('.se-content, .se-component-content');
                if (editor) {
                    const rect = editor.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height - 30] };
                }
                return { found: false };
            })()
        """)
        if body_click and body_click.get("found"):
            await publisher._click_at(*body_click["coords"])
            await asyncio.sleep(0.3)

        await publisher._type_text("\n\n이미지 링크 테스트 완료!")

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_03_content_done.png")

        # 발행
        print("\n5. 발행...")
        await publisher._click_publish_button()
        await asyncio.sleep(2)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_04_publish_panel.png")

        await publisher._click_final_publish_button()
        await asyncio.sleep(5)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_05_published.png")

        # URL 확인
        current_url = publisher.page.url
        print(f"\n최종 URL: {current_url}")

        if "PostView" in current_url or "logNo" in current_url:
            print("\n" + "="*60)
            print("발행 성공!")
            print(f"URL: {current_url}")
            print("="*60)
        else:
            print("\n발행 실패 또는 URL 확인 불가")

        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


if __name__ == "__main__":
    asyncio.run(test_image_with_link())
