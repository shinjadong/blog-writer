#!/usr/bin/env python3
"""링크 삽입 기능 집중 테스트"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def test_link():
    print("\n" + "="*60)
    print("링크 삽입 기능 테스트")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        screenshot_dir="data/link_test"
    )
    Path(config.screenshot_dir).mkdir(parents=True, exist_ok=True)

    publisher = AdaptivePublisher(config)

    try:
        await publisher._init_browser()
        print("브라우저 초기화 완료")

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

        # 본문 영역으로 이동
        print("\n1. 본문 영역 클릭...")
        dom = await publisher._get_dom_snapshot()
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        # 텍스트 입력
        link_text = "네이버 바로가기"
        print(f"\n2. 텍스트 입력: '{link_text}'")
        await publisher._type_text(link_text)
        await asyncio.sleep(0.5)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_01_text_typed.png")

        # 방법 1: 트리플 클릭으로 선택
        print("\n3. 방법 1: 트리플 클릭으로 선택 시도...")

        # 현재 커서 위치에서 트리플 클릭
        cursor_pos = await publisher._evaluate_js("""
            (() => {
                const selection = window.getSelection();
                if (selection.rangeCount > 0) {
                    const range = selection.getRangeAt(0);
                    const rect = range.getBoundingClientRect();
                    return { x: rect.x, y: rect.y };
                }
                return null;
            })()
        """)

        if cursor_pos:
            # 트리플 클릭
            for _ in range(3):
                await publisher.cdp.send("Input.dispatchMouseEvent", {
                    "type": "mousePressed", "x": cursor_pos["x"], "y": cursor_pos["y"],
                    "button": "left", "clickCount": 1
                })
                await publisher.cdp.send("Input.dispatchMouseEvent", {
                    "type": "mouseReleased", "x": cursor_pos["x"], "y": cursor_pos["y"],
                    "button": "left", "clickCount": 1
                })
                await asyncio.sleep(0.05)

        await asyncio.sleep(0.5)
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_02_after_triple_click.png")

        # 선택된 텍스트 확인
        selected = await publisher._evaluate_js("window.getSelection().toString()")
        print(f"   선택된 텍스트: '{selected}'")

        # text-link 버튼 확인
        textlink_info = await publisher._evaluate_js("""
            (() => {
                const btn = document.querySelector('[data-name="text-link"]');
                if (btn) {
                    const rect = btn.getBoundingClientRect();
                    return {
                        found: true,
                        visible: rect.width > 0,
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2],
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                    };
                }
                return { found: false };
            })()
        """)
        print(f"   text-link 버튼: {textlink_info}")

        # 방법 2: Ctrl+A 사용
        if not textlink_info or not textlink_info.get("visible"):
            print("\n4. 방법 2: Ctrl+A로 선택 시도...")
            await publisher._press_escape()
            await asyncio.sleep(0.2)

            # 본문 다시 클릭
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.2)

            # Ctrl+A
            await publisher.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "a", "code": "KeyA",
                "modifiers": 2  # Ctrl
            })
            await publisher.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "a", "code": "KeyA"
            })
            await asyncio.sleep(0.5)

            await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_03_after_ctrl_a.png")

            selected = await publisher._evaluate_js("window.getSelection().toString()")
            print(f"   선택된 텍스트: '{selected}'")

            textlink_info = await publisher._evaluate_js("""
                (() => {
                    const btn = document.querySelector('[data-name="text-link"]');
                    if (btn) {
                        const rect = btn.getBoundingClientRect();
                        return {
                            found: true,
                            visible: rect.width > 0,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                        };
                    }
                    return { found: false };
                })()
            """)
            print(f"   text-link 버튼: {textlink_info}")

        # 방법 3: 마우스 드래그로 선택
        if not textlink_info or not textlink_info.get("visible"):
            print("\n5. 방법 3: 마우스 드래그로 선택...")
            await publisher._press_escape()
            await asyncio.sleep(0.2)

            # 텍스트의 시작과 끝 위치 찾기
            text_bounds = await publisher._evaluate_js("""
                (() => {
                    const paragraphs = document.querySelectorAll('.se-text-paragraph');
                    for (const p of paragraphs) {
                        const text = p.innerText?.trim();
                        if (text && text.includes('네이버')) {
                            const rect = p.getBoundingClientRect();
                            return {
                                found: true,
                                startX: rect.x + 5,
                                endX: rect.x + rect.width - 5,
                                y: rect.y + rect.height / 2
                            };
                        }
                    }
                    return { found: false };
                })()
            """)
            print(f"   텍스트 영역: {text_bounds}")

            if text_bounds and text_bounds.get("found"):
                # 드래그 선택
                await publisher.cdp.send("Input.dispatchMouseEvent", {
                    "type": "mousePressed",
                    "x": text_bounds["startX"], "y": text_bounds["y"],
                    "button": "left", "clickCount": 1
                })
                await asyncio.sleep(0.1)
                await publisher.cdp.send("Input.dispatchMouseEvent", {
                    "type": "mouseMoved",
                    "x": text_bounds["endX"], "y": text_bounds["y"],
                    "button": "left"
                })
                await asyncio.sleep(0.1)
                await publisher.cdp.send("Input.dispatchMouseEvent", {
                    "type": "mouseReleased",
                    "x": text_bounds["endX"], "y": text_bounds["y"],
                    "button": "left", "clickCount": 1
                })
                await asyncio.sleep(0.5)

                await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_04_after_drag.png")

                selected = await publisher._evaluate_js("window.getSelection().toString()")
                print(f"   선택된 텍스트: '{selected}'")

                textlink_info = await publisher._evaluate_js("""
                    (() => {
                        const btn = document.querySelector('[data-name="text-link"]');
                        if (btn) {
                            const rect = btn.getBoundingClientRect();
                            return {
                                found: true,
                                visible: rect.width > 0,
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                            };
                        }
                        return { found: false };
                    })()
                """)
                print(f"   text-link 버튼: {textlink_info}")

        # 링크 버튼 클릭 시도
        if textlink_info and textlink_info.get("visible"):
            print("\n6. text-link 버튼 클릭...")
            await publisher._click_at(*textlink_info["coords"])
            await asyncio.sleep(1)

            await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_05_after_link_btn.png")

            # URL 입력 필드 찾기
            url_input = await publisher._evaluate_js("""
                (() => {
                    const inputs = document.querySelectorAll('input');
                    for (const inp of inputs) {
                        const rect = inp.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 0) {
                            const placeholder = inp.placeholder || '';
                            const type = inp.type || 'text';
                            return {
                                found: true,
                                placeholder: placeholder,
                                type: type,
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                            };
                        }
                    }
                    return { found: false };
                })()
            """)
            print(f"   URL 입력 필드: {url_input}")

            if url_input and url_input.get("found"):
                await publisher._click_at(*url_input["coords"])
                await asyncio.sleep(0.1)
                await publisher._type_text("https://naver.com")
                await asyncio.sleep(0.3)

                # Enter
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Enter",
                    "code": "Enter", "windowsVirtualKeyCode": 13
                })
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Enter",
                    "code": "Enter", "windowsVirtualKeyCode": 13
                })
                await asyncio.sleep(1)

                await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_06_link_done.png")
                print("   링크 삽입 완료!")

        print("\n" + "="*60)
        print("테스트 완료")
        print(f"스크린샷: {config.screenshot_dir}/{timestamp}_*.png")
        print("="*60)

        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(5)

    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


if __name__ == "__main__":
    asyncio.run(test_link())
