#!/usr/bin/env python3
"""
전체 파이프라인 테스트 스크립트

키워드 → 원고 생성 → 네이버 발행 전체 플로우 테스트

사용법:
    # 키워드로 원고 생성 후 발행
    python scripts/test_pipeline.py --keyword "가게CCTV추천" --blog-id YOUR_BLOG_ID

    # 브라우저 보면서 테스트
    python scripts/test_pipeline.py --keyword "가게CCTV추천" --blog-id YOUR_BLOG_ID --visible

    # 생성만 (발행 안 함)
    python scripts/test_pipeline.py --keyword "가게CCTV추천" --generate-only
"""

import asyncio
import argparse
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings
from src.shared.models import ArticleConfig, ArticleTemplate, ContentTone
from src.content.generator import ContentGenerator
from src.publisher.naver_publisher import NaverPublisher, PublishConfig
from src.traffic.trigger import TrafficTrigger, TrafficTriggerConfig


def get_default_chrome_user_data() -> str:
    """기본 Chrome 유저 데이터 경로 반환"""
    home = Path.home()
    linux_path = home / ".config" / "google-chrome"
    if linux_path.exists():
        return str(linux_path)
    mac_path = home / "Library" / "Application Support" / "Google" / "Chrome"
    if mac_path.exists():
        return str(mac_path)
    win_path = home / "AppData" / "Local" / "Google" / "Chrome" / "User Data"
    if win_path.exists():
        return str(win_path)
    return str(linux_path)


async def run_pipeline(
    keyword: str,
    blog_id: str = None,
    generate_only: bool = False,
    visible: bool = False,
    chrome_user_data: str = None,
    campaign_id: str = None,
    traffic_api_url: str = "http://localhost:8000"
):
    """전체 파이프라인 실행"""
    settings = get_settings()

    print("\n" + "=" * 60)
    print("🚀 Blog Writer Pipeline")
    print("=" * 60)
    print(f"키워드: {keyword}")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ===== STEP 1: 원고 생성 =====
    print("\n📝 STEP 1: 원고 생성 중...")

    generator = ContentGenerator(
        deepseek_api_key=settings.deepseek_api_key,
        model=settings.deepseek_model
    )

    config = ArticleConfig(
        keyword=keyword,
        template=ArticleTemplate.PERSONAL_STORY,
        tone=ContentTone.EMOTIONAL,
        target_length=2500,
        target_audience="소상공인"
    )

    article = await generator.generate(keyword=keyword, config=config)

    print(f"\n✅ 원고 생성 완료!")
    print(f"   제목: {article.title}")
    print(f"   길이: {article.word_count} 자")
    print(f"   품질 점수: {article.quality_score:.2f}")
    print(f"   SEO 점수: {article.seo_score:.2f}")

    # 파일 저장
    output_dir = project_root / "data" / "generated"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_keyword = keyword.replace(" ", "_")[:20]
    output_file = output_dir / f"{safe_keyword}_{timestamp}.md"

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# {article.title}\n\n")
        f.write(f"> 키워드: {article.keyword}\n")
        f.write(f"> 생성일: {article.created_at}\n\n")
        f.write(article.content)

    print(f"   저장됨: {output_file}")

    if generate_only:
        print("\n✅ 파이프라인 완료 (생성만)")
        return article, None

    # ===== STEP 2: 네이버 발행 =====
    if not blog_id:
        print("\n⚠️  --blog-id가 없어서 발행을 건너뜁니다.")
        return article, None

    print(f"\n📤 STEP 2: 네이버 발행 중...")
    print(f"   블로그 ID: {blog_id}")

    chrome_path = chrome_user_data or get_default_chrome_user_data()

    publish_config = PublishConfig(
        blog_id=blog_id,
        tags=article.tags[:5] if article.tags else [],
        chrome_user_data_dir=chrome_path,
        headless=not visible,
        slow_mo=150,
        screenshot_on_error=True
    )

    publisher = NaverPublisher()
    result = await publisher.publish(
        title=article.title,
        content=article.content,
        config=publish_config
    )

    if result.success:
        print(f"\n✅ 발행 성공!")
        print(f"   URL: {result.blog_url}")
        print(f"   Post ID: {result.post_id}")
    else:
        print(f"\n❌ 발행 실패: {result.error_message}")
        if result.screenshots:
            print(f"   스크린샷: {result.screenshots}")

    # ===== STEP 3: 트래픽 트리거 =====
    traffic_result = None
    if campaign_id and result.success:
        print(f"\n🚗 STEP 3: 트래픽 트리거 실행 중...")
        print(f"   캠페인 ID: {campaign_id}")

        trigger_config = TrafficTriggerConfig(
            api_base_url=traffic_api_url,
            api_key="careon-traffic-engine-2026"
        )
        trigger = TrafficTrigger(config=trigger_config)

        # ai-project 서버 상태 확인
        if await trigger.health_check():
            # AI 모드로 트래픽 실행
            traffic_result = await trigger.execute_ai(
                campaign_id=campaign_id,
                keyword=keyword,
                blog_title=article.title,
                blog_url=result.blog_url
            )

            if traffic_result.success:
                print(f"\n✅ 트래픽 트리거 성공!")
                print(f"   Execution ID: {traffic_result.execution_id}")
            else:
                print(f"\n⚠️  트래픽 트리거 실패: {traffic_result.error}")
        else:
            print(f"\n⚠️  ai-project 서버에 연결할 수 없습니다.")
            print(f"   URL: {traffic_api_url}")

    # ===== 결과 요약 =====
    print("\n" + "=" * 60)
    print("📊 파이프라인 결과 요약")
    print("=" * 60)
    print(f"키워드: {keyword}")
    print(f"제목: {article.title}")
    print(f"원고 생성: ✅")
    print(f"네이버 발행: {'✅' if result.success else '❌'}")
    if result.success:
        print(f"발행 URL: {result.blog_url}")
    if campaign_id:
        print(f"트래픽 트리거: {'✅' if (traffic_result and traffic_result.success) else '❌' if traffic_result else '⏭️ 건너뜀'}")
    print("=" * 60)

    return article, result, traffic_result


async def main():
    parser = argparse.ArgumentParser(description='Blog Writer 파이프라인 테스트')

    parser.add_argument('--keyword', '-k', required=True, help='타겟 키워드')
    parser.add_argument('--blog-id', '-b', help='네이버 블로그 ID')
    parser.add_argument('--generate-only', action='store_true', help='원고 생성만 (발행 안 함)')
    parser.add_argument('--visible', action='store_true', help='브라우저 창 표시')
    parser.add_argument('--chrome-user-data', help='Chrome 유저 데이터 경로')
    parser.add_argument('--campaign-id', '-c', help='캠페인 ID (트래픽 트리거용)')
    parser.add_argument('--traffic-api-url', default='http://localhost:8000', help='ai-project API URL')

    args = parser.parse_args()

    await run_pipeline(
        keyword=args.keyword,
        blog_id=args.blog_id,
        generate_only=args.generate_only,
        visible=args.visible,
        chrome_user_data=args.chrome_user_data,
        campaign_id=args.campaign_id,
        traffic_api_url=args.traffic_api_url
    )


if __name__ == "__main__":
    asyncio.run(main())
