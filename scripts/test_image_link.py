#!/usr/bin/env python3
"""이미지에 링크 삽입 기능 탐색"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig

TEST_IMAGE = "/home/tlswkehd/projects/cctv/OpenManus/assets/logo.jpg"


async def test_image_link():
    print("\n" + "="*60)
    print("이미지 링크 삽입 기능 탐색")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        screenshot_dir="data/image_link_test"
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

        # 본문 영역 클릭
        print("\n1. 본문 영역 클릭...")
        dom = await publisher._get_dom_snapshot()
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)

        # 이미지 업로드
        print("\n2. 이미지 업로드...")
        await publisher._handle_image_upload(TEST_IMAGE)
        await asyncio.sleep(2)

        await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_01_image_uploaded.png")

        # 3. 이미지 클릭하여 선택
        print("\n3. 이미지 클릭하여 선택...")
        image_element = await publisher._evaluate_js("""
            (() => {
                const images = document.querySelectorAll('.se-component.se-image, .se-image-resource img, .se-component.se-image img');
                for (const img of images) {
                    const rect = img.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 50) {
                        return {
                            found: true,
                            coords: [rect.x + rect.width/2, rect.y + rect.height/2],
                            width: rect.width,
                            height: rect.height
                        };
                    }
                }
                // 이미지 컴포넌트 찾기
                const imgComponent = document.querySelector('.se-component.se-image');
                if (imgComponent) {
                    const rect = imgComponent.getBoundingClientRect();
                    return {
                        found: true,
                        type: 'component',
                        coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                    };
                }
                return { found: false };
            })()
        """)
        print(f"   이미지 요소: {image_element}")

        if image_element and image_element.get("found"):
            await publisher._click_at(*image_element["coords"])
            await asyncio.sleep(0.5)

            await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_02_image_selected.png")

            # 4. 이미지 선택 후 나타나는 툴바/옵션 탐색
            print("\n4. 이미지 선택 후 툴바 탐색...")
            image_toolbar = await publisher._evaluate_js("""
                (() => {
                    const results = [];

                    // 이미지 관련 툴바 버튼들
                    const toolbarButtons = document.querySelectorAll('.se-component-toolbar button, .se-image-toolbar button, [class*="image"] button');
                    toolbarButtons.forEach(btn => {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {
                            results.push({
                                type: 'toolbar-button',
                                text: btn.innerText?.trim() || '',
                                title: btn.getAttribute('title') || '',
                                dataName: btn.getAttribute('data-name') || '',
                                ariaLabel: btn.getAttribute('aria-label') || '',
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2],
                                className: btn.className
                            });
                        }
                    });

                    // 링크 관련 버튼 찾기
                    const linkButtons = document.querySelectorAll('[data-name*="link"], [title*="링크"], [aria-label*="링크"]');
                    linkButtons.forEach(btn => {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {
                            results.push({
                                type: 'link-button',
                                dataName: btn.getAttribute('data-name'),
                                title: btn.getAttribute('title'),
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                            });
                        }
                    });

                    // 현재 보이는 모든 팝업/레이어
                    const layers = document.querySelectorAll('.se-popup, .se-layer, [class*="toolbar"]');
                    layers.forEach(layer => {
                        const rect = layer.getBoundingClientRect();
                        const style = getComputedStyle(layer);
                        if (rect.width > 50 && style.display !== 'none') {
                            results.push({
                                type: 'layer',
                                className: layer.className,
                                rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                            });
                        }
                    });

                    return results;
                })()
            """)

            print(f"   발견된 요소: {len(image_toolbar)}개")
            for elem in image_toolbar:
                print(f"   - {elem}")

            # 5. 이미지 더블클릭 시도
            print("\n5. 이미지 더블클릭...")
            await publisher.cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": image_element["coords"][0],
                "y": image_element["coords"][1],
                "button": "left",
                "clickCount": 2
            })
            await publisher.cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": image_element["coords"][0],
                "y": image_element["coords"][1],
                "button": "left",
                "clickCount": 2
            })
            await asyncio.sleep(1)

            await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_03_image_double_click.png")

            # 더블클릭 후 나타나는 요소 확인
            after_dblclick = await publisher._evaluate_js("""
                (() => {
                    const results = [];

                    // 모든 보이는 input 찾기
                    const inputs = document.querySelectorAll('input');
                    inputs.forEach(inp => {
                        const rect = inp.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 0) {
                            results.push({
                                type: 'input',
                                inputType: inp.type,
                                placeholder: inp.placeholder,
                                value: inp.value,
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                            });
                        }
                    });

                    // 팝업/모달
                    const modals = document.querySelectorAll('.se-popup, .se-layer, .se-dialog, [class*="modal"], [class*="dialog"]');
                    modals.forEach(modal => {
                        const rect = modal.getBoundingClientRect();
                        const style = getComputedStyle(modal);
                        if (rect.width > 100 && style.display !== 'none' && style.visibility !== 'hidden') {
                            results.push({
                                type: 'modal',
                                className: modal.className,
                                html: modal.innerHTML.substring(0, 500)
                            });
                        }
                    });

                    return results;
                })()
            """)
            print(f"   더블클릭 후 요소: {after_dblclick}")

            # 6. 이미지 우클릭 시도
            print("\n6. 이미지 우클릭...")
            await publisher._press_escape()
            await asyncio.sleep(0.3)
            await publisher._click_at(*image_element["coords"])
            await asyncio.sleep(0.3)

            await publisher.cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": image_element["coords"][0],
                "y": image_element["coords"][1],
                "button": "right",
                "clickCount": 1
            })
            await publisher.cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": image_element["coords"][0],
                "y": image_element["coords"][1],
                "button": "right",
                "clickCount": 1
            })
            await asyncio.sleep(1)

            await publisher.page.screenshot(path=f"{config.screenshot_dir}/{timestamp}_04_image_right_click.png")

            # 컨텍스트 메뉴 확인
            context_menu = await publisher._evaluate_js("""
                (() => {
                    const menus = document.querySelectorAll('[class*="context"], [class*="menu"], .se-popup-menu');
                    const results = [];
                    menus.forEach(menu => {
                        const rect = menu.getBoundingClientRect();
                        const style = getComputedStyle(menu);
                        if (rect.width > 50 && style.display !== 'none') {
                            const items = menu.querySelectorAll('button, li, a');
                            const itemTexts = [];
                            items.forEach(item => {
                                const text = item.innerText?.trim();
                                if (text) itemTexts.push(text);
                            });
                            results.push({
                                className: menu.className,
                                items: itemTexts
                            });
                        }
                    });
                    return results;
                })()
            """)
            print(f"   컨텍스트 메뉴: {context_menu}")

        print("\n" + "="*60)
        print("탐색 완료")
        print(f"스크린샷: {config.screenshot_dir}/{timestamp}_*.png")
        print("="*60)

        try:
            input("\nEnter 키를 눌러 종료...")
        except EOFError:
            await asyncio.sleep(10)

    except Exception as e:
        print(f"\n오류: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await publisher._close_browser()


if __name__ == "__main__":
    asyncio.run(test_image_link())
