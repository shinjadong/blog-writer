#!/usr/bin/env python3
"""
네이버 블로그 발행 워크플로우 탐색 v2

매 액션마다:
1. 스크린샷 캡처
2. DOM 스냅샷 (HTML 구조)
3. 포커스된 요소 확인
4. 주요 셀렉터 분석
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

PROJECT_ROOT = Path(__file__).parent.parent
ANALYSIS_DIR = PROJECT_ROOT / "data" / "workflow_analysis_v2"
ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)


async def capture_snapshot(page, step_name: str, description: str = ""):
    """스크린샷 + DOM 스냅샷 캡처"""
    timestamp = datetime.now().strftime("%H%M%S")
    base_name = f"{timestamp}_{step_name}"

    # 1. 스크린샷
    screenshot_path = ANALYSIS_DIR / f"{base_name}.png"
    await page.screenshot(path=str(screenshot_path), full_page=False)

    # 2. 현재 포커스된 요소 확인
    focused_info = await page.evaluate("""() => {
        const el = document.activeElement;
        if (!el) return null;
        return {
            tagName: el.tagName,
            id: el.id || '',
            className: el.className || '',
            contentEditable: el.contentEditable,
            innerText: el.innerText?.substring(0, 100) || '',
            role: el.getAttribute('role') || '',
            dataType: el.getAttribute('data-type') || ''
        };
    }""")

    # 3. 에디터 핵심 영역 스냅샷
    editor_snapshot = await page.evaluate("""() => {
        const result = {
            url: window.location.href,
            title: {},
            body: {},
            buttons: [],
            allEditableAreas: []
        };

        // 제목 영역 분석
        const titleSelectors = [
            '.se-title-text',
            '.se-documentTitle',
            '[data-name="documentTitle"]',
            '.se-component.se-documentTitle'
        ];

        for (const selector of titleSelectors) {
            const el = document.querySelector(selector);
            if (el) {
                const rect = el.getBoundingClientRect();
                result.title[selector] = {
                    found: true,
                    text: el.innerText?.substring(0, 200) || '',
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                    contentEditable: el.contentEditable,
                    className: el.className
                };
            }
        }

        // 본문 영역 분석
        const bodySelectors = [
            '.se-component.se-text',
            '.se-text-paragraph',
            '.se-component-content',
            '[data-name="paragraph"]',
            '.se-main-container .se-section'
        ];

        for (const selector of bodySelectors) {
            const elements = document.querySelectorAll(selector);
            if (elements.length > 0) {
                result.body[selector] = [];
                elements.forEach((el, i) => {
                    if (i < 5) {  // 처음 5개만
                        const rect = el.getBoundingClientRect();
                        result.body[selector].push({
                            index: i,
                            text: el.innerText?.substring(0, 100) || '',
                            rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                            contentEditable: el.contentEditable,
                            className: el.className?.substring(0, 100)
                        });
                    }
                });
            }
        }

        // 버튼들 분석
        const buttons = document.querySelectorAll('button, [role="button"]');
        buttons.forEach(btn => {
            const text = btn.innerText?.trim();
            if (text && (text.includes('발행') || text.includes('저장') || text.includes('등록') || text.includes('확인'))) {
                const rect = btn.getBoundingClientRect();
                result.buttons.push({
                    text: text.substring(0, 30),
                    className: btn.className?.substring(0, 50),
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                    disabled: btn.disabled
                });
            }
        });

        // 모든 contenteditable 영역
        const editables = document.querySelectorAll('[contenteditable="true"]');
        editables.forEach((el, i) => {
            if (i < 10) {
                const rect = el.getBoundingClientRect();
                result.allEditableAreas.push({
                    index: i,
                    tagName: el.tagName,
                    className: el.className?.substring(0, 80),
                    text: el.innerText?.substring(0, 50),
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                });
            }
        });

        return result;
    }""")

    # 4. HTML 구조 추출 (에디터 영역만)
    html_snapshot = await page.evaluate("""() => {
        const editor = document.querySelector('.se-content, .se-main-container, #se-editor');
        if (editor) {
            return editor.outerHTML.substring(0, 5000);
        }
        return document.body.innerHTML.substring(0, 5000);
    }""")

    # 결과 저장
    snapshot_data = {
        "step": step_name,
        "description": description,
        "timestamp": timestamp,
        "screenshot": str(screenshot_path),
        "focused_element": focused_info,
        "editor_snapshot": editor_snapshot,
    }

    # JSON 저장
    json_path = ANALYSIS_DIR / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(snapshot_data, f, ensure_ascii=False, indent=2)

    # HTML 저장
    html_path = ANALYSIS_DIR / f"{base_name}.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_snapshot)

    # 콘솔 출력
    print(f"\n{'='*60}")
    print(f"📸 STEP: {step_name}")
    print(f"{'='*60}")
    print(f"📝 Description: {description}")
    print(f"🔗 URL: {editor_snapshot.get('url', 'N/A')}")
    print(f"📁 Screenshot: {screenshot_path.name}")

    print(f"\n🎯 포커스된 요소:")
    if focused_info:
        print(f"   Tag: {focused_info.get('tagName')}")
        print(f"   Class: {focused_info.get('className', '')[:60]}")
        print(f"   ContentEditable: {focused_info.get('contentEditable')}")
        print(f"   Text: {focused_info.get('innerText', '')[:50]}...")
    else:
        print("   (없음)")

    print(f"\n📌 제목 영역:")
    for selector, info in editor_snapshot.get('title', {}).items():
        if info.get('found'):
            rect = info.get('rect', {})
            print(f"   ✅ {selector}")
            print(f"      위치: ({rect.get('x', 0):.0f}, {rect.get('y', 0):.0f})")
            print(f"      텍스트: {info.get('text', '')[:50]}...")

    print(f"\n📄 본문 영역:")
    for selector, items in editor_snapshot.get('body', {}).items():
        if items:
            print(f"   ✅ {selector} ({len(items)}개)")
            if items:
                rect = items[0].get('rect', {})
                print(f"      첫 번째 위치: ({rect.get('x', 0):.0f}, {rect.get('y', 0):.0f})")

    print(f"\n🔘 버튼:")
    for btn in editor_snapshot.get('buttons', []):
        rect = btn.get('rect', {})
        print(f"   [{btn.get('text')}] @ ({rect.get('x', 0):.0f}, {rect.get('y', 0):.0f})")

    print(f"\n✏️ Editable 영역: {len(editor_snapshot.get('allEditableAreas', []))}개")
    for area in editor_snapshot.get('allEditableAreas', [])[:5]:
        rect = area.get('rect', {})
        print(f"   #{area.get('index')}: {area.get('tagName')} @ ({rect.get('x', 0):.0f}, {rect.get('y', 0):.0f}) - {area.get('className', '')[:40]}")

    return snapshot_data


async def explore_workflow(blog_id: str, cdp_url: str = "http://localhost:9222"):
    """개선된 워크플로우 탐색"""

    print("\n" + "="*60)
    print("🔍 네이버 블로그 워크플로우 탐색 v2")
    print("="*60)
    print(f"Blog ID: {blog_id}")
    print(f"CDP URL: {cdp_url}")
    print(f"저장 디렉토리: {ANALYSIS_DIR}")

    workflow_steps = []

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            print("\n✅ Chrome CDP 연결 성공")
        except Exception as e:
            print(f"\n❌ Chrome CDP 연결 실패: {e}")
            print("\n💡 다음 명령으로 Chrome 실행:")
            print("   google-chrome --remote-debugging-port=9222 --user-data-dir=/home/tlswkehd/.config/chrome-debug")
            return None

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()
        page = await context.new_page()

        # ========== STEP 1: 글쓰기 페이지 이동 ==========
        write_url = f"https://blog.naver.com/{blog_id}/postwrite"
        print(f"\n📍 글쓰기 페이지 이동: {write_url}")
        await page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # 로그인 체크
        if "nid.naver.com" in page.url or "login" in page.url.lower():
            print("\n❌ 로그인이 필요합니다!")
            await page.close()
            return None

        # ========== 팝업 처리 ==========
        # "작성 중인 글이 있습니다" 팝업 확인
        popup_handled = False
        try:
            popup = await page.query_selector('.se-popup-alert-confirm')
            if popup:
                print("\n🔔 팝업 발견: 작성 중인 글이 있습니다")
                # '취소' 버튼 클릭 (새로 시작)
                cancel_btn = await popup.query_selector('button:has-text("취소")')
                if cancel_btn:
                    await cancel_btn.click()
                    print("   ✅ '취소' 클릭 - 새로 시작")
                    popup_handled = True
                    await asyncio.sleep(1)
        except Exception as e:
            print(f"   팝업 처리 중 오류: {e}")

        if not popup_handled:
            # 다른 형태의 팝업/모달 확인
            try:
                confirm_btn = await page.query_selector('.se-popup button:has-text("확인"), .se-popup button:has-text("취소")')
                if confirm_btn:
                    btn_text = await confirm_btn.inner_text()
                    await confirm_btn.click()
                    print(f"   ✅ '{btn_text}' 버튼 클릭")
                    await asyncio.sleep(1)
            except:
                pass

        step1 = await capture_snapshot(page, "01_editor_loaded", "에디터 페이지 로드 완료")
        workflow_steps.append(step1)

        # ========== STEP 2: 제목 영역 정확히 찾기 ==========
        print("\n\n" + "="*60)
        print("🔍 제목 영역 정확한 셀렉터 탐색")
        print("="*60)

        # 제목 영역의 실제 편집 가능한 요소 찾기
        title_element = await page.evaluate("""() => {
            // 방법 1: se-documentTitle 내부의 편집 가능 영역
            let titleEl = document.querySelector('.se-documentTitle .se-text-paragraph');
            if (titleEl) return { selector: '.se-documentTitle .se-text-paragraph', found: true };

            // 방법 2: data-name으로 찾기
            titleEl = document.querySelector('[data-name="documentTitle"] .se-text-paragraph');
            if (titleEl) return { selector: '[data-name="documentTitle"] .se-text-paragraph', found: true };

            // 방법 3: se-title-text
            titleEl = document.querySelector('.se-title-text');
            if (titleEl) return { selector: '.se-title-text', found: true };

            // 방법 4: 첫 번째 contenteditable
            const editables = document.querySelectorAll('[contenteditable="true"]');
            if (editables.length > 0) {
                return { selector: 'first_editable', found: true, index: 0 };
            }

            return { found: false };
        }""")

        print(f"제목 요소 탐색 결과: {title_element}")

        # 제목 영역 클릭
        title_clicked = False
        if title_element.get('found'):
            selector = title_element.get('selector')
            if selector == 'first_editable':
                # 첫 번째 editable 요소 클릭
                await page.evaluate("document.querySelectorAll('[contenteditable=\"true\"]')[0].click()")
                title_clicked = True
            else:
                el = await page.query_selector(selector)
                if el:
                    await el.click()
                    title_clicked = True

        if title_clicked:
            await asyncio.sleep(0.5)
            step2 = await capture_snapshot(page, "02_title_focused", "제목 영역 클릭 후 포커스")
            workflow_steps.append(step2)

        # ========== STEP 3: 제목 입력 ==========
        test_title = "테스트 제목 - CCTV 추천"
        print(f"\n📝 제목 입력: {test_title}")
        await page.keyboard.type(test_title, delay=50)
        await asyncio.sleep(0.5)

        step3 = await capture_snapshot(page, "03_title_typed", f"제목 입력 완료: {test_title}")
        workflow_steps.append(step3)

        # ========== STEP 4: 본문 영역으로 이동 (정확한 방법 탐색) ==========
        print("\n\n" + "="*60)
        print("🔍 본문 영역 이동 방법 탐색")
        print("="*60)

        # 본문 영역의 실제 편집 가능한 요소 찾기
        body_element = await page.evaluate("""() => {
            // 제목이 아닌 본문 영역 찾기
            const allEditables = document.querySelectorAll('[contenteditable="true"]');
            const titleArea = document.querySelector('.se-documentTitle');

            for (let i = 0; i < allEditables.length; i++) {
                const el = allEditables[i];
                // 제목 영역 내부가 아닌 요소 찾기
                if (titleArea && titleArea.contains(el)) continue;

                // se-text 컴포넌트 내부 확인
                const parent = el.closest('.se-component');
                if (parent && parent.classList.contains('se-text')) {
                    const rect = el.getBoundingClientRect();
                    return {
                        selector: `.se-component.se-text .se-text-paragraph`,
                        index: i,
                        found: true,
                        rect: { x: rect.x, y: rect.y }
                    };
                }
            }

            // 대안: 두 번째 editable (첫 번째가 제목이라고 가정)
            if (allEditables.length > 1) {
                const rect = allEditables[1].getBoundingClientRect();
                return {
                    selector: 'second_editable',
                    index: 1,
                    found: true,
                    rect: { x: rect.x, y: rect.y }
                };
            }

            return { found: false };
        }""")

        print(f"본문 요소 탐색 결과: {body_element}")

        # 본문 영역 클릭 (Tab 대신 직접 클릭)
        body_clicked = False
        if body_element.get('found'):
            if body_element.get('selector') == 'second_editable':
                await page.evaluate("document.querySelectorAll('[contenteditable=\"true\"]')[1].click()")
                body_clicked = True
            else:
                # 좌표로 클릭
                rect = body_element.get('rect', {})
                if rect:
                    await page.mouse.click(rect.get('x', 500) + 50, rect.get('y', 400) + 20)
                    body_clicked = True

        if not body_clicked:
            # Tab 키 시도
            print("   Tab 키로 이동 시도...")
            await page.keyboard.press("Tab")

        await asyncio.sleep(0.5)
        step4 = await capture_snapshot(page, "04_body_focused", "본문 영역 포커스")
        workflow_steps.append(step4)

        # ========== STEP 5: 포커스 확인 후 본문 입력 ==========
        # 현재 포커스가 제목인지 본문인지 확인
        current_focus = await page.evaluate("""() => {
            const active = document.activeElement;
            const titleArea = document.querySelector('.se-documentTitle');
            if (titleArea && titleArea.contains(active)) {
                return 'title';
            }
            return 'body';
        }""")

        print(f"\n현재 포커스 위치: {current_focus}")

        if current_focus == 'title':
            print("⚠️  아직 제목 영역에 포커스! 본문으로 다시 이동 시도...")
            # 명시적으로 본문 영역 클릭
            await page.evaluate("""() => {
                const bodyPara = document.querySelector('.se-component.se-text .se-text-paragraph');
                if (bodyPara) bodyPara.click();
            }""")
            await asyncio.sleep(0.5)

            step4b = await capture_snapshot(page, "04b_body_retry", "본문 영역 재시도")
            workflow_steps.append(step4b)

        # ========== STEP 6: 본문 입력 ==========
        test_content = "이것은 테스트 본문입니다.\n\n두 번째 문단입니다."
        print(f"\n📝 본문 입력 시작...")
        await page.keyboard.type(test_content, delay=30)
        await asyncio.sleep(0.5)

        step5 = await capture_snapshot(page, "05_body_typed", "본문 입력 완료")
        workflow_steps.append(step5)

        # ========== STEP 7: 발행 버튼 분석 ==========
        print("\n\n" + "="*60)
        print("🔍 발행 버튼 상세 분석")
        print("="*60)

        publish_buttons = await page.evaluate("""() => {
            const results = [];

            // 상단 버튼 영역
            const headerBtns = document.querySelectorAll('header button, .se-header button, [class*="header"] button');
            headerBtns.forEach(btn => {
                const text = btn.innerText?.trim();
                const rect = btn.getBoundingClientRect();
                results.push({
                    location: 'header',
                    text: text,
                    className: btn.className,
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                });
            });

            // 발행 관련 버튼
            const allBtns = document.querySelectorAll('button');
            allBtns.forEach(btn => {
                const text = btn.innerText?.trim();
                if (text && (text.includes('발행') || text.includes('저장'))) {
                    const rect = btn.getBoundingClientRect();
                    results.push({
                        location: 'page',
                        text: text,
                        className: btn.className,
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                    });
                }
            });

            return results;
        }""")

        print("발견된 버튼들:")
        for btn in publish_buttons:
            rect = btn.get('rect', {})
            print(f"   [{btn.get('text')}] @ ({rect.get('x', 0):.0f}, {rect.get('y', 0):.0f}) - {btn.get('location')}")

        step6 = await capture_snapshot(page, "06_ready_publish", "발행 준비 완료")
        workflow_steps.append(step6)

        # ========== 워크플로우 요약 저장 ==========
        summary = {
            "blog_id": blog_id,
            "timestamp": datetime.now().isoformat(),
            "steps": workflow_steps,
            "publish_buttons": publish_buttons
        }

        summary_path = ANALYSIS_DIR / "workflow_summary.json"
        with open(summary_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

        print(f"\n\n{'='*60}")
        print("📊 워크플로우 탐색 완료")
        print(f"{'='*60}")
        print(f"총 {len(workflow_steps)} 단계 분석")
        print(f"저장 위치: {ANALYSIS_DIR}")
        print(f"요약 파일: {summary_path}")

        print("\n⏸️  페이지를 열어둡니다. Enter 키를 누르면 종료...")
        input()

        await page.close()
        return workflow_steps


async def main():
    import argparse
    parser = argparse.ArgumentParser(description='네이버 블로그 워크플로우 탐색 v2')
    parser.add_argument('--blog-id', '-b', default='tlswkehd_', help='블로그 ID')
    parser.add_argument('--cdp-url', default='http://localhost:9222', help='Chrome CDP URL')

    args = parser.parse_args()
    await explore_workflow(args.blog_id, args.cdp_url)


if __name__ == "__main__":
    asyncio.run(main())
