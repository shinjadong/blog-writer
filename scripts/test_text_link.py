#!/usr/bin/env python3
"""
text-link 버튼 테스트 (하이퍼링크)

secondary toolbar의 링크 버튼 테스트
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def test_text_link():
    """text-link 버튼 테스트"""

    print("\n" + "="*60)
    print("text-link 버튼 테스트 (하이퍼링크)")
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

        # 본문에 텍스트 입력
        print("\n1. 본문에 텍스트 입력...")
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
            await asyncio.sleep(0.2)
            await publisher._type_text("네이버 바로가기")
            await asyncio.sleep(0.3)

        # 텍스트 선택
        print("   텍스트 선택 중...")
        for _ in range(8):  # "네이버 바로가기" 8글자
            await publisher.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "ArrowLeft", "code": "ArrowLeft",
                "modifiers": 8  # Shift
            })
            await publisher.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "ArrowLeft", "code": "ArrowLeft"
            })
            await asyncio.sleep(0.02)

        await asyncio.sleep(0.3)

        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_before_textlink.png")

        # text-link 버튼 찾기
        print("\n2. text-link 버튼 클릭...")
        textlink_info = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="text-link"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return { found: true, coords: [rect.x + rect.width/2, rect.y + rect.height/2], text: btn.innerText };
                }
                return { found: false };
            })()
        """)
        print(f"   text-link 버튼: {textlink_info}")

        if textlink_info and textlink_info.get("found"):
            await publisher._click_at(*textlink_info["coords"])
            await asyncio.sleep(1)

        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_after_textlink.png")

        # 3. 팝업/레이어 확인
        print("\n3. UI 변화 확인...")
        ui_state = await publisher._evaluate_js("""
            (() => {
                const result = { popups: [], inputs: [] };

                // 모든 가시적인 레이어/팝업
                const layers = document.querySelectorAll('.se-popup, .se-layer, [class*="layer"], [class*="link"]');
                layers.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    const style = getComputedStyle(el);
                    if (rect.width > 50 && rect.height > 30 && style.display !== 'none' && style.visibility !== 'hidden') {
                        result.popups.push({
                            className: el.className.substring(0, 80),
                            rect: {x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height)}
                        });

                        // 내부 입력 필드
                        el.querySelectorAll('input, textarea').forEach(inp => {
                            const inpRect = inp.getBoundingClientRect();
                            if (inpRect.width > 30) {
                                result.inputs.push({
                                    type: inp.type,
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

        print(f"   팝업/레이어: {len(ui_state.get('popups', []))}")
        for popup in ui_state.get('popups', []):
            print(f"      - {popup}")

        print(f"   입력 필드: {ui_state.get('inputs', [])}")

        # 4. 입력 필드가 있으면 URL 입력
        if ui_state.get('inputs'):
            print("\n4. URL 입력 시도...")
            input_coords = ui_state['inputs'][0]['coords']
            await publisher._click_at(input_coords[0], input_coords[1])
            await asyncio.sleep(0.2)
            await publisher._type_text("https://naver.com")
            await asyncio.sleep(1)

            await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_url_entered.png")

            # 확인 버튼 찾기
            confirm_info = await publisher._evaluate_js("""
                (() => {
                    const layers = document.querySelectorAll('.se-popup, .se-layer, [class*="layer"]');
                    for (const layer of layers) {
                        const rect = layer.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 30) {
                            const btns = layer.querySelectorAll('button');
                            for (const btn of btns) {
                                const text = btn.innerText?.trim() || '';
                                if (text === '확인' || text === '적용' || text === '등록') {
                                    const btnRect = btn.getBoundingClientRect();
                                    return {
                                        found: true,
                                        text: text,
                                        coords: [btnRect.x + btnRect.width/2, btnRect.y + btnRect.height/2]
                                    };
                                }
                            }
                        }
                    }
                    return { found: false };
                })()
            """)

            if confirm_info and confirm_info.get("found"):
                print(f"   확인 버튼: {confirm_info}")
                await publisher._click_at(*confirm_info["coords"])
                await asyncio.sleep(1)
                await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_link_applied.png")
                print("   링크 적용 완료!")
            else:
                # Enter 키 시도
                print("   확인 버튼 없음 - Enter 키 시도")
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Enter", "code": "Enter",
                    "windowsVirtualKeyCode": 13
                })
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Enter", "code": "Enter"
                })
                await asyncio.sleep(1)
                await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_link_applied.png")

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
    asyncio.run(test_text_link())
