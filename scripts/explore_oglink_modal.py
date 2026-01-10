#!/usr/bin/env python3
"""
OGLink 모달 구조 상세 탐색

글감 버튼 클릭 후 나타나는 모달의 정확한 구조를 파악합니다.
"""

import asyncio
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "data" / "oglink_explore"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def get_cdp_session(page):
    cdp = await page.context.new_cdp_session(page)
    return cdp


async def evaluate_js(cdp, expression: str):
    result = await cdp.send("Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True
    })
    return result.get("result", {}).get("value")


async def click_at(cdp, x, y):
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": x, "y": y,
        "button": "left", "clickCount": 1
    })
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": x, "y": y,
        "button": "left", "clickCount": 1
    })


async def explore_oglink_button(cdp, page):
    """글감 버튼 탐색 - 상단과 하단 모두"""

    print("\n" + "="*60)
    print("🔍 1. 글감 버튼 탐색")
    print("="*60)

    buttons = await evaluate_js(cdp, """
        (() => {
            const result = [];

            // data-name으로 찾기
            const oglink = document.querySelector('[data-name="oglink"]');
            if (oglink) {
                const rect = oglink.getBoundingClientRect();
                result.push({
                    type: 'data-name',
                    selector: '[data-name="oglink"]',
                    text: oglink.innerText?.trim() || '',
                    x: rect.x + rect.width/2,
                    y: rect.y + rect.height/2,
                    rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                });
            }

            // 텍스트로 찾기
            const allBtns = document.querySelectorAll('button');
            for (const btn of allBtns) {
                const text = btn.innerText?.trim() || '';
                if (text.includes('글감')) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0) {
                        result.push({
                            type: 'text-match',
                            text: text,
                            className: btn.className,
                            x: rect.x + rect.width/2,
                            y: rect.y + rect.height/2,
                            rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                        });
                    }
                }
            }

            return result;
        })()
    """)

    if buttons:
        print(f"\n📍 발견된 글감 버튼: {len(buttons)}개")
        for i, btn in enumerate(buttons):
            print(f"\n--- 버튼 #{i+1} ---")
            print(f"   Type: {btn.get('type')}")
            print(f"   Text: '{btn.get('text')}'")
            print(f"   Position: ({btn.get('x'):.0f}, {btn.get('y'):.0f})")
            print(f"   Rect: {btn.get('rect')}")
            if btn.get('className'):
                print(f"   Class: {btn.get('className')[:60]}")
    else:
        print("\n⚠️ 글감 버튼을 찾을 수 없습니다")

    return buttons


async def click_and_analyze_modal(cdp, page, btn_info):
    """버튼 클릭 후 모달 분석"""

    print(f"\n\n🖱️ 버튼 클릭: ({btn_info['x']:.0f}, {btn_info['y']:.0f})")
    await click_at(cdp, btn_info['x'], btn_info['y'])

    # 모달 로딩 대기
    await asyncio.sleep(1.5)

    # 스크린샷
    timestamp = datetime.now().strftime("%H%M%S")
    await page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_after_click.png"))
    print(f"📸 스크린샷 저장됨")

    # DOM 변화 분석
    print("\n" + "="*60)
    print("🔍 2. 클릭 후 DOM 분석")
    print("="*60)

    # 새로운 팝업/모달/레이어 찾기
    new_elements = await evaluate_js(cdp, """
        (() => {
            const result = {
                popups: [],
                layers: [],
                inputs: [],
                iframes: []
            };

            // 팝업/모달 요소
            const popupSelectors = [
                '.se-popup',
                '.se-layer',
                '[class*="popup"]',
                '[class*="modal"]',
                '[class*="layer"]',
                '[class*="dialog"]',
                '.se-oglink',
                '[class*="oglink"]'
            ];

            for (const sel of popupSelectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);

                    if (rect.width > 50 && rect.height > 50 &&
                        style.display !== 'none' && style.visibility !== 'hidden') {
                        result.popups.push({
                            selector: sel,
                            className: el.className,
                            id: el.id || '',
                            rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
                            html: el.outerHTML.substring(0, 300)
                        });
                    }
                }
            }

            // 입력 필드 찾기
            const inputs = document.querySelectorAll('input:not([type="hidden"]), textarea');
            for (const inp of inputs) {
                const rect = inp.getBoundingClientRect();
                const style = getComputedStyle(inp);

                if (rect.width > 50 && style.display !== 'none') {
                    result.inputs.push({
                        type: inp.type || 'text',
                        placeholder: inp.placeholder || '',
                        className: inp.className,
                        id: inp.id || '',
                        name: inp.name || '',
                        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                    });
                }
            }

            // iframe 확인
            const iframes = document.querySelectorAll('iframe');
            for (const iframe of iframes) {
                const rect = iframe.getBoundingClientRect();
                if (rect.width > 0) {
                    result.iframes.push({
                        src: iframe.src || '',
                        className: iframe.className,
                        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                    });
                }
            }

            return result;
        })()
    """)

    if new_elements:
        print(f"\n📦 팝업/모달 요소: {len(new_elements.get('popups', []))}개")
        for popup in new_elements.get('popups', []):
            print(f"\n   Selector: {popup.get('selector')}")
            print(f"   Class: {popup.get('className', '')[:80]}")
            print(f"   ID: {popup.get('id', 'N/A')}")
            print(f"   Rect: {popup.get('rect')}")
            print(f"   HTML preview: {popup.get('html', '')[:150]}...")

        print(f"\n📝 입력 필드: {len(new_elements.get('inputs', []))}개")
        for inp in new_elements.get('inputs', []):
            print(f"\n   Type: {inp.get('type')}")
            print(f"   Placeholder: '{inp.get('placeholder')}'")
            print(f"   Class: {inp.get('className', '')[:60]}")
            print(f"   Rect: {inp.get('rect')}")

        if new_elements.get('iframes'):
            print(f"\n🖼️ iframe: {len(new_elements.get('iframes', []))}개")
            for iframe in new_elements.get('iframes', []):
                print(f"   Src: {iframe.get('src', '')[:80]}")

    return new_elements


async def explore_bottom_toolbar(cdp, page):
    """하단 툴바 상세 분석"""

    print("\n\n" + "="*60)
    print("🔍 3. 하단 글감 툴바 분석")
    print("="*60)

    # 하단 툴바의 글감 버튼 찾기
    bottom_toolbar = await evaluate_js(cdp, """
        (() => {
            const result = {
                toolbar: null,
                buttons: []
            };

            // 하단 툴바 찾기 (y > 700 위치)
            const allBtns = document.querySelectorAll('button');
            for (const btn of allBtns) {
                const rect = btn.getBoundingClientRect();
                if (rect.y > 700 && rect.width > 30) {
                    const text = btn.innerText?.trim() || '';
                    result.buttons.push({
                        text: text,
                        className: btn.className,
                        dataName: btn.getAttribute('data-name') || '',
                        x: rect.x + rect.width/2,
                        y: rect.y + rect.height/2,
                        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                    });
                }
            }

            return result;
        })()
    """)

    if bottom_toolbar and bottom_toolbar.get('buttons'):
        print(f"\n📍 하단 버튼: {len(bottom_toolbar['buttons'])}개")
        for btn in bottom_toolbar['buttons']:
            text = btn.get('text', '')[:20]
            data_name = btn.get('dataName', '')
            print(f"   - '{text}' (data-name='{data_name}') @ ({btn.get('x'):.0f}, {btn.get('y'):.0f})")

    return bottom_toolbar


async def main():
    from playwright.async_api import async_playwright

    print("\n" + "="*60)
    print("🔗 OGLink 모달 구조 상세 탐색")
    print("="*60)

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            print("\n✅ Chrome CDP 연결 성공")
        except Exception as e:
            print(f"\n❌ Chrome CDP 연결 실패: {e}")
            return

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()

        # 에디터 페이지 찾기
        pages = context.pages
        page = None
        for pg in pages:
            if "blog.naver.com" in pg.url and "postwrite" in pg.url:
                page = pg
                break

        if not page:
            print("\n⚠️ 에디터 페이지를 찾을 수 없습니다")
            return

        print(f"📍 페이지: {page.url}")

        cdp = await get_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("Runtime.enable")

        # 1. 글감 버튼 탐색
        buttons = await explore_oglink_button(cdp, page)

        # 2. 하단 툴바 분석
        await explore_bottom_toolbar(cdp, page)

        # 3. 첫 번째 버튼 클릭 및 모달 분석
        if buttons:
            # 상단 data-name 버튼 우선
            target_btn = None
            for btn in buttons:
                if btn.get('type') == 'data-name':
                    target_btn = btn
                    break

            if not target_btn:
                target_btn = buttons[0]

            await click_and_analyze_modal(cdp, page, target_btn)

            # 모달이 열렸으면 추가 분석
            await asyncio.sleep(0.5)

            # 버튼들 분석
            modal_buttons = await evaluate_js(cdp, """
                (() => {
                    const btns = document.querySelectorAll('button');
                    const visible = [];

                    for (const btn of btns) {
                        const rect = btn.getBoundingClientRect();
                        const style = getComputedStyle(btn);

                        if (rect.width > 30 && rect.y > 100 && rect.y < 800 &&
                            style.display !== 'none') {
                            visible.push({
                                text: btn.innerText?.trim() || '',
                                className: btn.className,
                                x: rect.x + rect.width/2,
                                y: rect.y + rect.height/2
                            });
                        }
                    }

                    return visible;
                })()
            """)

            if modal_buttons:
                print(f"\n🔘 화면의 버튼들:")
                for btn in modal_buttons[:10]:
                    print(f"   - '{btn.get('text', '')}' @ ({btn.get('x'):.0f}, {btn.get('y'):.0f})")

        # ESC로 모달 닫기
        print("\n⌨️ ESC 키로 닫기...")
        await cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown",
            "key": "Escape",
            "code": "Escape",
            "windowsVirtualKeyCode": 27
        })
        await cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp",
            "key": "Escape",
            "code": "Escape",
            "windowsVirtualKeyCode": 27
        })

        print("\n" + "="*60)
        print("✅ 탐색 완료!")
        print(f"📁 스크린샷: {SCREENSHOT_DIR}")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
