#!/usr/bin/env python3
"""
CDP 방식 발행 테스트

Chrome을 디버깅 모드로 실행한 후 연결합니다.

사용법:
1. Chrome 실행: google-chrome --remote-debugging-port=9222
2. 네이버 로그인
3. 이 스크립트 실행: python scripts/publish_cdp.py --blog-id YOUR_ID --file FILE
"""

import asyncio
import argparse
import sys
import re
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from playwright.async_api import async_playwright


def parse_markdown_file(file_path: str) -> tuple[str, str]:
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

    for i in range(body_start, len(lines)):
        line = lines[i].strip()
        if line.startswith('>') or line == '':
            body_start = i + 1
        else:
            break

    body = '\n'.join(lines[body_start:]).strip()
    return title, body


def markdown_to_plain(markdown: str) -> str:
    """마크다운을 일반 텍스트로 변환"""
    text = markdown
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    text = re.sub(r'\[이미지:.*?\]', '', text)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)
    text = re.sub(r'^---+$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


async def publish_via_cdp(
    title: str,
    content: str,
    blog_id: str,
    cdp_url: str = "http://localhost:9222"
):
    """CDP를 통해 Chrome에 연결하여 발행"""

    print(f"\n🔌 CDP 연결 시도: {cdp_url}")

    async with async_playwright() as p:
        try:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            print("✅ Chrome 연결 성공")
        except Exception as e:
            print(f"❌ Chrome 연결 실패: {e}")
            print("\n💡 Chrome을 다음 명령으로 실행하세요:")
            print("   google-chrome --remote-debugging-port=9222")
            return None

        # 기존 컨텍스트 사용 또는 새로 생성
        contexts = browser.contexts
        if contexts:
            context = contexts[0]
            print(f"   기존 컨텍스트 사용 (페이지 수: {len(context.pages)})")
        else:
            context = await browser.new_context()
            print("   새 컨텍스트 생성")

        # 새 페이지 열기
        page = await context.new_page()

        # 글쓰기 페이지로 이동
        write_url = f"https://blog.naver.com/{blog_id}/postwrite"
        print(f"\n📝 글쓰기 페이지 이동: {write_url}")

        await page.goto(write_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)

        # 로그인 확인
        current_url = page.url
        if "nid.naver.com" in current_url or "login" in current_url.lower():
            print("❌ 로그인이 필요합니다. Chrome에서 네이버에 로그인해주세요.")
            await page.close()
            return None

        print("✅ 로그인 상태 확인됨")

        # 에디터 로드 대기
        try:
            await page.wait_for_selector(
                ".se-content, #content-area, .se-component-content",
                timeout=15000
            )
            print("✅ 에디터 로드됨")
        except:
            print("⚠️  에디터 로드 대기 시간 초과")

        await asyncio.sleep(1)

        # 제목 입력
        print(f"\n📌 제목 입력: {title[:30]}...")
        title_selectors = [
            ".se-title-text",
            "#post-title",
            "input[placeholder*='제목']",
            "[data-placeholder*='제목']"
        ]

        for selector in title_selectors:
            try:
                title_el = await page.query_selector(selector)
                if title_el:
                    await title_el.click()
                    await page.keyboard.type(title, delay=30)
                    print(f"   ✅ 제목 입력 완료 (selector: {selector})")
                    break
            except Exception as e:
                continue

        await asyncio.sleep(0.5)

        # 본문 영역으로 이동 (Tab 키)
        await page.keyboard.press("Tab")
        await asyncio.sleep(0.5)

        # 본문 입력
        plain_content = markdown_to_plain(content)
        print(f"\n📄 본문 입력 중... ({len(plain_content)} 자)")

        # 청크로 나눠서 입력
        chunk_size = 500
        chunks = [plain_content[i:i+chunk_size] for i in range(0, len(plain_content), chunk_size)]

        for i, chunk in enumerate(chunks):
            await page.keyboard.type(chunk, delay=5)
            await asyncio.sleep(0.1)
            if (i + 1) % 5 == 0:
                print(f"   {((i+1) * chunk_size / len(plain_content) * 100):.0f}% 완료...")

        print("   ✅ 본문 입력 완료")

        await asyncio.sleep(1)

        # 스크린샷 저장
        screenshot_path = project_root / "data" / "screenshots" / "before_publish.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(screenshot_path))
        print(f"\n📸 스크린샷 저장: {screenshot_path}")

        # 발행 버튼 클릭
        print("\n🚀 발행 버튼 클릭...")
        publish_selectors = [
            "button:has-text('발행')",
            ".se-publish-btn",
            "#publish-btn",
            "button:has-text('등록')"
        ]

        for selector in publish_selectors:
            try:
                btn = await page.query_selector(selector)
                if btn:
                    await btn.click()
                    print(f"   ✅ 발행 버튼 클릭 (selector: {selector})")
                    break
            except:
                continue

        # 확인 모달 처리
        await asyncio.sleep(1)
        try:
            confirm_btn = await page.query_selector("button:has-text('확인')")
            if confirm_btn:
                await confirm_btn.click()
                print("   ✅ 확인 버튼 클릭")
        except:
            pass

        # 발행 완료 대기
        await asyncio.sleep(3)

        try:
            await page.wait_for_url("**/PostView**", timeout=10000)
        except:
            pass

        final_url = page.url
        print(f"\n📍 최종 URL: {final_url}")

        if "PostView" in final_url or "logNo" in final_url:
            print("\n✅ 발행 성공!")
            return final_url
        else:
            print("\n⚠️  발행 완료 확인 필요")
            return final_url


async def main():
    parser = argparse.ArgumentParser(description='CDP 방식 네이버 블로그 발행')
    parser.add_argument('--blog-id', '-b', required=True, help='네이버 블로그 ID')
    parser.add_argument('--file', '-f', required=True, help='마크다운 파일 경로')
    parser.add_argument('--cdp-url', default='http://localhost:9222', help='Chrome CDP URL')

    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"❌ 파일을 찾을 수 없습니다: {args.file}")
        return

    title, content = parse_markdown_file(args.file)
    print(f"📄 파일 로드: {args.file}")
    print(f"   제목: {title[:50]}...")
    print(f"   본문: {len(content)} 자")

    result = await publish_via_cdp(
        title=title,
        content=content,
        blog_id=args.blog_id,
        cdp_url=args.cdp_url
    )

    print("\n" + "=" * 50)
    if result:
        print(f"🎉 발행 URL: {result}")
    else:
        print("❌ 발행 실패")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
