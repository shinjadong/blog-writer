"""
BlogArchiveParser - 네이버 블로그 텍스트 파일 파서

사진 개수N 구분자 기반 상태 머신으로 포스트를 파싱합니다.
"""

import re
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional, Tuple

from src.shared.models import BlogArchive


class BlogArchiveParser:
    """블로그 아카이브 텍스트 파일 파서"""

    PHOTO_COUNT_RE = re.compile(r"^사진 개수(\d+)$")
    DATE_RE = re.compile(r"^(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})\.$")
    SEO_MEMO_MARKER = "\U0001f4c8"  # 📈

    class _State:
        IDLE = "idle"
        AWAITING_TITLE = "awaiting_title"
        AWAITING_CONTENT = "awaiting_content"
        AWAITING_DATE = "awaiting_date"
        AWAITING_VIEWS = "awaiting_views"

    def __init__(self, source_file: str = "blog-cctv.txt"):
        self.source_file = source_file

    def parse_file(self, file_path: str) -> List[BlogArchive]:
        """파일 전체를 파싱하여 BlogArchive 리스트 반환"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")

        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        lines = [line.rstrip("\n") for line in lines]
        return self._parse_lines(lines)

    def _parse_lines(self, lines: List[str]) -> List[BlogArchive]:
        """라인 리스트를 상태 머신으로 파싱"""
        posts: List[BlogArchive] = []
        state = self._State.IDLE
        parse_order = 0

        photo_count = 0
        title = ""
        content = ""
        start_line = 0
        original_date = date(2025, 1, 1)

        for line_num, raw_line in enumerate(lines, start=1):
            stripped = raw_line.strip()

            if state == self._State.IDLE:
                match = self.PHOTO_COUNT_RE.match(stripped)
                if match:
                    photo_count = int(match.group(1))
                    start_line = line_num
                    state = self._State.AWAITING_TITLE

            elif state == self._State.AWAITING_TITLE:
                if stripped:
                    title = stripped
                    state = self._State.AWAITING_CONTENT

            elif state == self._State.AWAITING_CONTENT:
                # 빈 줄 건너뛰고 첫 번째 비어있지 않은 줄 = 본문
                if stripped:
                    content = stripped
                    state = self._State.AWAITING_DATE

            elif state == self._State.AWAITING_DATE:
                date_match = self.DATE_RE.match(stripped)
                if date_match:
                    try:
                        original_date = date(
                            int(date_match.group(1)),
                            int(date_match.group(2)),
                            int(date_match.group(3)),
                        )
                    except ValueError:
                        original_date = date(2025, 1, 1)
                    state = self._State.AWAITING_VIEWS
                # 날짜가 아닌 줄은 본문의 연속으로 처리 (혹시 멀티라인인 경우)
                elif stripped:
                    content += " " + stripped

            elif state == self._State.AWAITING_VIEWS:
                if stripped.isdigit():
                    view_count = int(stripped)
                elif stripped == "":
                    # 빈 줄이면 아직 조회수 대기
                    continue
                else:
                    # 조회수가 아닌 다른 내용 → 조회수 0으로 처리
                    view_count = 0

                # SEO 메모 분리
                seo_memo, clean_content = self._extract_seo_memo(content, title)

                parse_order += 1
                post = BlogArchive(
                    id=str(uuid.uuid4()),
                    original_title=title,
                    original_content=content,
                    seo_memo=seo_memo,
                    clean_content=clean_content,
                    photo_count=photo_count,
                    original_date=original_date,
                    view_count=view_count,
                    word_count=len(clean_content),
                    has_seo_memo=seo_memo is not None,
                    source_file=self.source_file,
                    source_line=start_line,
                    parse_order=parse_order,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                posts.append(post)

                # 상태 리셋
                state = self._State.IDLE
                photo_count = 0
                title = ""
                content = ""
                start_line = 0

                # 현재 줄이 다음 블록의 시작인지 확인
                if not stripped.isdigit():
                    next_match = self.PHOTO_COUNT_RE.match(stripped)
                    if next_match:
                        photo_count = int(next_match.group(1))
                        start_line = line_num
                        state = self._State.AWAITING_TITLE

        return posts

    def _extract_seo_memo(
        self, content: str, title: str
    ) -> Tuple[Optional[str], str]:
        """SEO 메모(📈 블록)를 본문에서 분리

        SEO 메모가 있는 포스트는 본문이 📈로 시작하며,
        실제 제목이 본문 내에서 반복되는 지점까지가 메모입니다.
        """
        if not content.startswith(self.SEO_MEMO_MARKER):
            return None, content

        # 제목이 본문에서 반복되는 위치 찾기
        title_idx = content.find(title)
        if title_idx > 0:
            seo_memo = content[:title_idx].strip()
            clean_content = content[title_idx:].strip()
            return seo_memo, clean_content

        # 제목을 못 찾은 경우 전체를 clean으로 반환
        return content, ""

    def get_stats(self, posts: List[BlogArchive]) -> dict:
        """파싱 결과 통계 반환"""
        if not posts:
            return {"total": 0}

        dates = [p.original_date for p in posts if p.original_date]
        seo_count = sum(1 for p in posts if p.has_seo_memo)

        return {
            "total": len(posts),
            "with_seo_memo": seo_count,
            "without_seo_memo": len(posts) - seo_count,
            "date_range": {
                "earliest": min(dates).isoformat() if dates else None,
                "latest": max(dates).isoformat() if dates else None,
            },
            "avg_word_count": sum(p.word_count for p in posts) // len(posts),
            "total_views": sum(p.view_count for p in posts),
        }
