#!/usr/bin/env python3
"""
네이버 블로그 발행 워크플로우 탐색 v3

핵심 개선:
1. Tab 대신 마우스 클릭으로 영역 전환
2. 포커스 검증 후 입력
3. 정확한 좌표 기반 클릭
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

PROJECT_ROOT = Path(__file__).parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "data" / "workflow_analysis_v3"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


async def capture_snapshot(page, step_name: str, description: str = ""):
    """간단한 스냅샷 캡처"""
    timestamp = datetime.now().strftime("%H%M%S")
    base_name = f"{timestamp}_{step_name}"

    # 스크린샷
    screenshot_path = ANALYSIS_DIR / f"{base_name}.png"
    await page.screenshot(path=str(screenshot_path), full_page=False)

    # 현재 상태 분석
    state = await page.evaluate("""() => {
        const result = {
            url: window.location.href,
            title: { text: '', rect: null },
            body: { text: '', rect: null },
            focusedIn: 'unknown'
        };

        // 제목 텍스트
        const titleEl = document.querySelector('.se-title-text');
        if (titleEl) {
            result.title.text = titleEl.innerText || '';
            const rect = titleEl.getBoundingClientRect();
            result.title.rect = { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        }

        // 본문 텍스트 (제목 외의 se-text-paragraph)
        const allParagraphs = document.querySelectorAll('.se-text-paragraph');
        const titleArea = document.querySelector('.se-documentTitle');

        for (const p of allParagraphs) {
            if (titleArea && titleArea.contains(p)) continue;
            result.body.text = p.innerText || '';
            const rect = p.getBoundingClientRect();
            result.body.rect = { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
            break;
        }

        // 포커스 위치 확인 (툴바의 폰트 크기로 판단)
        const fontSizeEl = document.querySelector('[data-name="fontSize"]');
        if (fontSizeEl) {
            const size = fontSizeEl.innerText?.trim();
            result.focusedIn = size === '32' ? 'title' : 'body';
        }

        return result;
    }""")

    # JSON 저장
    json_path = ANALYSIS_DIR / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({"step": step_name, "description": description, **state}, f, ensure_ascii=False, indent=2)

    # 출력
    print(f"\n{'='*50}")
    print(f"📸 {step_name}: {description}")
    print(f"{'='*50}")
    print(f"📍 포커스: {state.get('focusedIn', 'unknown')}")
    print(f"📌 제목: {state['title']['text'][:50] if state['title']['text'] else '(비어있음)'}...")
    print(f"📄 본문: {state['body']['text'][:50] if state['body']['text'] else '(비어있음)'}...")
    print(f"📁 {screenshot_path.name}")

    return state


async def click_body_area(page):
    """본문 영역을 정확히 클릭"""

    # 방법 1: 본문 영역의 플레이스홀더나 텍스트 영역 클릭
    body_info = await page.evaluate("""() => {
        // 제목 영역 제외한 텍스트 컴포넌트 찾기
        const textComponents = document.querySelectorAll('.se-component.se-text');
        for (const comp of textComponents) {
            // documentTitle 내부가 아닌지 확인
            if (comp.closest('.se-documentTitle')) continue;

            const paragraph = comp.querySelector('.se-text-paragraph');
            if (paragraph) {
                const rect = paragraph.getBoundingClientRect();
                return {
                    found: true,
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2,
                    selector: '.se-component.se-text .se-text-paragraph'
                };
            }
        }

        // 대안: 구분선 아래 영역 찾기
        const separator = document.querySelector('.se-component.se-horizontalLine');
        if (separator) {
            const rect = separator.getBoundingClientRect();
            return {
                found: true,
                x: rect.x + 200,
                y: rect.y + 100,  // 구분선 아래
                selector: 'below_separator'
            };
        }

        return { found: false };
    }""")

    print(f"\n본문 클릭 정보: {body_info}")

    if body_info.get('found'):
        x, y = body_info['x'], body_info['y']
        print(f"   클릭 좌표: ({x:.0f}, {y:.0f})")
        await page.mouse.click(x, y)
        return True

    return False


async def explore_workflow(blog_id: str, cdp_url: str = "http://localhost:9222"):
    """워크플로우 탐색 v3"""

    print("\n" + "="*60)
    print("🔍 네이버 블로그 워크플로우 탐색 v3")
    print("="*60)
    print(f"Blog ID: {blog_id}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            print("✅ Chrome CDP 연결 성공")
        except Exception as e:
            print(f"❌ Chrome CDP 연결 실패: {e}")
            return None

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()
        page = await context.new_page()

        # ========== 글쓰기 페이지 ==========
        write_url = f"https://blog.naver.com/{blog_id}/postwrite"
        print(f"\n📍 글쓰기 페이지: {write_url}")
        await page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 팝업 처리
        try:
            cancel_btn = await page.query_selector('.se-popup-alert-confirm button:has-text("취소")')
            if cancel_btn:
                await cancel_btn.click()
                print("✅ 임시저장 팝업 닫기 (취소)")
                await asyncio.sleep(1)
        except:
            pass

        state0 = await capture_snapshot(page, "00_initial", "초기 상태")

        # ========== STEP 1: 제목 클릭 ==========
        print("\n\n🎯 STEP 1: 제목 영역 클릭")

        title_selector = ".se-documentTitle .se-text-paragraph"
        title_el = await page.query_selector(title_selector)
        if title_el:
            await title_el.click()
            await asyncio.sleep(0.5)
            print("   ✅ 제목 클릭 완료")

        state1 = await capture_snapshot(page, "01_title_clicked", "제목 클릭 후")

        # ========== STEP 2: 제목 입력 ==========
        print("\n\n📝 STEP 2: 제목 입력")

        test_title = "CCTV 설치 후기 테스트"
        await page.keyboard.type(test_title, delay=50)
        await asyncio.sleep(0.5)

        state2 = await capture_snapshot(page, "02_title_typed", "제목 입력 완료")

        # 제목이 제대로 입력됐는지 확인
        if test_title not in state2.get('title', {}).get('text', ''):
            print("   ⚠️ 제목 입력 확인 필요!")

        # ========== STEP 3: 본문으로 이동 (클릭) ==========
        print("\n\n🎯 STEP 3: 본문 영역으로 이동 (마우스 클릭)")

        # 본문 영역 클릭
        clicked = await click_body_area(page)
        if not clicked:
            # 대안: 고정 좌표 클릭 (본문 영역 중앙)
            print("   셀렉터 실패, 고정 좌표로 클릭 (720, 450)")
            await page.mouse.click(720, 450)

        await asyncio.sleep(1)  # 포커스 전환 대기

        state3 = await capture_snapshot(page, "03_body_clicked", "본문 클릭 후")

        # 포커스 확인
        if state3.get('focusedIn') != 'body':
            print("   ⚠️ 포커스가 여전히 제목에 있음! 재시도...")
            await page.mouse.click(720, 400)
            await asyncio.sleep(0.5)
            state3b = await capture_snapshot(page, "03b_body_retry", "본문 재클릭")

        # ========== STEP 4: 본문 입력 ==========
        print("\n\n📝 STEP 4: 본문 입력")

        test_body = "이것은 테스트 본문입니다."
        await page.keyboard.type(test_body, delay=30)
        await asyncio.sleep(0.5)

        state4 = await capture_snapshot(page, "04_body_typed", "본문 입력 완료")

        # 검증: 제목과 본문이 분리됐는지
        title_text = state4.get('title', {}).get('text', '')
        body_text = state4.get('body', {}).get('text', '')

        print(f"\n📊 입력 결과 검증:")
        print(f"   제목: '{title_text}'")
        print(f"   본문: '{body_text}'")

        if test_body in title_text:
            print("   ❌ 실패: 본문 내용이 제목에 입력됨!")
        elif test_body in body_text:
            print("   ✅ 성공: 본문이 올바르게 입력됨!")
        else:
            print("   ⚠️ 검증 필요: 본문 내용을 찾을 수 없음")

        # ========== STEP 5: Enter로 새 문단 추가 ==========
        print("\n\n📝 STEP 5: 새 문단 추가")
        await page.keyboard.press("Enter")
        await page.keyboard.press("Enter")
        await page.keyboard.type("두 번째 문단입니다.", delay=30)
        await asyncio.sleep(0.5)

        state5 = await capture_snapshot(page, "05_second_para", "두 번째 문단")

        # ========== STEP 6: 발행 버튼 확인 ==========
        print("\n\n🔘 STEP 6: 발행 버튼 분석")

        buttons = await page.evaluate("""() => {
            const result = [];
            const btns = document.querySelectorAll('button');
            btns.forEach(btn => {
                const text = btn.innerText?.trim();
                if (text === '발행' || text === '저장') {
                    const rect = btn.getBoundingClientRect();
                    result.push({
                        text,
                        x: rect.x + rect.width/2,
                        y: rect.y + rect.height/2,
                        width: rect.width,
                        height: rect.height
                    });
                }
            });
            return result;
        }""")

        print("발견된 버튼:")
        for btn in buttons:
            print(f"   [{btn['text']}] @ ({btn['x']:.0f}, {btn['y']:.0f}) {btn['width']:.0f}x{btn['height']:.0f}")

        state6 = await capture_snapshot(page, "06_ready", "발행 준비 완료")

        # ========== 결과 요약 ==========
        summary = {
            "blog_id": blog_id,
            "timestamp": datetime.now().isoformat(),
            "title_selector": ".se-documentTitle .se-text-paragraph",
            "body_click_method": "direct_click_on_body_area",
            "publish_button": buttons[0] if buttons else None,
            "final_state": state6
        }

        summary_path = ANALYSIS_DIR / "workflow_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n\n{'='*60}")
        print("📊 워크플로우 탐색 완료")
        print(f"{'='*60}")
        print(f"저장 위치: {ANALYSIS_DIR}")

        # 페이지 열어둠
        print("\n⏸️  Enter 키로 종료...")
        try:
            input()
        except EOFError:
            pass

        await page.close()
        return summary


async def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--blog-id', '-b', default='tlswkehd_')
    parser.add_argument('--cdp-url', default='http://localhost:9222')
    args = parser.parse_args()

    await explore_workflow(args.blog_id, args.cdp_url)


if __name__ == "__main__":
    asyncio.run(main())
