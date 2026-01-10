#!/usr/bin/env python3
"""
링크 버튼 탐색 테스트

에디터의 링크 관련 버튼/요소를 탐색합니다.
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def explore_link_buttons():
    """링크 버튼 탐색"""

    print("\n" + "="*60)
    print("링크 버튼 탐색")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        screenshot_dir="data/link_explore"
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

        # 1. 본문 영역으로 이동하여 텍스트 입력
        print("\n1. 본문에 텍스트 입력...")
        dom = await publisher._get_dom_snapshot()
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        await publisher._type_text("링크 테스트 텍스트")
        await asyncio.sleep(0.5)

        # 2. 텍스트 선택
        print("\n2. 텍스트 선택...")
        for _ in range(10):  # "링크 테스트 텍스트" 선택
            await publisher.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown", "key": "ArrowLeft", "code": "ArrowLeft",
                "modifiers": 8  # Shift
            })
            await publisher.cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp", "key": "ArrowLeft", "code": "ArrowLeft"
            })
            await asyncio.sleep(0.01)

        await asyncio.sleep(0.5)
        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_01_text_selected.png")

        # 3. 링크 관련 버튼 탐색
        print("\n3. 링크 관련 버튼 탐색...")

        link_elements = await publisher._evaluate_js("""
            (() => {
                const results = [];

                // data-name 속성으로 찾기
                const dataNameButtons = document.querySelectorAll('[data-name]');
                dataNameButtons.forEach(btn => {
                    const name = btn.getAttribute('data-name');
                    if (name.includes('link') || name.includes('url') || name.includes('og')) {
                        const rect = btn.getBoundingClientRect();
                        results.push({
                            type: 'data-name',
                            name: name,
                            visible: rect.width > 0 && rect.height > 0,
                            coords: rect.width > 0 ? [rect.x + rect.width/2, rect.y + rect.height/2] : null,
                            html: btn.outerHTML.substring(0, 300)
                        });
                    }
                });

                // 링크 아이콘 버튼 (툴바)
                const allButtons = document.querySelectorAll('button');
                allButtons.forEach(btn => {
                    const text = btn.innerText?.trim() || '';
                    const ariaLabel = btn.getAttribute('aria-label') || '';
                    const title = btn.getAttribute('title') || '';
                    const className = btn.className || '';

                    if (text.includes('링크') || ariaLabel.includes('링크') ||
                        title.includes('링크') || className.includes('link')) {
                        const rect = btn.getBoundingClientRect();
                        results.push({
                            type: 'button',
                            text: text,
                            ariaLabel: ariaLabel,
                            title: title,
                            visible: rect.width > 0,
                            coords: rect.width > 0 ? [rect.x + rect.width/2, rect.y + rect.height/2] : null
                        });
                    }
                });

                // 툴바의 모든 버튼 (현재 보이는 것)
                const visibleToolbarBtns = [];
                const toolbar = document.querySelector('.se-toolbar, [class*="toolbar"]');
                if (toolbar) {
                    const btns = toolbar.querySelectorAll('button');
                    btns.forEach(btn => {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            visibleToolbarBtns.push({
                                dataName: btn.getAttribute('data-name'),
                                text: btn.innerText?.trim().substring(0, 20),
                                title: btn.getAttribute('title'),
                                x: Math.round(rect.x),
                                y: Math.round(rect.y)
                            });
                        }
                    });
                }
                results.push({
                    type: 'visible-toolbar-buttons',
                    count: visibleToolbarBtns.length,
                    buttons: visibleToolbarBtns.slice(0, 30)
                });

                // 링크 텍스트 셀렉터로 찾기
                const linkBtn = document.querySelector('[data-name="link"], [data-name="text-link"], [data-name="hyperlink"]');
                if (linkBtn) {
                    const rect = linkBtn.getBoundingClientRect();
                    results.push({
                        type: 'link-selector',
                        found: true,
                        dataName: linkBtn.getAttribute('data-name'),
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                    });
                }

                return results;
            })()
        """)

        print(f"   발견된 요소: {len(link_elements)}개")
        for elem in link_elements:
            print(f"   - {elem.get('type')}: {elem}")

        # 4. Ctrl+K 단축키 시도
        print("\n4. Ctrl+K 단축키 시도...")
        await publisher.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyDown", "key": "k", "code": "KeyK",
            "modifiers": 2  # Ctrl
        })
        await publisher.cdp.send("Input.dispatchKeyEvent", {
            "type": "keyUp", "key": "k", "code": "KeyK"
        })
        await asyncio.sleep(1)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_02_after_ctrl_k.png")

        # 링크 입력 레이어가 나타났는지 확인
        link_layer = await publisher._evaluate_js("""
            (() => {
                const layers = document.querySelectorAll('.se-custom-layer, .se-layer, [class*="link-layer"], [class*="popup"]');
                const results = [];
                for (const layer of layers) {
                    const rect = layer.getBoundingClientRect();
                    const style = getComputedStyle(layer);
                    if (rect.width > 50 && style.display !== 'none' && style.visibility !== 'hidden') {
                        const inputs = layer.querySelectorAll('input');
                        const inputInfo = [];
                        inputs.forEach(inp => {
                            inputInfo.push({
                                type: inp.type,
                                placeholder: inp.placeholder,
                                className: inp.className
                            });
                        });
                        results.push({
                            className: layer.className,
                            width: rect.width,
                            height: rect.height,
                            inputs: inputInfo,
                            html: layer.innerHTML.substring(0, 500)
                        });
                    }
                }
                return results;
            })()
        """)

        print(f"   레이어 발견: {len(link_layer)}개")
        for layer in link_layer:
            print(f"   - {layer}")

        # 5. ESC로 닫고 다시 시도
        await publisher._press_escape()
        await asyncio.sleep(0.3)

        # 6. 툴바의 링크 버튼 직접 찾기
        print("\n5. 툴바에서 링크 버튼 직접 찾기...")

        # 256 (링크 아이콘의 x 좌표 근처) 위치의 버튼 확인
        toolbar_link = await publisher._evaluate_js("""
            (() => {
                // '링크' 텍스트를 가진 버튼
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    const text = btn.innerText?.trim() || '';
                    if (text === '링크' || text.includes('링크')) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {
                            return {
                                found: true,
                                text: text,
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2],
                                dataName: btn.getAttribute('data-name')
                            };
                        }
                    }
                }

                // data-name="oglink" 버튼
                const oglinkBtn = document.querySelector('[data-name="oglink"]');
                if (oglinkBtn) {
                    const rect = oglinkBtn.getBoundingClientRect();
                    return {
                        found: true,
                        type: 'oglink',
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                    };
                }

                return { found: false };
            })()
        """)

        print(f"   결과: {toolbar_link}")

        if toolbar_link and toolbar_link.get("found"):
            print("\n6. 링크 버튼 클릭...")
            await publisher._click_at(*toolbar_link["coords"])
            await asyncio.sleep(1)

            await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_03_after_link_click.png")

            # 링크 모달/레이어 확인
            modal_info = await publisher._evaluate_js("""
                (() => {
                    const modals = document.querySelectorAll('.se-popup, .se-layer, [class*="modal"], [class*="layer"]');
                    for (const modal of modals) {
                        const rect = modal.getBoundingClientRect();
                        const style = getComputedStyle(modal);
                        if (rect.width > 100 && style.display !== 'none') {
                            const inputs = modal.querySelectorAll('input');
                            const buttons = modal.querySelectorAll('button');
                            return {
                                found: true,
                                className: modal.className,
                                inputCount: inputs.length,
                                buttonCount: buttons.length,
                                html: modal.innerHTML.substring(0, 1000)
                            };
                        }
                    }
                    return { found: false };
                })()
            """)
            print(f"   모달 정보: {modal_info}")

        print("\n" + "="*60)
        print("탐색 완료")
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
    asyncio.run(explore_link_buttons())
