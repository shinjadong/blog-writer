#!/usr/bin/env python3
"""
네이버 스마트에디터 도구모음 탐색

에디터의 각종 서식 도구들의 DOM 구조를 파악합니다:
- 인용구 (Quote)
- 구분선 (Divider)
- 링크
- 폰트 설정
- 글감 등
"""

import asyncio
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
SCREENSHOT_DIR = PROJECT_ROOT / "data" / "editor_explore"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


async def get_cdp_session(page):
    """Playwright 페이지에서 CDP 세션 획득"""
    cdp = await page.context.new_cdp_session(page)
    return cdp


async def evaluate_js(cdp, expression: str):
    """JavaScript 평가"""
    result = await cdp.send("Runtime.evaluate", {
        "expression": expression,
        "returnByValue": True
    })
    return result.get("result", {}).get("value")


async def explore_toolbar(cdp):
    """도구모음 버튼들 탐색"""

    toolbar_info = await evaluate_js(cdp, """
        (() => {
            const result = {
                toolbarButtons: [],
                componentButtons: [],
                formatButtons: []
            };

            // 1. 메인 툴바 버튼들 (상단)
            const toolButtons = document.querySelectorAll('.se-toolbar button');
            for (const btn of toolButtons) {
                const name = btn.getAttribute('data-name') ||
                             btn.getAttribute('aria-label') ||
                             btn.className;
                const rect = btn.getBoundingClientRect();

                if (rect.width > 0 && rect.height > 0) {
                    result.toolbarButtons.push({
                        name: name,
                        text: btn.innerText?.trim() || '',
                        class: btn.className,
                        dataName: btn.getAttribute('data-name'),
                        ariaLabel: btn.getAttribute('aria-label'),
                        x: rect.x + rect.width/2,
                        y: rect.y + rect.height/2,
                        rect: { x: rect.x, y: rect.y, w: rect.width, h: rect.height }
                    });
                }
            }

            // 2. 컴포넌트 패널 버튼들 (글감, 구분선 등)
            const componentBtns = document.querySelectorAll('[class*="component-panel"] button, .se-component-picker button');
            for (const btn of componentBtns) {
                const rect = btn.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0) {
                    result.componentButtons.push({
                        name: btn.getAttribute('data-name') || btn.innerText?.trim(),
                        text: btn.innerText?.trim() || '',
                        class: btn.className,
                        dataName: btn.getAttribute('data-name'),
                        x: rect.x + rect.width/2,
                        y: rect.y + rect.height/2
                    });
                }
            }

            // 3. 서식 관련 버튼들 검색
            const allButtons = document.querySelectorAll('button');
            for (const btn of allButtons) {
                const dataName = btn.getAttribute('data-name');
                const ariaLabel = btn.getAttribute('aria-label');
                const text = btn.innerText?.trim();

                // 특정 서식 도구 찾기
                const keywords = ['quote', 'link', 'divider', 'line', 'font',
                                  '인용', '링크', '구분', '글감', 'material',
                                  'bold', 'italic', 'underline', 'color'];

                const matched = keywords.some(kw =>
                    (dataName && dataName.toLowerCase().includes(kw)) ||
                    (ariaLabel && ariaLabel.toLowerCase().includes(kw)) ||
                    (text && text.toLowerCase().includes(kw))
                );

                if (matched) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0) {
                        result.formatButtons.push({
                            name: dataName || ariaLabel || text,
                            text: text,
                            dataName: dataName,
                            ariaLabel: ariaLabel,
                            class: btn.className,
                            x: rect.x + rect.width/2,
                            y: rect.y + rect.height/2
                        });
                    }
                }
            }

            return result;
        })()
    """)

    return toolbar_info


async def explore_component_panel(cdp):
    """컴포넌트 패널 (+ 버튼 클릭 시 나타나는 패널) 탐색"""

    panel_info = await evaluate_js(cdp, """
        (() => {
            const result = {
                plusButton: null,
                panelItems: [],
                allDataNames: []
            };

            // + 버튼 찾기
            const plusBtns = document.querySelectorAll('[data-name="oglink"], .se-component-pick-button, button[class*="add"]');
            for (const btn of plusBtns) {
                const rect = btn.getBoundingClientRect();
                if (rect.width > 0) {
                    result.plusButton = {
                        class: btn.className,
                        dataName: btn.getAttribute('data-name'),
                        x: rect.x + rect.width/2,
                        y: rect.y + rect.height/2
                    };
                    break;
                }
            }

            // 모든 data-name 속성 수집
            const allWithDataName = document.querySelectorAll('[data-name]');
            for (const el of allWithDataName) {
                const name = el.getAttribute('data-name');
                if (name && !result.allDataNames.includes(name)) {
                    result.allDataNames.push(name);
                }
            }

            // 컴포넌트 관련 요소들
            const componentEls = document.querySelectorAll('[class*="component"]');
            const uniqueClasses = new Set();
            for (const el of componentEls) {
                uniqueClasses.add(el.className);
            }
            result.componentClasses = Array.from(uniqueClasses).slice(0, 30);

            return result;
        })()
    """)

    return panel_info


async def find_format_tools(cdp):
    """특정 서식 도구들의 위치 찾기"""

    tools = await evaluate_js(cdp, """
        (() => {
            const findButton = (dataNames) => {
                for (const name of dataNames) {
                    const btn = document.querySelector(`[data-name="${name}"]`);
                    if (btn) {
                        const rect = btn.getBoundingClientRect();
                        if (rect.width > 0) {
                            return {
                                found: true,
                                dataName: name,
                                x: rect.x + rect.width/2,
                                y: rect.y + rect.height/2,
                                class: btn.className
                            };
                        }
                    }
                }
                return { found: false };
            };

            return {
                // 볼드
                bold: findButton(['bold', 'fontWeight']),
                // 이탤릭
                italic: findButton(['italic', 'fontStyle']),
                // 밑줄
                underline: findButton(['underline', 'textDecoration']),
                // 취소선
                strikethrough: findButton(['strikethrough', 'lineThrough']),
                // 폰트 크기
                fontSize: findButton(['fontSize', 'fontsize']),
                // 폰트 색상
                fontColor: findButton(['fontColor', 'foreColor', 'color']),
                // 정렬
                align: findButton(['align', 'textAlign', 'justifyLeft']),
                // 인용구
                quote: findButton(['quote', 'quotation', 'blockquote']),
                // 구분선
                line: findButton(['line', 'horizontalLine', 'divider', 'hr']),
                // 링크
                link: findButton(['link', 'hyperlink', 'url']),
                // 글감
                material: findButton(['material', 'snippet', 'oglink']),
                // 이미지
                image: findButton(['image', 'photo', 'img']),
                // 리스트
                list: findButton(['bulletList', 'numberedList', 'list'])
            };
        })()
    """)

    return tools


async def main():
    from playwright.async_api import async_playwright

    print("\n" + "="*60)
    print("🔍 네이버 스마트에디터 도구모음 탐색")
    print("="*60)

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            print("\n✅ Chrome CDP 연결 성공")
        except Exception as e:
            print(f"\n❌ Chrome CDP 연결 실패: {e}")
            print("   Chrome을 --remote-debugging-port=9222로 실행하세요")
            return

        contexts = browser.contexts
        context = contexts[0] if contexts else await browser.new_context()

        # 기존 페이지 찾기
        pages = context.pages
        page = None
        for p in pages:
            if "blog.naver.com" in p.url and "postwrite" in p.url:
                page = p
                break

        if not page:
            print("\n⚠️ 에디터 페이지를 찾을 수 없습니다")
            print("   네이버 블로그 글쓰기 페이지를 열어주세요")
            return

        print(f"\n📍 페이지: {page.url}")

        # CDP 세션
        cdp = await get_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("Runtime.enable")

        # 스크린샷
        timestamp = datetime.now().strftime("%H%M%S")
        await page.screenshot(path=str(SCREENSHOT_DIR / f"{timestamp}_editor.png"))
        print(f"📸 스크린샷 저장: {timestamp}_editor.png")

        # 1. 도구모음 탐색
        print("\n\n" + "="*50)
        print("📋 1. 도구모음 버튼들")
        print("="*50)

        toolbar = await explore_toolbar(cdp)

        if toolbar:
            print(f"\n🔧 툴바 버튼 ({len(toolbar.get('toolbarButtons', []))}개):")
            for btn in toolbar.get('toolbarButtons', [])[:20]:
                name = btn.get('dataName') or btn.get('ariaLabel') or btn.get('name', '?')
                print(f"   - {name} @ ({btn['x']:.0f}, {btn['y']:.0f})")

            print(f"\n📦 컴포넌트 버튼 ({len(toolbar.get('componentButtons', []))}개):")
            for btn in toolbar.get('componentButtons', []):
                print(f"   - {btn.get('name', '?')}: {btn.get('text', '')}")

            print(f"\n✨ 서식 관련 버튼 ({len(toolbar.get('formatButtons', []))}개):")
            for btn in toolbar.get('formatButtons', []):
                print(f"   - {btn.get('name', '?')} @ ({btn.get('x', 0):.0f}, {btn.get('y', 0):.0f})")

        # 2. 컴포넌트 패널 탐색
        print("\n\n" + "="*50)
        print("📋 2. 컴포넌트 패널 & data-name 목록")
        print("="*50)

        panel = await explore_component_panel(cdp)

        if panel:
            print(f"\n➕ Plus 버튼: {panel.get('plusButton')}")

            print(f"\n📝 모든 data-name 속성 ({len(panel.get('allDataNames', []))}개):")
            for name in sorted(panel.get('allDataNames', [])):
                print(f"   - {name}")

            print(f"\n🎨 컴포넌트 클래스들:")
            for cls in panel.get('componentClasses', [])[:15]:
                print(f"   - {cls[:80]}...")

        # 3. 특정 서식 도구 찾기
        print("\n\n" + "="*50)
        print("📋 3. 서식 도구 위치")
        print("="*50)

        tools = await find_format_tools(cdp)

        if tools:
            for tool_name, info in tools.items():
                if info.get('found'):
                    print(f"   ✅ {tool_name}: {info.get('dataName')} @ ({info.get('x', 0):.0f}, {info.get('y', 0):.0f})")
                else:
                    print(f"   ❌ {tool_name}: 찾을 수 없음")

        # 4. 추가 분석: 인용구, 구분선 관련 요소 상세 검색
        print("\n\n" + "="*50)
        print("📋 4. 인용구/구분선/링크 상세 검색")
        print("="*50)

        detailed = await evaluate_js(cdp, """
            (() => {
                const result = {};

                // 모든 버튼의 data-name 수집
                const buttons = document.querySelectorAll('button[data-name]');
                result.buttonDataNames = [];
                for (const btn of buttons) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0) {
                        result.buttonDataNames.push({
                            dataName: btn.getAttribute('data-name'),
                            ariaLabel: btn.getAttribute('aria-label'),
                            title: btn.getAttribute('title'),
                            x: rect.x + rect.width/2,
                            y: rect.y + rect.height/2
                        });
                    }
                }

                // 컴포넌트 패널 (왼쪽 + 버튼)
                const componentPickButtons = document.querySelectorAll('.se-component-pick-list button');
                result.componentPickList = [];
                for (const btn of componentPickButtons) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0) {
                        result.componentPickList.push({
                            dataName: btn.getAttribute('data-name'),
                            text: btn.innerText?.trim(),
                            x: rect.x + rect.width/2,
                            y: rect.y + rect.height/2
                        });
                    }
                }

                // 드롭다운/팝업 메뉴들
                const menus = document.querySelectorAll('[class*="layer"], [class*="popup"], [class*="dropdown"]');
                result.menuClasses = [];
                for (const menu of menus) {
                    if (!result.menuClasses.includes(menu.className)) {
                        result.menuClasses.push(menu.className);
                    }
                }

                return result;
            })()
        """)

        if detailed:
            print(f"\n🔘 버튼 data-name 목록 ({len(detailed.get('buttonDataNames', []))}개):")
            for btn in detailed.get('buttonDataNames', []):
                print(f"   - {btn['dataName']:<20} | {btn.get('ariaLabel', ''):<20} @ ({btn['x']:.0f}, {btn['y']:.0f})")

            print(f"\n📦 컴포넌트 선택 목록 ({len(detailed.get('componentPickList', []))}개):")
            for item in detailed.get('componentPickList', []):
                print(f"   - {item.get('dataName', '?')}: {item.get('text', '')}")

        print("\n\n✅ 탐색 완료!")
        print(f"📁 스크린샷 위치: {SCREENSHOT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
