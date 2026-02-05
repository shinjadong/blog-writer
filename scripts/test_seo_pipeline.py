#!/usr/bin/env python3
"""
SEO 자동 발행 파이프라인 테스트 스크립트

네이버 검색 → 경쟁 분석 → SEO 원고 생성 테스트

사용법:
    # 단일 키워드 테스트
    python scripts/test_seo_pipeline.py --keyword "매장CCTV설치비용"

    # 개별 단계 테스트
    python scripts/test_seo_pipeline.py --mode search --keyword "CCTV설치비용"
    python scripts/test_seo_pipeline.py --mode reasoner
    python scripts/test_seo_pipeline.py --mode analyzer --keyword "CCTV설치비용"
    python scripts/test_seo_pipeline.py --mode full --keyword "매장CCTV설치비용"
"""

import asyncio
import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.config import get_settings
from src.research.naver_search import NaverSearchClient
from src.research.competition_analyzer import CompetitionAnalyzer
from src.shared.deepseek_client import DeepSeekClient
from src.pipeline.auto_publisher import AutoPublisher


async def test_naver_search(keyword: str = "CCTV 설치 비용"):
    """네이버 검색 API 테스트"""
    print("\n" + "=" * 50)
    print("네이버 검색 API 테스트")
    print("=" * 50)

    settings = get_settings()

    if not settings.naver_client_id or not settings.naver_client_secret:
        print("오류: NAVER_CLIENT_ID 또는 NAVER_CLIENT_SECRET이 설정되지 않았습니다.")
        return None

    client = NaverSearchClient(
        client_id=settings.naver_client_id,
        client_secret=settings.naver_client_secret
    )

    print(f"검색 키워드: {keyword}")

    try:
        result = await client.search_and_analyze(keyword, display=10)

        print(f"\n총 검색 결과: {result.get('total_results', 0):,}건")
        print(f"상위 블로그 수: {len(result.get('top_blogs', []))}")

        print("\n상위 5개 블로그:")
        for blog in result.get("top_blogs", [])[:5]:
            print(f"  {blog['rank']}위: {blog['title'][:50]}...")
            print(f"       블로거: {blog['bloggername']}")

        return result

    except Exception as e:
        print(f"오류: {e}")
        return None


async def test_deepseek_reasoner():
    """DeepSeek Reasoner 테스트"""
    print("\n" + "=" * 50)
    print("DeepSeek Reasoner 테스트")
    print("=" * 50)

    settings = get_settings()

    if not settings.deepseek_api_key:
        print("오류: DEEPSEEK_API_KEY가 설정되지 않았습니다.")
        return None

    client = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model
    )

    prompt = """다음 JSON 형식으로 CCTV 설치에 대한 간단한 분석을 제공하세요:
{
    "topic": "CCTV 설치",
    "key_points": ["포인트1", "포인트2", "포인트3"],
    "recommendation": "추천 내용"
}
JSON만 출력하세요."""

    print("Reasoner 호출 중... (시간이 걸릴 수 있습니다)")

    try:
        result = await client.reason_json(user_prompt=prompt)

        print(f"\n추론 과정 (일부):")
        print(f"  {result['reasoning_content'][:300]}...")

        print(f"\n결과:")
        print(json.dumps(result['data'], ensure_ascii=False, indent=2))

        print(f"\n토큰 사용량:")
        usage = result.get('usage', {})
        print(f"  프롬프트: {usage.get('prompt_tokens', 0)}")
        print(f"  추론: {usage.get('reasoning_tokens', 0)}")
        print(f"  완성: {usage.get('completion_tokens', 0)}")

        return result

    except Exception as e:
        print(f"오류: {e}")
        return None


async def test_competition_analyzer(keyword: str = "CCTV 설치 비용"):
    """경쟁 분석기 테스트"""
    print("\n" + "=" * 50)
    print("경쟁 분석기 테스트")
    print("=" * 50)

    # 먼저 검색 수행
    search_result = await test_naver_search(keyword)
    if not search_result:
        return None

    settings = get_settings()
    client = DeepSeekClient(
        api_key=settings.deepseek_api_key,
        model=settings.deepseek_model
    )

    analyzer = CompetitionAnalyzer(client)

    print("\n경쟁 분석 중... (시간이 걸릴 수 있습니다)")

    try:
        analysis = await analyzer.analyze(search_result)

        print(f"\n분석 결과:")
        print(f"  경쟁도: {analysis.competition_level}")
        print(f"  검색 의도: {analysis.search_intent}")
        print(f"  평균 글자수: {analysis.avg_word_count}")

        print(f"\n콘텐츠 갭:")
        for gap in analysis.content_gaps[:5]:
            print(f"  - {gap}")

        print(f"\nSEO 권장사항:")
        for rec in analysis.seo_recommendations[:5]:
            print(f"  - {rec}")

        print(f"\n제목 제안:")
        for title in analysis.title_suggestions[:3]:
            print(f"  - {title}")

        return analyzer.to_dict(analysis)

    except Exception as e:
        print(f"오류: {e}")
        return None


async def test_full_pipeline(keyword: str = "매장CCTV설치비용"):
    """전체 파이프라인 테스트"""
    print("\n" + "=" * 50)
    print("전체 SEO 파이프라인 테스트")
    print("=" * 50)

    print(f"처리 키워드: {keyword}")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        publisher = AutoPublisher()
        result = await publisher.process_single(keyword)

        print(f"\n처리 완료!")
        print(f"  단계: {' → '.join(result.get('steps', []))}")

        if 'title' in result:
            print(f"  제목: {result['title']}")
        if 'word_count' in result:
            print(f"  글자수: {result['word_count']}")
        if 'article_id' in result:
            print(f"  원고 ID: {result['article_id']}")

        # 생성된 파일 확인
        articles_dir = Path("data/generated_articles")
        if articles_dir.exists():
            safe_keyword = keyword.replace(" ", "_").replace("/", "_")
            md_file = articles_dir / f"{safe_keyword}_article.md"

            if md_file.exists():
                print(f"\n생성된 원고 파일: {md_file}")

                # 원고 미리보기
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    print(f"\n원고 미리보기 (처음 500자):")
                    print("-" * 40)
                    print(content[:500])
                    print("-" * 40)
                    print(f"... (총 {len(content)}자)")

        return result

    except Exception as e:
        print(f"오류: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    parser = argparse.ArgumentParser(description='SEO 자동 발행 파이프라인 테스트')

    parser.add_argument(
        '--mode', '-m',
        choices=['search', 'reasoner', 'analyzer', 'full'],
        default='full',
        help='테스트 모드 (기본: full)'
    )
    parser.add_argument(
        '--keyword', '-k',
        default='매장CCTV설치비용',
        help='테스트할 키워드 (기본: 매장CCTV설치비용)'
    )

    args = parser.parse_args()

    print("\n" + "#" * 50)
    print(" SEO 파이프라인 테스트")
    print("#" * 50)
    print(f"모드: {args.mode}")
    print(f"키워드: {args.keyword}")

    if args.mode == 'search':
        await test_naver_search(args.keyword)
    elif args.mode == 'reasoner':
        await test_deepseek_reasoner()
    elif args.mode == 'analyzer':
        await test_competition_analyzer(args.keyword)
    else:  # full
        await test_full_pipeline(args.keyword)

    print("\n테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
