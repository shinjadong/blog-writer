#!/usr/bin/env python3
"""
네이버 스마트에디터 고급 기능 탐색

이미지 업로드와 OGLink 기능의 DOM 구조를 파악합니다:
1. 숨겨진 file input 요소 탐색
2. 이미지 버튼 클릭 시 동작 확인
3. OGLink 모달 구조 탐색
"""

import asyncio
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "data" / "advanced_explore"
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


async def explore_file_inputs(cdp):
    """숨겨진 file input 요소 탐색"""

    print("\n" + "="*60)
    print("🔍 1. 숨겨진 File Input 탐색")
    print("="*60)

    file_inputs = await evaluate_js(cdp, """
        (() => {
            const inputs = document.querySelectorAll('input[type="file"]');
            const result = [];

            for (const input of inputs) {
                const style = getComputedStyle(input);
                const rect = input.getBoundingClientRect();

                result.push({
                    id: input.id || '',
                    name: input.name || '',
                    className: input.className || '',
                    accept: input.accept || '',
                    multiple: input.multiple,
                    display: style.display,
                    visibility: style.visibility,
                    opacity: style.opacity,
                    position: style.position,
                    rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height },
                    hidden: input.hidden,
                    disabled: input.disabled,
                    parentClass: input.parentElement?.className || '',
                    outerHTML: input.outerHTML.substring(0, 200)
                });
            }

            return result;
        })()
    """)

    if file_inputs:
        print(f"\n📁 발견된 file input 개수: {len(file_inputs)}")
        for i, inp in enumerate(file_inputs):
            print(f"\n--- File Input #{i+1} ---")
            print(f"   ID: {inp.get('id', 'N/A')}")
            print(f"   Name: {inp.get('name', 'N/A')}")
            print(f"   Class: {inp.get('className', 'N/A')}")
            print(f"   Accept: {inp.get('accept', 'N/A')}")
            print(f"   Multiple: {inp.get('multiple', False)}")
            print(f"   Display: {inp.get('display')}, Visibility: {inp.get('visibility')}")
            print(f"   Position: {inp.get('position')}, Opacity: {inp.get('opacity')}")
            print(f"   Rect: {inp.get('rect')}")
            print(f"   Parent Class: {inp.get('parentClass', 'N/A')[:50]}")
            print(f"   HTML: {inp.get('outerHTML', '')[:100]}...")
    else:
        print("\n⚠️ File input을 찾을 수 없습니다")

    return file_inputs


async def explore_image_button(cdp, page):
    """이미지 버튼 클릭 후 DOM 변화 감지"""

    print("\n\n" + "="*60)
    print("🖼️ 2. 이미지 버튼 클릭 테스트")
    print("="*60)

    # 이미지 버튼 찾기
    img_btn = await evaluate_js(cdp, """
        (() => {
            const btn = document.querySelector('[data-name="image"]');
            if (btn) {
                const rect = btn.getBoundingClientRect();
                return { x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true };
            }
            return { found: false };
        })()
    """)

    if not img_btn or not img_btn.get('found'):
        print("❌ 이미지 버튼을 찾을 수 없습니다")
        return

    print(f"✅ 이미지 버튼 위치: ({img_btn['x']:.0f}, {img_btn['y']:.0f})")

    # 클릭 전 file input 개수 확인
    before_count = await evaluate_js(cdp, """
        document.querySelectorAll('input[type="file"]').length
    """)
    print(f"   클릭 전 file input 개수: {before_count}")

    # 이미지 버튼 클릭
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": img_btn['x'], "y": img_btn['y'],
        "button": "left", "clickCount": 1
    })
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": img_btn['x'], "y": img_btn['y'],
        "button": "left", "clickCount": 1
    })

    print("   🖱️ 이미지 버튼 클릭")

    # 대기 (팝업 로딩)
    await asyncio.sleep(1)

    # 클릭 후 file input 개수 확인
    after_count = await evaluate_js(cdp, """
        document.querySelectorAll('input[type="file"]').length
    """)
    print(f"   클릭 후 file input 개수: {after_count}")

    # 새로 나타난 모달/팝업 확인
    modals = await evaluate_js(cdp, """
        (() => {
            const result = [];

            // 팝업/모달 찾기
            const popups = document.querySelectorAll('.se-popup, [class*="modal"], [class*="dialog"], [class*="layer"]');
            for (const popup of popups) {
                const style = getComputedStyle(popup);
                const rect = popup.getBoundingClientRect();

                if (rect.width > 0 && rect.height > 0 && style.display !== 'none') {
                    result.push({
                        className: popup.className,
                        tagName: popup.tagName,
                        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                    });
                }
            }

            return result;
        })()
    """)

    if modals:
        print(f"\n   📦 출현한 모달/팝업: {len(modals)}개")
        for modal in modals:
            print(f"      - {modal.get('className', 'N/A')[:60]}")

    # 스크린샷
    timestamp = datetime.now().strftime("%H%M%S")
    await page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_after_image_click.png"))
    print(f"   📸 스크린샷 저장됨")

    # 새로 생성된 file input 상세 정보
    if after_count > before_count:
        print("\n   🆕 새로 생성된 file input 발견!")
        new_inputs = await explore_file_inputs(cdp)


async def explore_oglink(cdp, page):
    """OGLink 버튼 클릭 후 모달 구조 탐색"""

    print("\n\n" + "="*60)
    print("🔗 3. OGLink(글감) 모달 탐색")
    print("="*60)

    # OGLink 버튼 찾기
    oglink_btn = await evaluate_js(cdp, """
        (() => {
            const btn = document.querySelector('[data-name="oglink"]');
            if (btn) {
                const rect = btn.getBoundingClientRect();
                return { x: rect.x + rect.width/2, y: rect.y + rect.height/2, found: true };
            }
            return { found: false };
        })()
    """)

    if not oglink_btn or not oglink_btn.get('found'):
        print("❌ OGLink 버튼을 찾을 수 없습니다")
        return

    print(f"✅ OGLink 버튼 위치: ({oglink_btn['x']:.0f}, {oglink_btn['y']:.0f})")

    # OGLink 버튼 클릭
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mousePressed",
        "x": oglink_btn['x'], "y": oglink_btn['y'],
        "button": "left", "clickCount": 1
    })
    await cdp.send("Input.dispatchMouseEvent", {
        "type": "mouseReleased",
        "x": oglink_btn['x'], "y": oglink_btn['y'],
        "button": "left", "clickCount": 1
    })

    print("   🖱️ OGLink 버튼 클릭")

    # 대기 (모달 로딩)
    await asyncio.sleep(1.5)

    # 스크린샷
    timestamp = datetime.now().strftime("%H%M%S")
    await page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_oglink_modal.png"))
    print(f"   📸 스크린샷 저장됨")

    # 모달 구조 분석
    modal_info = await evaluate_js(cdp, """
        (() => {
            const result = {
                found: false,
                modalClass: '',
                inputs: [],
                buttons: [],
                structure: ''
            };

            // se-popup 또는 oglink 관련 모달 찾기
            const modals = document.querySelectorAll('.se-popup, [class*="oglink"], [class*="link-layer"]');

            for (const modal of modals) {
                const rect = modal.getBoundingClientRect();
                if (rect.width > 100 && rect.height > 100) {
                    result.found = true;
                    result.modalClass = modal.className;

                    // 입력 필드 찾기
                    const inputs = modal.querySelectorAll('input, textarea');
                    for (const input of inputs) {
                        const inputRect = input.getBoundingClientRect();
                        result.inputs.push({
                            type: input.type || 'text',
                            placeholder: input.placeholder || '',
                            className: input.className,
                            name: input.name || '',
                            rect: { x: inputRect.x, y: inputRect.y, w: inputRect.width, h: inputRect.height }
                        });
                    }

                    // 버튼 찾기
                    const buttons = modal.querySelectorAll('button');
                    for (const btn of buttons) {
                        const btnRect = btn.getBoundingClientRect();
                        if (btnRect.width > 0) {
                            result.buttons.push({
                                text: btn.innerText?.trim() || '',
                                className: btn.className,
                                rect: { x: btnRect.x, y: btnRect.y, w: btnRect.width, h: btnRect.height }
                            });
                        }
                    }

                    // 전체 구조 (간략)
                    result.structure = modal.innerHTML.substring(0, 500);

                    break;
                }
            }

            return result;
        })()
    """)

    if modal_info and modal_info.get('found'):
        print(f"\n✅ 모달 발견!")
        print(f"   Class: {modal_info.get('modalClass', 'N/A')[:80]}")

        print(f"\n   📝 입력 필드 ({len(modal_info.get('inputs', []))}개):")
        for inp in modal_info.get('inputs', []):
            print(f"      - Type: {inp.get('type')}, Placeholder: {inp.get('placeholder', 'N/A')}")
            print(f"        Class: {inp.get('className', 'N/A')[:50]}")
            print(f"        Rect: {inp.get('rect')}")

        print(f"\n   🔘 버튼 ({len(modal_info.get('buttons', []))}개):")
        for btn in modal_info.get('buttons', []):
            print(f"      - '{btn.get('text')}' @ ({btn.get('rect', {}).get('x', 0):.0f}, {btn.get('rect', {}).get('y', 0):.0f})")
            print(f"        Class: {btn.get('className', 'N/A')[:50]}")
    else:
        print("\n⚠️ 모달을 찾을 수 없습니다")

        # 전체 페이지에서 URL 입력 필드 검색
        url_inputs = await evaluate_js(cdp, """
            (() => {
                const inputs = document.querySelectorAll('input[placeholder*="링크"], input[placeholder*="URL"], input[placeholder*="http"]');
                return Array.from(inputs).map(inp => ({
                    placeholder: inp.placeholder,
                    className: inp.className,
                    visible: getComputedStyle(inp).display !== 'none'
                }));
            })()
        """)

        if url_inputs:
            print(f"\n   발견된 URL 관련 input: {url_inputs}")

    # ESC로 모달 닫기
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
    print("\n   ⌨️ ESC로 모달 닫기")


async def explore_material_buttons(cdp):
    """하단 글감 버튼들 탐색"""

    print("\n\n" + "="*60)
    print("📚 4. 하단 글감 버튼 탐색")
    print("="*60)

    material_btns = await evaluate_js(cdp, """
        (() => {
            const result = [];
            const btns = document.querySelectorAll('button');

            for (const btn of btns) {
                const text = btn.innerText?.trim() || '';
                if (text.includes('글감')) {
                    const rect = btn.getBoundingClientRect();
                    result.push({
                        text: text,
                        className: btn.className,
                        dataName: btn.getAttribute('data-name'),
                        rect: { x: rect.x + rect.width/2, y: rect.y + rect.height/2 }
                    });
                }
            }

            return result;
        })()
    """)

    if material_btns:
        print(f"\n📦 글감 버튼 ({len(material_btns)}개):")
        for btn in material_btns:
            print(f"   - '{btn.get('text')}' @ ({btn.get('rect', {}).get('x', 0):.0f}, {btn.get('rect', {}).get('y', 0):.0f})")
    else:
        print("\n⚠️ 글감 버튼을 찾을 수 없습니다")


async def main():
    from playwright.async_api import async_playwright

    print("\n" + "="*60)
    print("🔍 네이버 스마트에디터 고급 기능 탐색")
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
        for p in pages:
            if "blog.naver.com" in p.url and "postwrite" in p.url:
                page = p
                break

        if not page:
            print("\n⚠️ 에디터 페이지를 찾을 수 없습니다")
            return

        print(f"📍 페이지: {page.url}")

        cdp = await get_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("Runtime.enable")

        # 탐색 실행
        await explore_file_inputs(cdp)
        await explore_image_button(cdp, page)
        await asyncio.sleep(1)
        await explore_oglink(cdp, page)
        await explore_material_buttons(cdp)

        print("\n\n" + "="*60)
        print("✅ 탐색 완료!")
        print(f"📁 스크린샷 위치: {SCREENSHOT_DIR}")
        print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
