"""
블로그 아카이브 임포트 CLI 스크립트

Usage:
    # dry-run (파싱만, DB 저장 안 함)
    python scripts/import_blog_archive.py data/blog-cctv.txt --dry-run

    # 실제 임포트
    python scripts/import_blog_archive.py data/blog-cctv.txt

    # 배치 크기 지정
    python scripts/import_blog_archive.py data/blog-cctv.txt --batch-size 20
"""

import argparse
import json
import logging
import sys
import uuid
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.archive.parser import BlogArchiveParser
from src.archive.classifier import PostClassifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("import_archive")


def main():
    parser = argparse.ArgumentParser(description="블로그 아카이브 텍스트 파일을 DB에 임포트")
    parser.add_argument("file", help="파싱할 텍스트 파일 경로")
    parser.add_argument("--dry-run", action="store_true", help="파싱만 실행 (DB 저장 안 함)")
    parser.add_argument("--batch-size", type=int, default=50, help="DB 저장 배치 크기")
    parser.add_argument("--output", help="dry-run 결과를 JSON으로 저장할 경로")
    parser.add_argument("--verbose", "-v", action="store_true", help="상세 출력")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    file_path = Path(args.file)
    if not file_path.exists():
        logger.error(f"파일을 찾을 수 없습니다: {file_path}")
        sys.exit(1)

    # 1. 파싱
    logger.info(f"파싱 시작: {file_path}")
    archive_parser = BlogArchiveParser(source_file=file_path.name)
    posts = archive_parser.parse_file(str(file_path))
    logger.info(f"파싱 완료: {len(posts)}개 포스트")

    # 2. 분류
    logger.info("자동 분류 시작...")
    classifier = PostClassifier()
    posts = classifier.classify_batch(posts)
    logger.info("분류 완료")

    # 3. 배치 ID 설정
    batch_id = str(uuid.uuid4())[:8]
    for post in posts:
        post.import_batch_id = batch_id

    # 4. 통계 출력
    stats = archive_parser.get_stats(posts)
    distribution = classifier.get_distribution(posts)

    print("\n" + "=" * 60)
    print(f"  파싱 결과 요약 (batch: {batch_id})")
    print("=" * 60)
    print(f"  총 포스트 수: {stats['total']}")
    print(f"  SEO 메모 있음: {stats['with_seo_memo']}")
    print(f"  SEO 메모 없음: {stats['without_seo_memo']}")
    print(f"  날짜 범위: {stats['date_range']['earliest']} ~ {stats['date_range']['latest']}")
    print(f"  평균 글자 수: {stats['avg_word_count']:,}")
    print(f"  총 조회수: {stats['total_views']:,}")
    print()
    print("  카테고리 분포:")
    for cat, count in distribution.items():
        bar = "█" * count
        print(f"    {cat:12s} │ {count:3d} │ {bar}")
    print("=" * 60)

    # 5. 샘플 출력
    if args.verbose and posts:
        print("\n  처음 3개 포스트:")
        for p in posts[:3]:
            print(f"    [{p.parse_order}] {p.original_title[:50]}")
            print(f"        카테고리: {p.category} | 키워드: {p.primary_keyword}")
            print(f"        글자수: {p.word_count:,} | 조회수: {p.view_count}")
            print(f"        태그: {', '.join(p.tags[:5])}")
            print(f"        SEO 메모: {'있음' if p.has_seo_memo else '없음'}")
            print()

    # 6. dry-run 결과 저장
    if args.dry_run:
        logger.info("dry-run 모드: DB 저장을 건너뜁니다.")

        if args.output:
            output_path = Path(args.output)
            result = {
                "batch_id": batch_id,
                "stats": stats,
                "distribution": distribution,
                "posts": [p.to_dict() for p in posts],
            }
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"결과 저장: {output_path}")

        print(f"\n  dry-run 완료. 실제 임포트: --dry-run 플래그 제거")
        return

    # 7. DB 저장
    logger.info("Supabase에 저장 시작...")
    try:
        from src.core.config import get_settings
        from src.shared.supabase_client import SupabaseClient

        settings = get_settings()
        db = SupabaseClient(url=settings.supabase_url, key=settings.supabase_service_key)

        total_saved = 0
        for i in range(0, len(posts), args.batch_size):
            batch = posts[i : i + args.batch_size]
            saved = db.bulk_create_archives(batch)
            total_saved += saved
            logger.info(f"  배치 {i // args.batch_size + 1}: {saved}개 저장")

        print(f"\n  DB 저장 완료: {total_saved}/{len(posts)}개")

    except Exception as e:
        logger.error(f"DB 저장 실패: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
