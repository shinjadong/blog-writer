#!/usr/bin/env python3
"""
네이버 블로그 발행 테스트 스크립트

사용법:
    # 생성된 원고 파일로 테스트
    python scripts/publish_article.py --file data/generated/test.md --blog-id YOUR_BLOG_ID

    # 직접 제목/내용 입력
    python scripts/publish_article.py --title "테스트 제목" --content "테스트 내용" --blog-id YOUR_BLOG_ID

    # headless=False로 브라우저 확인하며 테스트
    python scripts/publish_article.py --file data/generated/test.md --blog-id YOUR_BLOG_ID --visible
"""

import asyncio
import argparse
import sys
import os
from pathlib import Path

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.publisher.naver_publisher import NaverPublisher, PublishConfig, PublishResult


def get_default_chrome_user_data() -> str:
    """기본 Chrome 유저 데이터 경로 반환"""
    home = Path.home()

    # Linux
    linux_path = home / ".config" / "google-chrome"
    if linux_path.exists():
        return str(linux_path)

    # macOS
    mac_path = home / "Library" / "Application Support" / "Google" / "Chrome"
    if mac_path.exists():
        return str(mac_path)

    # Windows
    win_path = home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    if win_path.exists():
        return str(win_path)

    return str(linux_path)  # 기본값


def parse_markdown_file(file_path: str) -> tuple[str, str]:
    """마크다운 파일에서 제목과 본문 추출"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    lines = content.split('\n')
    title = ""
    body_start = 0

    # 첫 번째 # 제목 찾기
    for i, line in enumerate(lines):
        if line.startswith('# ') and not line.startswith('## '):
            title = line[2:].strip()
            body_start = i + 1
            break

    # 메타 정보(> 키워드, > 생성일) 건너뛰기
    for i in range(body_start, len(lines)):
        line = lines[i].strip()
        if line.startswith('>') or line == '':
            body_start = i + 1
        else:
            break

    body = '\n'.join(lines[body_start:]).strip()

    return title, body


async def test_connection(config: PublishConfig) -> bool:
    """연결 테스트"""
    print("\n🔍 네이버 블로그 연결 테스트...")
    publisher = NaverPublisher()

    result = await publisher.test_connection(config)

    if result:
        print("✅ 연결 성공! 로그인 상태가 확인되었습니다.")
    else:
        print("❌ 연결 실패. 로그인이 필요합니다.")
        print("   Chrome에서 네이버에 로그인한 후 다시 시도하세요.")

    return result


async def publish_article(
    title: str,
    content: str,
    config: PublishConfig
) -> PublishResult:
    """원고 발행"""
    print(f"\n📝 발행 시작...")
    print(f"   제목: {title[:50]}...")
    print(f"   본문 길이: {len(content)} 자")
    print(f"   블로그 ID: {config.blog_id}")
    print(f"   headless: {config.headless}")

    publisher = NaverPublisher()
    result = await publisher.publish(title, content, config)

    return result


async def main():
    parser = argparse.ArgumentParser(description='네이버 블로그 자동 발행 테스트')

    # 입력 옵션
    parser.add_argument('--file', '-f', help='마크다운 파일 경로')
    parser.add_argument('--title', '-t', help='블로그 제목')
    parser.add_argument('--content', '-c', help='블로그 내용')

    # 블로그 설정
    parser.add_argument('--blog-id', '-b', required=True, help='네이버 블로그 ID')
    parser.add_argument('--category', help='카테고리 이름')
    parser.add_argument('--tags', nargs='+', help='태그 목록')

    # 브라우저 설정
    parser.add_argument('--chrome-user-data', help='Chrome 유저 데이터 경로')
    parser.add_argument('--visible', action='store_true', help='브라우저 창 표시 (headless=False)')
    parser.add_argument('--slow-mo', type=int, default=100, help='액션 간 딜레이 (ms)')

    # 테스트 모드
    parser.add_argument('--test-only', action='store_true', help='연결 테스트만 실행')

    args = parser.parse_args()

    # 제목/내용 결정
    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ 파일을 찾을 수 없습니다: {args.file}")
            return
        title, content = parse_markdown_file(args.file)
        print(f"📄 파일 로드: {args.file}")
    elif args.title and args.content:
        title = args.title
        content = args.content
    elif not args.test_only:
        print("❌ --file 또는 --title/--content를 지정하세요.")
        return
    else:
        title, content = "", ""

    # Chrome 유저 데이터 경로
    chrome_user_data = args.chrome_user_data or get_default_chrome_user_data()

    if not os.path.exists(chrome_user_data):
        print(f"⚠️  Chrome 유저 데이터 경로를 찾을 수 없습니다: {chrome_user_data}")
        print("   --chrome-user-data 옵션으로 경로를 지정하세요.")
        return

    print(f"🔧 Chrome 유저 데이터: {chrome_user_data}")

    # 설정 생성
    config = PublishConfig(
        blog_id=args.blog_id,
        category=args.category or "",
        tags=args.tags or [],
        chrome_user_data_dir=chrome_user_data,
        headless=not args.visible,
        slow_mo=args.slow_mo,
        screenshot_on_error=True
    )

    # 연결 테스트만
    if args.test_only:
        await test_connection(config)
        return

    # 발행 실행
    result = await publish_article(title, content, config)

    # 결과 출력
    print("\n" + "=" * 50)
    if result.success:
        print("✅ 발행 성공!")
        print(f"   URL: {result.blog_url}")
        print(f"   Post ID: {result.post_id}")
        print(f"   발행 시간: {result.published_at}")
    else:
        print("❌ 발행 실패")
        print(f"   에러: {result.error_message}")
        if result.screenshots:
            print(f"   스크린샷: {result.screenshots}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
