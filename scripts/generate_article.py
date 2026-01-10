#!/usr/bin/env python3
"""
블로그 원고 생성 CLI

사용법:
    python scripts/generate_article.py --keyword "매장CCTV설치비용"
    python scripts/generate_article.py --keyword "가게CCTV" --template expert_review
    python scripts/generate_article.py --keyword "CCTV가격" --save
"""

import asyncio
import argparse
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv(project_root / ".env")

from src.content.generator import ContentGenerator
from src.shared.models import ArticleConfig, ArticleTemplate, ContentTone
from src.shared.supabase_client import SupabaseClient
from src.core.config import settings


async def main():
    parser = argparse.ArgumentParser(description="블로그 원고 생성")
    parser.add_argument("--keyword", "-k", required=True, help="타겟 키워드")
    parser.add_argument(
        "--template", "-t",
        choices=["personal_story", "expert_review", "comparison"],
        default="personal_story",
        help="템플릿 유형"
    )
    parser.add_argument(
        "--tone",
        choices=["casual", "professional", "emotional", "informative"],
        default="emotional",
        help="톤앤매너"
    )
    parser.add_argument(
        "--audience", "-a",
        choices=["소상공인", "가정", "기업"],
        default="소상공인",
        help="타겟 독자"
    )
    parser.add_argument("--length", "-l", type=int, default=3000, help="목표 글자 수")
    parser.add_argument("--save", "-s", action="store_true", help="Supabase에 저장")
    parser.add_argument("--output", "-o", help="출력 파일 경로 (마크다운)")

    args = parser.parse_args()

    # API 키 확인
    api_key = settings.deepseek_api_key
    if not api_key:
        print("Error: DEEPSEEK_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("  .env 파일에 DEEPSEEK_API_KEY=your-key 를 추가하세요.")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"블로그 원고 생성 시작")
    print(f"{'='*60}")
    print(f"키워드: {args.keyword}")
    print(f"템플릿: {args.template}")
    print(f"톤: {args.tone}")
    print(f"타겟 독자: {args.audience}")
    print(f"목표 길이: {args.length}자")
    print(f"{'='*60}\n")

    # ContentGenerator 초기화
    generator = ContentGenerator(
        deepseek_api_key=api_key,
        model=settings.deepseek_model
    )

    # 설정 생성
    config = ArticleConfig(
        keyword=args.keyword,
        template=ArticleTemplate(args.template),
        tone=ContentTone(args.tone),
        target_audience=args.audience,
        target_length=args.length,
    )

    try:
        # 원고 생성
        print("원고 생성 중... (1-2분 소요될 수 있습니다)")
        article = await generator.generate(args.keyword, config)

        print(f"\n{'='*60}")
        print("원고 생성 완료!")
        print(f"{'='*60}")
        print(f"제목: {article.title}")
        print(f"글자 수: {article.word_count}")
        print(f"품질 점수: {article.quality_score:.2f}")
        print(f"SEO 점수: {article.seo_score:.2f}")
        print(f"가독성 점수: {article.readability_score:.2f}")
        print(f"태그: {', '.join(article.tags[:5])}")
        print(f"{'='*60}\n")

        # 콘텐츠 미리보기
        preview_length = 500
        print("--- 콘텐츠 미리보기 ---")
        print(article.content[:preview_length])
        if len(article.content) > preview_length:
            print(f"\n... (총 {len(article.content)}자)")
        print("--- 미리보기 끝 ---\n")

        # 파일로 저장
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(f"# {article.title}\n\n")
                f.write(f"> 키워드: {article.keyword}\n")
                f.write(f"> 생성일: {article.created_at}\n\n")
                f.write(article.content)
            print(f"파일 저장됨: {output_path}")

        # Supabase에 저장
        if args.save:
            print("Supabase에 저장 중...")
            client = SupabaseClient(
                url=settings.supabase_url,
                key=settings.supabase_service_key
            )
            saved_article = client.create_article(article)
            print(f"저장 완료! ID: {saved_article.id}")

        return article

    except Exception as e:
        print(f"\n오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
