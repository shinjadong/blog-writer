#!/usr/bin/env python3
"""
CDP 기반 네이버 블로그 발행 v2

Browser-Use 방식 적용:
1. CDP를 통한 직접 요소 조작
2. 정확한 포커스 관리
3. JavaScript 평가를 통한 요소 탐색
"""

import asyncio
import json
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "data" / "publish_screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def get_cdp_session(page):
    """Playwright 페이지에서 CDP 세션 획득"""
    cdp = await page.context.new_cdp_session(page)
    return cdp


async def find_element_by_selector(cdp, selector: str):
    """CSS 셀렉터로 요소의 BackendNodeId 찾기"""
    # DOM 활성화
    await cdp.send("DOM.enable")

    # 문서 루트 가져오기
    doc = await cdp.send("DOM.getDocument")
    root_id = doc["root"]["nodeId"]

    # 셀렉터로 요소 찾기
    result = await cdp.send("DOM.querySelector", {
        "nodeId": root_id,
        "selector": selector
    })

    if result.get("nodeId", 0) == 0:
        return None

    # nodeId로 backendNodeId 가져오기
    node_info = await cdp.send("DOM.describeNode", {
        "nodeId": result["nodeId"]
    })

    return {
        "nodeId": result["nodeId"],
        "backendNodeId": node_info["node"]["backendNodeId"]
    }


async def click_element(cdp, backend_node_id: int):
    """BackendNodeId로 요소 클릭"""
    # 요소를 뷰포트로 스크롤
    try:
        await cdp.send("DOM.scrollIntoViewIfNeeded", {
            "backendNodeId": backend_node_id
        })
        await asyncio.sleep(0.1)
    except:
        pass

    # 요소 좌표 가져오기
    try:
        quads = await cdp.send("DOM.getContentQuads", {
            "backendNodeId": backend_node_id
        })

        if quads.get("quads") and len(quads["quads"]) > 0:
            quad = quads["quads"][0]
            # 중심점 계산
            center_x = sum(quad[i] for i in range(0, 8, 2)) / 4
            center_y = sum(quad[i] for i in range(1, 8, 2)) / 4

            # 마우스 클릭
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": center_x,
                "y": center_y
            })
            await asyncio.sleep(0.05)

            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": center_x,
                "y": center_y,
                "button": "left",
                "clickCount": 1
            })
            await asyncio.sleep(0.05)

            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": center_x,
                "y": center_y,
                "button": "left",
                "clickCount": 1
            })
            return True
    except Exception as e:
        print(f"   좌표 클릭 실패: {e}")

    # JavaScript 폴백
    try:
        result = await cdp.send("DOM.resolveNode", {
            "backendNodeId": backend_node_id
        })
        object_id = result["object"]["objectId"]

        await cdp.send("Runtime.callFunctionOn", {
            "functionDeclaration": "function() { this.click(); }",
            "objectId": object_id
        })
        return True
    except Exception as e:
        print(f"   JS 클릭 실패: {e}")
        return False


async def focus_element(cdp, backend_node_id: int):
    """요소에 포커스"""
    try:
        # 먼저 nodeId 획득
        result = await cdp.send("DOM.resolveNode", {
            "backendNodeId": backend_node_id
        })
        object_id = result["object"]["objectId"]

        # JavaScript로 focus 호출
        await cdp.send("Runtime.callFunctionOn", {
            "functionDeclaration": "function() { this.focus(); }",
            "objectId": object_id
        })
        return True
    except Exception as e:
        print(f"   포커스 실패: {e}")
        return False


async def type_text(cdp, text: str, delay_ms: int = 18):
    """CDP를 통해 텍스트 입력 (Browser-Use 방식)

    핵심: keyDown에는 text 없음, char에만 text 있음
    """

    for char in text:
        if char == '\n':
            # Enter 키
            await cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "key": "Enter",
                "code": "Enter",
                "windowsVirtualKeyCode": 13
            })
            await asyncio.sleep(0.001)
            await cdp.send("Input.dispatchKeyEvent", {
                "type": "char",
                "text": "\r",
                "key": "Enter"
            })
            await cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": "Enter",
                "code": "Enter",
                "windowsVirtualKeyCode": 13
            })
        else:
            # 일반 문자 - keyDown에는 text 없음!
            await cdp.send("Input.dispatchKeyEvent", {
                "type": "keyDown",
                "key": char
            })
            await asyncio.sleep(0.001)
            # char 이벤트에만 text
            await cdp.send("Input.dispatchKeyEvent", {
                "type": "char",
                "text": char,
                "key": char
            })
            await cdp.send("Input.dispatchKeyEvent", {
                "type": "keyUp",
                "key": char
            })

        await asyncio.sleep(delay_ms / 1000)


async def evaluate_js(cdp, expression: str):
    """JavaScript 평가"""
    result = await cdp.send("Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True
    })
    return result.get("result", {}).get("value")


async def capture_state(page, cdp, step_name: str):
    """현재 상태 캡처"""
    timestamp = datetime.now().strftime("%H%M%S")

    # 스크린샷
    screenshot_path = SCREENSHOT_DIR / f"{timestamp}_{step_name}.png"
    await page.screenshot(path=str(screenshot_path))

    # 에디터 상태 확인
    state = await evaluate_js(cdp, """
        (() => {
            const result = { title: '', body: '', focusedIn: 'unknown' };

            // 제목
            const titleEl = document.querySelector('.se-title-text');
            if (titleEl) result.title = titleEl.innerText || '';

            // 본문 (제목 외)
            const paragraphs = document.querySelectorAll('.se-text-paragraph');
            const titleArea = document.querySelector('.se-documentTitle');
            for (const p of paragraphs) {
                if (titleArea && titleArea.contains(p)) continue;
                result.body = p.innerText || '';
                break;
            }

            // 포커스 위치 (폰트 크기로 판단)
            const fontBtn = document.querySelector('[data-name="fontSize"]');
            if (fontBtn) {
                const size = fontBtn.innerText?.trim();
                result.focusedIn = size === '32' ? 'title' : 'body';
            }

            return result;
        })()
    """)

    print(f"\n📸 {step_name}")
    print(f"   📌 제목: {state.get('title', '')[:40] if state else '?'}...")
    print(f"   📄 본문: {state.get('body', '')[:40] if state else '?'}...")
    print(f"   🎯 포커스: {state.get('focusedIn', '?') if state else '?'}")
    print(f"   📁 {screenshot_path.name}")

    return state


async def find_body_element(cdp):
    """본문 영역 요소 찾기 (제목 제외)"""
    result = await evaluate_js(cdp, """
        (() => {
            // 모든 se-text-paragraph 찾기
            const paragraphs = document.querySelectorAll('.se-text-paragraph');
            const titleArea = document.querySelector('.se-documentTitle');

            for (const p of paragraphs) {
                // 제목 영역 내부가 아닌 것
                if (titleArea && titleArea.contains(p)) continue;

                // 본문 영역 발견
                const rect = p.getBoundingClientRect();
                return {
                    found: true,
                    selector: '.se-component.se-text .se-text-paragraph',
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                };
            }

            return { found: false };
        })()
    """)
    return result


async def publish_blog_post(
    title: str,
    content: str,
    blog_id: str,
    cdp_url: str = "http://localhost:9222"
):
    """CDP 기반 블로그 발행"""

    from playwright.async_api import async_playwright

    print("\n" + "="*60)
    print("🚀 CDP 기반 네이버 블로그 발행 v2")
    print("="*60)
    print(f"Blog ID: {blog_id}")
    print(f"제목: {title[:40]}...")
    print(f"본문: {len(content)}자")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            print("\n✅ Chrome CDP 연결 성공")
        except Exception as e:
            print(f"\n❌ Chrome CDP 연결 실패: {e}")
            return None

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()
        page = await context.new_page()

        # CDP 세션 획득
        cdp = await get_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("Runtime.enable")

        # ========== 글쓰기 페이지 ==========
        write_url = f"https://blog.naver.com/{blog_id}/postwrite"
        print(f"\n📍 글쓰기 페이지: {write_url}")
        await page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 팝업 처리
        try:
            popup_btn = await find_element_by_selector(cdp, '.se-popup-alert-confirm button')
            if popup_btn:
                # '취소' 버튼 클릭 (새로 시작)
                cancel_btn = await find_element_by_selector(cdp, '.se-popup-alert-confirm button:first-child')
                if cancel_btn:
                    await click_element(cdp, cancel_btn["backendNodeId"])
                    print("✅ 임시저장 팝업 닫기")
                    await asyncio.sleep(1)
        except:
            pass

        await capture_state(page, cdp, "01_initial")

        # ========== STEP 1: 제목 입력 ==========
        print("\n\n📝 STEP 1: 제목 입력")

        # 제목 영역 찾기 및 클릭
        title_el = await find_element_by_selector(cdp, '.se-documentTitle .se-text-paragraph')
        if not title_el:
            title_el = await find_element_by_selector(cdp, '.se-title-text')

        if title_el:
            await click_element(cdp, title_el["backendNodeId"])
            await asyncio.sleep(0.3)
            await focus_element(cdp, title_el["backendNodeId"])
            await asyncio.sleep(0.3)

            # 제목 입력
            await type_text(cdp, title, delay_ms=30)
            print(f"   ✅ 제목 입력 완료: {title[:30]}...")
        else:
            print("   ❌ 제목 영역을 찾을 수 없습니다")
            return None

        await asyncio.sleep(0.5)
        state1 = await capture_state(page, cdp, "02_title_typed")

        # 제목 검증
        if title not in (state1 or {}).get('title', ''):
            print("   ⚠️ 제목 입력 확인 필요")

        # ========== STEP 2: 본문 영역으로 이동 ==========
        print("\n\n🎯 STEP 2: 본문 영역으로 이동")

        # 본문 요소 찾기
        body_info = await find_body_element(cdp)

        if body_info and body_info.get('found'):
            rect = body_info.get('rect', {})
            x = rect.get('x', 700) + 50
            y = rect.get('y', 400) + 20

            print(f"   본문 영역 클릭: ({x:.0f}, {y:.0f})")

            # 직접 좌표 클릭
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseMoved",
                "x": x,
                "y": y
            })
            await asyncio.sleep(0.05)
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1
            })
            await asyncio.sleep(0.05)
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": x,
                "y": y,
                "button": "left",
                "clickCount": 1
            })
        else:
            # 본문 요소를 직접 찾아 클릭
            body_el = await find_element_by_selector(cdp, '.se-component.se-text .se-text-paragraph')
            if body_el:
                await click_element(cdp, body_el["backendNodeId"])
            else:
                print("   ⚠️ 본문 요소 없음, 고정 좌표 클릭")
                await cdp.send("Input.dispatchMouseEvent", {
                    "type": "mousePressed",
                    "x": 700, "y": 400,
                    "button": "left", "clickCount": 1
                })
                await cdp.send("Input.dispatchMouseEvent", {
                    "type": "mouseReleased",
                    "x": 700, "y": 400,
                    "button": "left", "clickCount": 1
                })

        await asyncio.sleep(1)  # 포커스 전환 대기

        state2 = await capture_state(page, cdp, "03_body_focused")

        # 포커스 확인
        if (state2 or {}).get('focusedIn') == 'title':
            print("   ⚠️ 아직 제목에 포커스! 재시도...")
            # 더 아래쪽 클릭
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": 700, "y": 450,
                "button": "left", "clickCount": 1
            })
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": 700, "y": 450,
                "button": "left", "clickCount": 1
            })
            await asyncio.sleep(0.5)

        # ========== STEP 3: 본문 입력 ==========
        print("\n\n📝 STEP 3: 본문 입력")

        # 본문을 문단별로 입력
        paragraphs = content.split('\n\n')
        for i, para in enumerate(paragraphs):
            if not para.strip():
                continue

            await type_text(cdp, para.strip(), delay_ms=10)

            if i < len(paragraphs) - 1:
                # 문단 사이 Enter 두 번
                await type_text(cdp, '\n\n', delay_ms=50)

            print(f"   문단 {i+1}/{len(paragraphs)} 입력 완료")

        await asyncio.sleep(0.5)
        state3 = await capture_state(page, cdp, "04_body_typed")

        # 검증
        body_text = (state3 or {}).get('body', '')
        title_text = (state3 or {}).get('title', '')

        if content[:20] in title_text:
            print("   ❌ 오류: 본문이 제목에 입력됨!")
        elif content[:20] in body_text or body_text:
            print("   ✅ 본문 입력 성공!")
        else:
            print("   ⚠️ 본문 입력 확인 필요")

        # ========== STEP 4: 발행 ==========
        print("\n\n🚀 STEP 4: 발행")

        # 발행 버튼 찾기 (JavaScript로)
        publish_btn = await evaluate_js(cdp, """
            (() => {
                const btns = document.querySelectorAll('button');
                for (const btn of btns) {
                    if (btn.innerText?.trim() === '발행') {
                        const rect = btn.getBoundingClientRect();
                        return { x: rect.x + rect.width/2, y: rect.y + rect.height/2 };
                    }
                }
                return null;
            })()
        """)

        if publish_btn:
            print(f"   발행 버튼 클릭: ({publish_btn['x']:.0f}, {publish_btn['y']:.0f})")
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": publish_btn['x'], "y": publish_btn['y'],
                "button": "left", "clickCount": 1
            })
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": publish_btn['x'], "y": publish_btn['y'],
                "button": "left", "clickCount": 1
            })
            print("   ✅ 발행 버튼 클릭")
        else:
            print("   ❌ 발행 버튼을 찾을 수 없습니다")

        await asyncio.sleep(2)
        await capture_state(page, cdp, "05_publish_clicked")

        # 발행 설정 패널의 최종 발행 버튼 클릭
        print("\n   발행 설정 패널에서 최종 발행 버튼 찾기...")

        final_publish_btn = await evaluate_js(cdp, """
            (() => {
                // 발행 설정 패널 내의 발행 버튼 (녹색 버튼)
                // 패널 하단에 있음 - y좌표가 300 이상인 발행 버튼
                const btns = document.querySelectorAll('button');
                let candidates = [];

                for (const btn of btns) {
                    const text = btn.innerText?.trim();
                    if (text === '발행' || text.includes('발행')) {
                        const rect = btn.getBoundingClientRect();
                        candidates.push({
                            x: rect.x + rect.width/2,
                            y: rect.y + rect.height/2,
                            text: text,
                            width: rect.width,
                            height: rect.height
                        });
                    }
                }

                // y좌표가 가장 큰 (가장 아래에 있는) 발행 버튼 선택
                // 헤더 버튼은 y < 50이므로 제외됨
                if (candidates.length > 0) {
                    candidates.sort((a, b) => b.y - a.y);
                    // y > 300인 버튼만 (패널 내 버튼)
                    const panelBtn = candidates.find(b => b.y > 300);
                    if (panelBtn) return panelBtn;
                }

                return null;
            })()
        """)

        if final_publish_btn:
            print(f"   최종 발행 버튼 발견: '{final_publish_btn.get('text')}' @ ({final_publish_btn['x']:.0f}, {final_publish_btn['y']:.0f})")
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mousePressed",
                "x": final_publish_btn['x'], "y": final_publish_btn['y'],
                "button": "left", "clickCount": 1
            })
            await asyncio.sleep(0.1)
            await cdp.send("Input.dispatchMouseEvent", {
                "type": "mouseReleased",
                "x": final_publish_btn['x'], "y": final_publish_btn['y'],
                "button": "left", "clickCount": 1
            })
            print("   ✅ 최종 발행 버튼 클릭!")
        else:
            print("   ⚠️ 최종 발행 버튼을 찾을 수 없습니다")

        await asyncio.sleep(5)  # 발행 완료 대기

        # 최종 URL 확인
        final_url = page.url
        await capture_state(page, cdp, "06_final")

        print(f"\n📍 최종 URL: {final_url}")

        if "PostView" in final_url or "logNo" in final_url:
            print("\n✅ 발행 성공!")
            return final_url
        else:
            print("\n⚠️ 발행 완료 확인 필요")
            print("   페이지를 확인하세요...")

            # 페이지 열어둠
            try:
                input("\nEnter 키로 종료...")
            except EOFError:
                pass

        await page.close()
        return final_url


def parse_markdown(file_path: str) -> tuple[str, str]:
    """마크다운 파일에서 제목과 본문 추출"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    title = ""
    body_start = 0

    for i, line in enumerate(lines):
        if line.startswith('# ') and not line.startswith('## '):
            title = line[2:].strip()
            body_start = i + 1
            break

    # 인용문 건너뛰기
    for i in range(body_start, len(lines)):
        line = lines[i].strip()
        if line.startswith('>') or line == '':
            body_start = i + 1
        else:
            break

    body = '\n'.join(lines[body_start:]).strip()

    # 마크다운 정리
    body = re.sub(r'^#{1,6}\s+', '', body, flags=re.MULTILINE)
    body = re.sub(r'\*\*(.+?)\*\*', r'\1', body)
    body = re.sub(r'\*(.+?)\*', r'\1', body)
    body = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', body)
    body = re.sub(r'!\[.*?\]\(.*?\)', '', body)
    body = re.sub(r'```[\s\S]*?```', '', body)
    body = re.sub(r'`(.+?)`', r'\1', body)
    body = re.sub(r'\n{3,}', '\n\n', body)

    return title, body.strip()


async def main():
    import argparse
    parser = argparse.ArgumentParser(description='CDP 기반 네이버 블로그 발행 v2')
    parser.add_argument('--blog-id', '-b', default='tlswkehd_', help='블로그 ID')
    parser.add_argument('--file', '-f', help='마크다운 파일 경로')
    parser.add_argument('--title', '-t', help='제목 (파일 없을 때)')
    parser.add_argument('--content', '-c', help='내용 (파일 없을 때)')
    parser.add_argument('--cdp-url', default='http://localhost:9222')

    args = parser.parse_args()

    if args.file:
        title, content = parse_markdown(args.file)
    elif args.title and args.content:
        title = args.title
        content = args.content
    else:
        # 테스트용 기본값
        title = "CCTV 설치 테스트 포스트"
        content = """이것은 테스트 본문입니다.

CCTV 설치를 고민하시는 분들께 도움이 되었으면 합니다.

첫째, 설치 위치를 잘 선정해야 합니다.
둘째, 화질과 저장 용량을 고려해야 합니다.
셋째, 야간 촬영 기능이 중요합니다.

감사합니다."""

    result = await publish_blog_post(
        title=title,
        content=content,
        blog_id=args.blog_id,
        cdp_url=args.cdp_url
    )

    print("\n" + "="*60)
    if result:
        print(f"🎉 결과: {result}")
    else:
        print("❌ 발행 실패")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
