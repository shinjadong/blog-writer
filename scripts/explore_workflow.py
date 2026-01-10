#!/usr/bin/env python3
"""
네이버 블로그 발행 워크플로우 탐색

CDP로 Chrome에 연결하여 각 단계별 스크린샷과 DOM 정보를 수집합니다.
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

PROJECT_ROOT = Path(__file__).parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "data" / "workflow_analysis"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def capture_step(page, step_name: str, description: str = ""):
    """단계별 스크린샷과 DOM 정보 캡처"""
    timestamp = datetime.now().strftime("%H%M%S")

    # 스크린샷 저장
    screenshot_path = SCREENSHOT_DIR / f"{timestamp}_{step_name}.png"
    await page.screenshot(path=str(screenshot_path), full_page=False)

    # 현재 URL
    current_url = page.url

    # 주요 요소 탐색
    elements_info = []

    # 입력 필드들
    inputs = await page.query_selector_all("input, textarea, [contenteditable='true']")
    for inp in inputs[:10]:
        try:
            tag = await inp.evaluate("el => el.tagName")
            placeholder = await inp.get_attribute("placeholder") or ""
            class_name = await inp.get_attribute("class") or ""
            element_id = await inp.get_attribute("id") or ""
            elements_info.append({
                "type": "input",
                "tag": tag,
                "id": element_id,
                "class": class_name[:50],
                "placeholder": placeholder
            })
        except:
            pass

    # 버튼들
    buttons = await page.query_selector_all("button, [role='button']")
    for btn in buttons[:10]:
        try:
            text = await btn.inner_text()
            class_name = await btn.get_attribute("class") or ""
            elements_info.append({
                "type": "button",
                "text": text[:30],
                "class": class_name[:50]
            })
        except:
            pass

    # 결과 출력
    print(f"\n{'='*60}")
    print(f"📸 STEP: {step_name}")
    print(f"{'='*60}")
    print(f"URL: {current_url}")
    print(f"Screenshot: {screenshot_path}")
    print(f"Description: {description}")
    print(f"\n주요 요소:")
    for el in elements_info[:8]:
        print(f"  - {el}")

    return {
        "step": step_name,
        "url": current_url,
        "screenshot": str(screenshot_path),
        "elements": elements_info
    }


async def explore_naver_blog_workflow(blog_id: str, cdp_url: str = "http://localhost:9222"):
    """네이버 블로그 발행 워크플로우 탐색"""

    workflow_data = []

    print("\n🔍 네이버 블로그 발행 워크플로우 탐색 시작")
    print(f"   Blog ID: {blog_id}")
    print(f"   CDP URL: {cdp_url}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            print("\n✅ Chrome 연결 성공")
        except Exception as e:
            print(f"\n❌ Chrome 연결 실패: {e}")
            print("\n💡 Chrome을 다음 명령으로 실행하세요:")
            print("   google-chrome --remote-debugging-port=9222")
            return None

        # 기존 컨텍스트 사용
        contexts = browser.contexts
        if contexts:
            context = contexts[0]
        else:
            context = await browser.new_context()

        page = await context.new_page()

        # ========== STEP 1: 블로그 메인 페이지 ==========
        blog_url = f"https://blog.naver.com/{blog_id}"
        print(f"\n📍 블로그 메인 이동: {blog_url}")
        await page.goto(blog_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        step1 = await capture_step(page, "01_blog_main", "블로그 메인 페이지")
        workflow_data.append(step1)

        # 로그인 확인
        if "nid.naver.com" in page.url or "login" in page.url.lower():
            print("\n❌ 로그인이 필요합니다!")
            await page.close()
            return workflow_data

        # ========== STEP 2: 글쓰기 페이지 이동 ==========
        write_url = f"https://blog.naver.com/{blog_id}/postwrite"
        print(f"\n📍 글쓰기 페이지 이동: {write_url}")
        await page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        step2 = await capture_step(page, "02_write_page", "글쓰기 페이지 (에디터)")
        workflow_data.append(step2)

        # ========== STEP 3: 에디터 분석 ==========
        print("\n🔍 에디터 구조 분석...")

        # iframe 확인
        iframes = await page.query_selector_all("iframe")
        print(f"   iframe 수: {len(iframes)}")

        # 제목 영역 찾기
        title_selectors = [
            ".se-title-text",
            "#post-title",
            "input[placeholder*='제목']",
            "[data-placeholder*='제목']",
            ".se-ff-nanumgothic.se-fs32",
            "span.se-ff-nanumgothic"
        ]

        print("\n   제목 영역 탐색:")
        for selector in title_selectors:
            el = await page.query_selector(selector)
            if el:
                print(f"   ✅ {selector} - 발견!")
                try:
                    box = await el.bounding_box()
                    if box:
                        print(f"      위치: x={box['x']:.0f}, y={box['y']:.0f}, w={box['width']:.0f}, h={box['height']:.0f}")
                except:
                    pass
            else:
                print(f"   ❌ {selector} - 없음")

        # 본문 영역 찾기
        content_selectors = [
            ".se-component-content",
            ".se-text-paragraph",
            "#content-area",
            "[contenteditable='true']",
            ".se-main-container"
        ]

        print("\n   본문 영역 탐색:")
        for selector in content_selectors:
            el = await page.query_selector(selector)
            if el:
                print(f"   ✅ {selector} - 발견!")
                try:
                    box = await el.bounding_box()
                    if box:
                        print(f"      위치: x={box['x']:.0f}, y={box['y']:.0f}, w={box['width']:.0f}, h={box['height']:.0f}")
                except:
                    pass
            else:
                print(f"   ❌ {selector} - 없음")

        # 발행 버튼 찾기
        publish_selectors = [
            "button:has-text('발행')",
            ".se-publish-btn",
            "#publish-btn",
            "button:has-text('등록')",
            "[class*='publish']"
        ]

        print("\n   발행 버튼 탐색:")
        for selector in publish_selectors:
            try:
                el = await page.query_selector(selector)
                if el:
                    text = await el.inner_text()
                    print(f"   ✅ {selector} - '{text}'")
            except:
                print(f"   ❌ {selector} - 없음")

        # ========== STEP 4: 제목 입력 테스트 ==========
        print("\n📝 제목 영역 클릭 시도...")

        # 제목 영역 클릭
        title_area = await page.query_selector(".se-title-text, [data-placeholder*='제목']")
        if title_area:
            await title_area.click()
            await asyncio.sleep(0.5)
            step3 = await capture_step(page, "03_title_focus", "제목 영역 포커스")
            workflow_data.append(step3)

            # 테스트 제목 입력
            await page.keyboard.type("테스트 제목입니다", delay=50)
            await asyncio.sleep(0.5)
            step4 = await capture_step(page, "04_title_typed", "제목 입력 완료")
            workflow_data.append(step4)
        else:
            print("   ❌ 제목 영역을 찾을 수 없습니다")

        # ========== STEP 5: 본문 영역 이동 ==========
        print("\n📝 본문 영역 이동...")
        await page.keyboard.press("Tab")
        await asyncio.sleep(0.5)

        # 또는 직접 클릭
        content_area = await page.query_selector(".se-component-content, [contenteditable='true']")
        if content_area:
            await content_area.click()
            await asyncio.sleep(0.5)

        step5 = await capture_step(page, "05_content_focus", "본문 영역 포커스")
        workflow_data.append(step5)

        # 테스트 본문 입력
        await page.keyboard.type("테스트 본문 내용입니다.\n\n두 번째 문단입니다.", delay=30)
        await asyncio.sleep(0.5)
        step6 = await capture_step(page, "06_content_typed", "본문 입력 완료")
        workflow_data.append(step6)

        # ========== 워크플로우 저장 ==========
        workflow_path = SCREENSHOT_DIR / "workflow_analysis.json"
        with open(workflow_path, 'w', encoding='utf-8') as f:
            json.dump(workflow_data, f, ensure_ascii=False, indent=2)

        print(f"\n📄 워크플로우 분석 저장: {workflow_path}")
        print(f"📁 스크린샷 디렉토리: {SCREENSHOT_DIR}")

        # 페이지는 열어둠 (사용자가 확인할 수 있도록)
        print("\n⏸️  페이지를 열어둡니다. 확인 후 Enter를 누르세요...")
        input()

        await page.close()

        return workflow_data


async def main():
    import argparse
    parser = argparse.ArgumentParser(description='네이버 블로그 워크플로우 탐색')
    parser.add_argument('--blog-id', '-b', default='tlswkehd_', help='블로그 ID')
    parser.add_argument('--cdp-url', default='http://localhost:9222', help='Chrome CDP URL')

    args = parser.parse_args()

    result = await explore_naver_blog_workflow(
        blog_id=args.blog_id,
        cdp_url=args.cdp_url
    )

    if result:
        print("\n✅ 워크플로우 탐색 완료")
        print(f"   총 {len(result)} 단계 분석됨")


if __name__ == "__main__":
    asyncio.run(main())
