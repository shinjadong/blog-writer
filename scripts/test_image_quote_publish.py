#!/usr/bin/env python3
"""
이미지 + 인용구 발행 테스트

이미지 업로드와 인용구를 포함한 실제 발행 테스트
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


# 테스트 이미지 경로
TEST_IMAGE = "/home/tlswkehd/projects/cctv/OpenManus/assets/logo.jpg"


async def test_image_quote_publish():
    """이미지 + 인용구 발행 테스트"""

    print("\n" + "="*60)
    print("이미지 + 인용구 발행 테스트")
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)

    # 이미지 파일 확인
    if not Path(TEST_IMAGE).exists():
        print(f"테스트 이미지가 없습니다: {TEST_IMAGE}")
        return

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        screenshot_dir="data/image_quote_test"
    )

    Path(config.screenshot_dir).mkdir(parents=True, exist_ok=True)

    publisher = AdaptivePublisher(config)

    try:
        await publisher._init_browser()
        print("브라우저 초기화 완료")

        # 글쓰기 페이지로 이동
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
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_01_start.png")

        # DOM 상태 확인
        dom = await publisher._get_dom_snapshot()

        # 1. 제목 입력
        print("\n1. 제목 입력...")
        title = f"이미지+인용구 테스트 - {datetime.now().strftime('%m/%d %H:%M')}"
        title_info = dom.get("editor", {}).get("title")
        if title_info and title_info.get("coords"):
            await publisher._click_at(*title_info["coords"])
            await asyncio.sleep(0.3)
            await publisher._type_text(title)
            print(f"   제목: {title}")

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_02_title.png")

        # 2. 본문으로 이동
        print("\n2. 본문 입력...")
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        # 첫 번째 텍스트
        await publisher._type_text("안녕하세요! 이미지와 인용구 테스트입니다.\n\n")
        await asyncio.sleep(0.3)

        # 3. 이미지 업로드 (expect_file_chooser 방식)
        print("\n3. 이미지 업로드...")
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_03_before_image.png")

        # 이미지 버튼 클릭
        image_btn = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="image"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                }
                return { found: false };
            })()
        """)

        if image_btn and image_btn.get("found"):
            try:
                # expect_file_chooser로 파일 다이얼로그 인터셉트
                async with publisher.page.expect_file_chooser(timeout=5000) as fc_info:
                    await publisher._click_at(*image_btn["coords"])
                    print(f"   이미지 버튼 클릭: {image_btn['coords']}")

                file_chooser = await fc_info.value
                await file_chooser.set_files(TEST_IMAGE)
                print(f"   이미지 파일 선택 완료: {TEST_IMAGE}")
                await asyncio.sleep(3)  # 업로드 대기

            except Exception as e:
                print(f"   이미지 업로드 실패: {e}")

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_04_after_image.png")

        # 팝업 닫기 (이미지 업로드 후 팝업이 있을 수 있음)
        await publisher._dismiss_temp_save_popup()
        await publisher._press_escape()
        await asyncio.sleep(0.5)

        # 본문으로 다시 이동
        dom = await publisher._get_dom_snapshot()
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        await publisher._type_text("\n\n")

        # 4. 인용구 삽입
        print("\n4. 인용구 삽입...")

        # 인용구 버튼 찾기
        quote_btn = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="quotation"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                }
                return { found: false };
            })()
        """)

        if quote_btn and quote_btn.get("found"):
            await publisher._click_at(*quote_btn["coords"])
            print(f"   인용구 버튼 클릭: {quote_btn['coords']}")
            await asyncio.sleep(0.5)

            # 인용구 내용 입력
            await publisher._type_text("AI 기반 자동화로 블로그 발행이 가능합니다!")
            await asyncio.sleep(0.3)

            # 인용구에서 나가기 (아래 화살표 + Enter)
            await publisher._type_text("\n")
            await asyncio.sleep(0.2)
        else:
            print("   인용구 버튼을 찾을 수 없음")

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_05_after_quote.png")

        # 5. 마무리 텍스트
        print("\n5. 마무리 텍스트...")

        # 본문 영역 다시 클릭 (인용구 밖으로)
        dom = await publisher._get_dom_snapshot()
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            # 인용구 아래쪽 클릭
            await publisher._click_at(body_info["coords"][0], body_info["coords"][1] + 200)
            await asyncio.sleep(0.3)

        await publisher._type_text("\n\n감사합니다!")
        await asyncio.sleep(0.3)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_06_content_done.png")

        # 6. 발행
        print("\n6. 발행...")

        # 발행 버튼 클릭
        dom = await publisher._get_dom_snapshot()
        publish_info = dom.get("toolbar", {}).get("publish")

        if publish_info and publish_info.get("found"):
            await publisher._click_at(*publish_info["coords"])
            print(f"   발행 버튼 클릭: {publish_info['coords']}")
        else:
            publish_btn = await publisher._evaluate_js("""
                (() => {
                    const btns = document.querySelectorAll('button');
                    for (const btn of btns) {
                        if (btn.innerText?.trim() === '발행') {
                            const rect = btn.getBoundingClientRect();
                            return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                        }
                    }
                    return { found: false };
                })()
            """)
            if publish_btn and publish_btn.get("found"):
                await publisher._click_at(*publish_btn["coords"])

        await asyncio.sleep(2)
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_07_publish_panel.png")

        # 7. 최종 발행 버튼
        print("\n7. 최종 발행...")

        final_publish = await publisher._evaluate_js("""
            (() => {
                const allBtns = document.querySelectorAll('button');
                let candidates = [];

                for (const btn of allBtns) {
                    const text = btn.innerText?.trim() || '';
                    const rect = btn.getBoundingClientRect();

                    if (text.includes('발행') && rect.x > 1000 && rect.y > 100) {
                        candidates.push({
                            text: text,
                            x: rect.x,
                            y: rect.y,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        });
                    }
                }

                if (candidates.length > 0) {
                    candidates.sort((a, b) => b.y - a.y);
                    return { found: true, ...candidates[0] };
                }

                return { found: false };
            })()
        """)

        if final_publish and final_publish.get("found"):
            print(f"   최종 발행 버튼: {final_publish}")
            await publisher._click_at(*final_publish["coords"])

        await asyncio.sleep(5)
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_08_final.png")

        # URL 확인
        current_url = publisher.page.url
        print(f"\n최종 URL: {current_url}")

        if "PostView" in current_url or "logNo" in current_url:
            print("\n" + "="*60)
            print("발행 성공!")
            print(f"URL: {current_url}")
            print("="*60)
        else:
            print("\n발행 완료 여부 불확실")

        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


if __name__ == "__main__":
    asyncio.run(test_image_quote_publish())
