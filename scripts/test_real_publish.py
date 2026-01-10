#!/usr/bin/env python3
"""
실제 발행 테스트

실제로 블로그에 포스트를 발행합니다.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def real_publish():
    """실제 발행 테스트"""

    print("\n" + "="*60)
    print("실제 발행 테스트")
    print(f"시작: {datetime.now().strftime('%H:%M:%S')}")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY"),
        screenshot_dir="data/real_publish"
    )

    # 스크린샷 폴더 생성
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

        # 상태 확인
        dom = await publisher._get_dom_snapshot()
        print(f"\n에디터 상태:")
        print(f"  제목 영역: {dom.get('editor', {}).get('title', {}).get('found', False)}")
        print(f"  본문 영역: {dom.get('editor', {}).get('body', {}).get('found', False)}")
        print(f"  발행 버튼: {dom.get('toolbar', {}).get('publish', {}).get('found', False)}")

        # 제목 입력
        print("\n1. 제목 입력...")
        title = f"AI 자동 발행 테스트 - {datetime.now().strftime('%m/%d %H:%M')}"
        title_info = dom.get("editor", {}).get("title")
        if title_info and title_info.get("coords"):
            await publisher._click_at(*title_info["coords"])
            await asyncio.sleep(0.3)
            await publisher._type_text(title)
            print(f"   제목: {title}")

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_02_title.png")

        # 본문으로 이동
        print("\n2. 본문 입력...")
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        # 본문 내용
        content = """안녕하세요!

이 포스트는 AI 기반 적응형 발행 시스템으로 자동 작성되었습니다.

DOM 파싱과 AI 분석을 결합하여 네이버 블로그 에디터의 UI 요소를 동적으로 파악합니다.

감사합니다!"""

        await publisher._type_text(content)
        await asyncio.sleep(0.5)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_03_content.png")

        # 발행 버튼 클릭
        print("\n3. 발행 버튼 클릭...")

        # DOM 재분석
        dom = await publisher._get_dom_snapshot()
        publish_info = dom.get("toolbar", {}).get("publish")

        if publish_info and publish_info.get("found"):
            await publisher._click_at(*publish_info["coords"])
            print(f"   발행 버튼 클릭: {publish_info['coords']}")
        else:
            # 발행 버튼 직접 찾기
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
                print(f"   발행 버튼 클릭: {publish_btn['coords']}")
            else:
                print("   발행 버튼을 찾을 수 없음!")
                return

        await asyncio.sleep(2)
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_04_publish_panel.png")

        # 발행 패널에서 최종 발행 버튼 클릭
        print("\n4. 최종 발행...")

        # 발행 패널 내부의 발행 버튼 찾기 (우측 하단에 있는 녹색 발행 버튼)
        final_publish = await publisher._evaluate_js("""
            (() => {
                // 발행 패널 찾기 (우측에 열리는 패널)
                const publishPanel = document.querySelector('.se-publish-panel, .se-popup-publish, [class*="publish-option"]');

                // 패널 내부 또는 우측 영역에서 발행 버튼 찾기
                const allBtns = document.querySelectorAll('button');
                let candidates = [];

                for (const btn of allBtns) {
                    const text = btn.innerText?.trim() || '';
                    const rect = btn.getBoundingClientRect();

                    // "발행" 텍스트를 포함하고, 화면 우측에 있는 버튼
                    if (text.includes('발행') && rect.x > 1000 && rect.y > 100) {
                        candidates.push({
                            text: text,
                            x: rect.x,
                            y: rect.y,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2],
                            className: btn.className
                        });
                    }
                }

                // y 좌표가 가장 큰 것 (가장 아래쪽) 선택
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
        else:
            # 화면 우측 상단의 발행 버튼 다시 클릭 (1차 발행이 최종인 경우)
            print("   발행 패널 없음 - 이미 발행됨?")

        await asyncio.sleep(5)
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_05_final.png")

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
            print("스크린샷을 확인하세요.")

        # 대기
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
    asyncio.run(real_publish())
