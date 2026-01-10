#!/usr/bin/env python3
"""
OGLink 수정 테스트

oglink 버튼(링크 삽입)이 제대로 동작하는지 테스트합니다.
- "글감" 버튼: 검색 기능 (잘못된 버튼)
- "oglink" 버튼: URL 링크 삽입 (올바른 버튼)
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

os.environ["DEEPSEEK_API_KEY"] = "sk-323858b712234509a03982172fc11247"

from publisher.adaptive_publisher import AdaptivePublisher, PublishConfig


async def test_oglink_flow():
    """OGLink 링크 삽입 테스트"""

    print("\n" + "="*60)
    print("OGLink (링크 삽입) 테스트")
    print("="*60)

    config = PublishConfig(
        blog_id="tlswkehd_",
        cdp_url="http://localhost:9222",
        deepseek_api_key=os.environ.get("DEEPSEEK_API_KEY")
    )

    publisher = AdaptivePublisher(config)

    try:
        await publisher._init_browser()
        print("브라우저 초기화 완료")

        # 글쓰기 페이지 이동
        write_url = f"https://blog.naver.com/{config.blog_id}/postwrite"
        await publisher.page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)
        print(f"페이지 로드: {publisher.page.url}")

        # 임시저장 팝업 처리 (취소 버튼 클릭)
        async def dismiss_temp_save_popup():
            """임시저장 팝업 닫기"""
            popup_info = await publisher._evaluate_js("""
                (() => {
                    // "작성 중인 글" 팝업 찾기
                    const popups = document.querySelectorAll('.se-popup-alert, [class*="popup"], [class*="modal"]');
                    for (const popup of popups) {
                        const text = popup.innerText || '';
                        if (text.includes('작성 중인 글') || text.includes('임시저장')) {
                            // 취소 버튼 찾기
                            const buttons = popup.querySelectorAll('button');
                            for (const btn of buttons) {
                                const btnText = btn.innerText?.trim() || '';
                                if (btnText === '취소') {
                                    const rect = btn.getBoundingClientRect();
                                    return {
                                        found: true,
                                        coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                                    };
                                }
                            }
                        }
                    }
                    return { found: false };
                })()
            """)
            if popup_info and popup_info.get("found"):
                print(f"   임시저장 팝업 '취소' 클릭: {popup_info['coords']}")
                await publisher._click_at(*popup_info["coords"])
                await asyncio.sleep(0.5)
                return True
            return False

        # 팝업 여러번 처리 (중첩될 수 있음)
        for i in range(3):
            dismissed = await dismiss_temp_save_popup()
            if not dismissed:
                break
            print(f"   팝업 {i+1}번째 닫음")

        # 1. 버튼 위치 확인
        print("\n1. 툴바 버튼 확인:")
        dom = await publisher._get_dom_snapshot()
        toolbar = dom.get("toolbar", {})

        oglink_info = toolbar.get("oglink")
        material_info = toolbar.get("material")

        print(f"   oglink (링크): {oglink_info}")
        print(f"   material (글감): {material_info}")

        if not oglink_info or not oglink_info.get("found"):
            print("   oglink 버튼을 찾을 수 없음!")
            return

        # 2. 본문으로 이동
        print("\n2. 본문 영역으로 이동...")
        body_info = dom.get("editor", {}).get("body")
        if body_info and body_info.get("coords"):
            await publisher._click_at(*body_info["coords"])
            await asyncio.sleep(0.3)
            await publisher._type_text("링크 삽입 테스트:\n")

        # 3. oglink 버튼 클릭
        print("\n3. oglink 버튼 클릭...")
        oglink_coords = oglink_info.get("coords")
        print(f"   클릭 좌표: {oglink_coords}")
        await publisher._click_at(oglink_coords[0], oglink_coords[1])
        await asyncio.sleep(1)

        # 4. 모달 상태 확인
        print("\n4. 모달/팝업 확인...")
        modal_info = await publisher._evaluate_js("""
            (() => {
                const result = {
                    popups: [],
                    inputs: [],
                    buttons: []
                };

                // 팝업/모달 찾기
                const popups = document.querySelectorAll('.se-popup, [class*="layer"], [class*="modal"]');
                for (const popup of popups) {
                    const rect = popup.getBoundingClientRect();
                    const style = getComputedStyle(popup);
                    if (rect.width > 50 && style.display !== 'none' && style.visibility !== 'hidden') {
                        result.popups.push({
                            className: popup.className,
                            rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                        });

                        // 팝업 내 입력 필드
                        const inputs = popup.querySelectorAll('input, textarea');
                        for (const inp of inputs) {
                            const inputRect = inp.getBoundingClientRect();
                            if (inputRect.width > 50) {
                                result.inputs.push({
                                    type: inp.type || 'text',
                                    placeholder: inp.placeholder || '',
                                    coords: [inputRect.x + inputRect.width/2, inputRect.y + inputRect.height/2]
                                });
                            }
                        }

                        // 팝업 내 버튼
                        const buttons = popup.querySelectorAll('button');
                        for (const btn of buttons) {
                            const btnRect = btn.getBoundingClientRect();
                            const text = btn.innerText?.trim() || '';
                            if (btnRect.width > 30 && text) {
                                result.buttons.push({
                                    text: text,
                                    coords: [btnRect.x + btnRect.width/2, btnRect.y + btnRect.height/2]
                                });
                            }
                        }
                    }
                }

                return result;
            })()
        """)

        print(f"   팝업 수: {len(modal_info.get('popups', []))}")
        print(f"   입력 필드: {modal_info.get('inputs', [])}")
        print(f"   버튼: {modal_info.get('buttons', [])}")

        # 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_oglink_modal.png")
        print(f"   스크린샷 저장됨")

        if modal_info.get("inputs"):
            # 5. URL 입력
            print("\n5. URL 입력...")
            input_coords = modal_info["inputs"][0]["coords"]
            await publisher._click_at(input_coords[0], input_coords[1])
            await asyncio.sleep(0.2)
            await publisher._type_text("https://naver.com")
            await asyncio.sleep(2)  # OG 메타데이터 로딩

            # 6. 스크린샷 (OG 프리뷰 확인)
            await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_oglink_preview.png")
            print("   프리뷰 스크린샷 저장됨")

            # 7. 확인 버튼 클릭
            print("\n6. 확인 버튼 찾기...")
            confirm_info = await publisher._evaluate_js("""
                (() => {
                    const popup = document.querySelector('.se-popup, [class*="layer"], [class*="modal"]');
                    if (!popup) return { found: false };

                    const buttons = popup.querySelectorAll('button');
                    for (const btn of buttons) {
                        const text = btn.innerText?.trim() || '';
                        if (text === '확인' || text === '적용' || text === '등록' || text === '추가') {
                            const rect = btn.getBoundingClientRect();
                            return {
                                found: true,
                                text: text,
                                coords: [rect.x + rect.width/2, rect.y + rect.height/2]
                            };
                        }
                    }
                    return { found: false };
                })()
            """)

            if confirm_info and confirm_info.get("found"):
                print(f"   확인 버튼 발견: {confirm_info}")
                await publisher._click_at(*confirm_info["coords"])
                await asyncio.sleep(1)
                print("   확인 버튼 클릭 완료!")
            else:
                print("   확인 버튼 못 찾음 - Enter 키 시도")
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Enter",
                    "code": "Enter", "windowsVirtualKeyCode": 13
                })
                await publisher.cdp.send("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Enter",
                    "code": "Enter", "windowsVirtualKeyCode": 13
                })
                await asyncio.sleep(1)

            # 최종 스크린샷
            await publisher.page.screenshot(path=f"data/adaptive_test/{timestamp}_oglink_done.png")
            print("\n링크 삽입 완료!")

        else:
            print("\n입력 필드를 찾지 못함 - ESC로 닫기")
            await publisher._press_escape()

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
    asyncio.run(test_oglink_flow())
