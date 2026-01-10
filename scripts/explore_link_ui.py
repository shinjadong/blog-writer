#!/usr/bin/env python3
"""
링크 삽입 UI 탐색

네이버 에디터의 링크 삽입 UI를 자세히 탐색합니다.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def explore_link_ui():
    """링크 삽입 UI 탐색"""

    print("\n" + "="*60)
    print("링크 삽입 UI 탐색")
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
                        const cancelBtn = popup.querySelector('button');
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

        # 1. 전체 툴바 구조 탐색
        print("\n1. 전체 툴바 버튼 탐색:")
        toolbar_info = await publisher._evaluate_js("""
            (() => {
                const result = { main_toolbar: [], secondary_toolbar: [], all_buttons: [] };

                // 모든 버튼과 클릭 가능 요소 찾기
                const allClickable = document.querySelectorAll('button, [role="button"], [data-name], .se-toolbar-item');
                for (const el of allClickable) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 10 && rect.height > 10 && rect.y < 120) {  // 상단 120px 이내
                        const text = el.innerText?.trim() || '';
                        const dataName = el.getAttribute('data-name') || '';
                        const className = el.className || '';
                        const title = el.getAttribute('title') || '';

                        result.all_buttons.push({
                            text: text.substring(0, 20),
                            dataName: dataName,
                            title: title,
                            className: className.substring(0, 50),
                            coords: [Math.round(rect.x + rect.width/2), Math.round(rect.y + rect.height/2)],
                            rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) }
                        });
                    }
                }

                return result;
            })()
        """)

        print(f"   발견된 버튼 수: {len(toolbar_info.get('all_buttons', []))}")
        for btn in toolbar_info.get('all_buttons', []):
            if btn.get('dataName') or '링크' in btn.get('text', '') or 'link' in btn.get('dataName', '').lower():
                print(f"   * {btn}")

        # 2. data-name="oglink" 버튼 상세 정보
        print("\n2. data-name='oglink' 상세:")
        oglink_detail = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="oglink"]');
                if (!btn) return { found: false };

                const rect = btn.getBoundingClientRect();
                return {
                    found: true,
                    tagName: btn.tagName,
                    className: btn.className,
                    innerHTML: btn.innerHTML.substring(0, 200),
                    outerHTML: btn.outerHTML.substring(0, 300),
                    coords: [rect.x + rect.width/2, rect.y + rect.height/2],
                    parentClass: btn.parentElement?.className || ''
                };
            })()
        """)
        print(f"   {oglink_detail}")

        # 3. 본문에 텍스트 입력 후 선택
        print("\n3. 본문에 텍스트 입력 후 선택...")
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

        if body_info and body_info.get("found"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.2)
            await publisher._type_text("테스트 링크")
            await asyncio.sleep(0.3)

            # 텍스트 선택 (Ctrl+A)
            print("   텍스트 전체 선택 (Ctrl+Shift+Left)...")
            # Shift+Home으로 줄 시작까지 선택
            for _ in range(6):  # "테스트 링크" 6글자
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "ArrowLeft", "code": "ArrowLeft",
                    "modifiers": 8  # Shift
                })
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "ArrowLeft", "code": "ArrowLeft"
                })
                await asyncio.sleep(0.02)

        await asyncio.sleep(0.5)

        # 4. 선택 후 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_text_selected.png")
        print("   텍스트 선택 스크린샷 저장")

        # 5. 링크 버튼 클릭 (텍스트 선택 상태에서)
        print("\n4. 텍스트 선택 상태에서 oglink 클릭...")
        oglink = await publisher._evaluate_js("""
            document.querySelector('[data-name="oglink"]')?.getBoundingClientRect()
        """)
        if oglink:
            await publisher._click_at(oglink['x'] + oglink['width']/2, oglink['y'] + oglink['height']/2)
            await asyncio.sleep(1)

        # 6. UI 변화 확인
        print("\n5. UI 변화 확인...")
        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_after_oglink.png")

        ui_state = await publisher._evaluate_js("""
            (() => {
                const result = {
                    popups: [],
                    panels: [],
                    inputs: [],
                    selection: null
                };

                // 모든 팝업/패널/레이어 확인
                const containers = document.querySelectorAll('.se-popup, .se-layer, .se-panel, [class*="popup"], [class*="layer"], [class*="panel"], [class*="modal"]');
                for (const el of containers) {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (rect.width > 50 && style.display !== 'none' && style.visibility !== 'hidden') {
                        result.panels.push({
                            className: el.className.substring(0, 100),
                            rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) },
                            innerHTML_preview: el.innerHTML.substring(0, 200)
                        });

                        // 이 컨테이너 내의 입력 필드
                        const inputs = el.querySelectorAll('input, textarea, [contenteditable="true"]');
                        for (const inp of inputs) {
                            const inpRect = inp.getBoundingClientRect();
                            if (inpRect.width > 30) {
                                result.inputs.push({
                                    type: inp.tagName,
                                    placeholder: inp.placeholder || '',
                                    contentEditable: inp.contentEditable,
                                    coords: [Math.round(inpRect.x + inpRect.width/2), Math.round(inpRect.y + inpRect.height/2)]
                                });
                            }
                        }
                    }
                }

                // 현재 선택 상태
                const sel = window.getSelection();
                if (sel && sel.toString()) {
                    result.selection = sel.toString();
                }

                return result;
            })()
        """)

        print(f"   패널/팝업 수: {len(ui_state.get('panels', []))}")
        for panel in ui_state.get('panels', [])[:5]:
            print(f"   - {panel.get('className', '')[:60]}")
            print(f"     위치: {panel.get('rect')}")

        print(f"\n   입력 필드: {ui_state.get('inputs', [])}")
        print(f"   선택된 텍스트: {ui_state.get('selection')}")

        # 7. Ctrl+K 단축키 시도 (링크 삽입 단축키)
        print("\n6. Ctrl+K 단축키 시도 (링크 삽입)...")
        await publisher.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "k", "code": "KeyK",
            "modifiers": 2  # Ctrl
        })
        await publisher.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "k", "code": "KeyK"
        })
        await asyncio.sleep(1)

        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_after_ctrlk.png")

        ui_state2 = await publisher._evaluate_js("""
            (() => {
                const result = { inputs: [], panels: [] };
                const containers = document.querySelectorAll('.se-popup, .se-layer, [class*="link"], [class*="oglink"]');
                for (const el of containers) {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (rect.width > 50 && style.display !== 'none') {
                        result.panels.push({
                            className: el.className,
                            rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) }
                        });

                        const inputs = el.querySelectorAll('input, textarea');
                        for (const inp of inputs) {
                            const inpRect = inp.getBoundingClientRect();
                            result.inputs.push({
                                placeholder: inp.placeholder,
                                coords: [Math.round(inpRect.x + inpRect.width/2), Math.round(inpRect.y + inpRect.height/2)]
                            });
                        }
                    }
                }
                return result;
            })()
        """)
        print(f"   Ctrl+K 후 패널: {ui_state2.get('panels', [])}")
        print(f"   Ctrl+K 후 입력: {ui_state2.get('inputs', [])}")

        print("\n" + "="*60)
        print("탐색 완료")
        print("="*60)

        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"\n탐색 실패: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


if __name__ == "__main__":
    asyncio.run(explore_link_ui())
