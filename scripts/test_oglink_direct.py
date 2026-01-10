#!/usr/bin/env python3
"""
OGLink 직접 클릭 테스트

oglink 버튼을 직접 클릭하고 결과 관찰
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def test_oglink_direct():
    """OGLink 직접 테스트"""

    print("\n" + "="*60)
    print("OGLink 직접 클릭 테스트")
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

        # 본문 클릭
        print("\n1. 본문 영역 클릭...")
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

        # 2. oglink 버튼 클릭
        print("\n2. oglink 버튼 클릭...")
        oglink_info = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="oglink"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2] };
                }
                return { found: false };
            })()
        """)
        if oglink_info.get("found"):
            await publisher._click_at(*oglink_info["coords"])
            print(f"   클릭: {oglink_info['coords']}")
            await asyncio.sleep(2)  # 충분히 대기

        # 3. 현재 화면 상태 확인
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_oglink_clicked.png")
        print(f"   스크린샷: {timestamp}_oglink_clicked.png")

        # 4. 전체 DOM에서 입력 필드와 팝업 찾기
        print("\n3. DOM 상태 확인...")
        ui_state = await publisher._evaluate_js("""
            (() => {
                const result = {
                    all_inputs: [],
                    all_textareas: [],
                    contenteditable: [],
                    visible_popups: [],
                    focused_element: null
                };

                // 활성화된 요소
                const active = document.activeElement;
                if (active) {
                    result.focused_element = {
                        tagName: active.tagName,
                        className: active.className?.substring(0, 50),
                        id: active.id,
                        type: active.type
                    };
                }

                // 모든 input 찾기
                document.querySelectorAll('input').forEach(inp => {
                    const rect = inp.getBoundingClientRect();
                    const style = getComputedStyle(inp);
                    if (rect.width > 30 && style.display !== 'none' && style.visibility !== 'hidden') {
                        result.all_inputs.push({
                            type: inp.type,
                            placeholder: inp.placeholder,
                            className: inp.className?.substring(0, 40),
                            coords: [Math.round(rect.x + rect.width/2), Math.round(rect.y + rect.height/2)],
                            visible: rect.y > 0 && rect.y < 800
                        });
                    }
                });

                // 모든 textarea 찾기
                document.querySelectorAll('textarea').forEach(ta => {
                    const rect = ta.getBoundingClientRect();
                    const style = getComputedStyle(ta);
                    if (rect.width > 30 && style.display !== 'none') {
                        result.all_textareas.push({
                            placeholder: ta.placeholder,
                            className: ta.className?.substring(0, 40),
                            coords: [Math.round(rect.x + rect.width/2), Math.round(rect.y + rect.height/2)]
                        });
                    }
                });

                // contenteditable 요소
                document.querySelectorAll('[contenteditable="true"]').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 30) {
                        result.contenteditable.push({
                            className: el.className?.substring(0, 40),
                            coords: [Math.round(rect.x + rect.width/2), Math.round(rect.y + rect.height/2)]
                        });
                    }
                });

                // 팝업/레이어 찾기
                const popupSelectors = '.se-popup, .se-layer, .se-oglink-layer, [class*="oglink"], [class*="link-layer"]';
                document.querySelectorAll(popupSelectors).forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (rect.width > 50 && style.display !== 'none' && style.visibility !== 'hidden') {
                        result.visible_popups.push({
                            className: el.className,
                            rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                            innerHTML: el.innerHTML.substring(0, 300)
                        });
                    }
                });

                return result;
            })()
        """)

        print(f"   포커스된 요소: {ui_state.get('focused_element')}")
        print(f"   입력 필드 수: {len(ui_state.get('all_inputs', []))}")
        for inp in ui_state.get('all_inputs', []):
            if inp.get('visible'):
                print(f"      - {inp}")

        print(f"   Textarea 수: {len(ui_state.get('all_textareas', []))}")
        print(f"   Contenteditable 수: {len(ui_state.get('contenteditable', []))}")
        print(f"   팝업/레이어 수: {len(ui_state.get('visible_popups', []))}")
        for popup in ui_state.get('visible_popups', []):
            print(f"      - {popup.get('className', '')[:60]}")
            print(f"        위치: {popup.get('rect')}")

        # 5. oglink 관련 특수 요소 찾기
        print("\n4. OGLink 관련 요소 찾기...")
        oglink_elements = await publisher._evaluate_js("""
            (() => {
                const result = [];
                // oglink 관련 클래스 검색
                const allElements = document.querySelectorAll('[class*="oglink"], [class*="og-link"], [data-name*="oglink"]');
                allElements.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    result.push({
                        tagName: el.tagName,
                        className: el.className,
                        id: el.id,
                        rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)},
                        display: getComputedStyle(el).display
                    });
                });
                return result;
            })()
        """)
        print(f"   발견된 oglink 요소: {len(oglink_elements)}")
        for el in oglink_elements[:10]:
            print(f"      - {el.get('tagName')} {el.get('className')[:50]}...")
            print(f"        {el.get('rect')}, display={el.get('display')}")

        # 6. 추가 대기 후 다시 확인
        print("\n5. 추가 2초 대기 후 확인...")
        await asyncio.sleep(2)

        ui_state2 = await publisher._evaluate_js("""
            (() => {
                const result = { popups: [], inputs: [] };
                document.querySelectorAll('.se-popup, .se-layer, [class*="layer"]').forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (rect.width > 100 && rect.height > 100 && style.display !== 'none') {
                        result.popups.push(el.className);

                        el.querySelectorAll('input, textarea').forEach(inp => {
                            const inpRect = inp.getBoundingClientRect();
                            if (inpRect.width > 50) {
                                result.inputs.push({
                                    placeholder: inp.placeholder,
                                    coords: [Math.round(inpRect.x + inpRect.width/2), Math.round(inpRect.y + inpRect.height/2)]
                                });
                            }
                        });
                    }
                });
                return result;
            })()
        """)
        print(f"   팝업: {ui_state2.get('popups', [])}")
        print(f"   입력: {ui_state2.get('inputs', [])}")

        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_oglink_final.png")

        print("\n" + "="*60)
        print("테스트 완료")
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
    asyncio.run(test_oglink_direct())
