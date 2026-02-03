"""
PostClassifier - 블로그 포스트 자동 분류기

키워드 가중치 기반으로 포스트를 카테고리에 매핑합니다.
"""

import re
from typing import Dict, List, Tuple

from src.shared.models import BlogArchive

# 카테고리별 키워드 가중치
CATEGORY_KEYWORDS: Dict[str, List[Tuple[str, int]]] = {
    "렌탈비교": [
        ("렌탈", 3),
        ("구매형", 3),
        ("월 0원", 2),
        ("월정액", 2),
        ("약정", 2),
        ("위약금", 2),
        ("총비용", 2),
        ("비용 비교", 3),
        ("호갱", 2),
        ("할부", 1),
        ("소유권", 1),
        ("렌탈료", 2),
        ("렌탈 vs", 3),
        ("구매 vs", 3),
    ],
    "법적이슈": [
        ("불법", 3),
        ("합법", 3),
        ("개인정보보호법", 3),
        ("과태료", 3),
        ("벌금", 2),
        ("동의서", 2),
        ("사생활", 2),
        ("법적", 2),
        ("위법", 3),
        ("고소", 2),
        ("징역", 2),
        ("처벌", 2),
        ("전과자", 2),
        ("음성 녹음", 2),
        ("촬영 각도", 1),
    ],
    "해킹보안": [
        ("해킹", 3),
        ("보안 설정", 2),
        ("비밀번호", 2),
        ("백도어", 3),
        ("사생활 유출", 2),
        ("펌웨어", 2),
        ("2단계 인증", 2),
        ("중국산", 1),
        ("국산", 1),
        ("칩셋", 2),
        ("생중계", 2),
        ("타포", 1),
        ("Tapo", 1),
    ],
    "설치가이드": [
        ("설치 가이드", 3),
        ("자가설치", 3),
        ("설치법", 2),
        ("설치할 때", 2),
        ("방수", 2),
        ("배선", 2),
        ("마감", 1),
        ("하이박스", 2),
        ("하드디스크", 1),
        ("DIY", 2),
        ("설치 비용", 1),
        ("설치 수칙", 2),
    ],
    "제품리뷰": [
        ("캠앤", 2),
        ("500만화소", 2),
        ("소형CCTV", 2),
        ("야간", 1),
        ("화질", 1),
        ("WDR", 2),
        ("태양광CCTV", 2),
        ("업소용", 1),
        ("가성비", 1),
        ("한화비전", 2),
        ("국산CCTV", 1),
        ("원격모니터", 2),
    ],
    "현관보안": [
        ("현관", 3),
        ("도어가드", 3),
        ("도어캠", 2),
        ("캡스도어가드", 3),
        ("아파트현관", 3),
        ("집앞", 2),
        ("도어락", 1),
        ("택배 도난", 2),
        ("현관문", 2),
        ("출동", 1),
    ],
    "업체비교": [
        ("세콤", 2),
        ("캡스", 2),
        ("KT텔레캅", 2),
        ("KTCCTV", 2),
        ("에스원", 2),
        ("ADT", 2),
        ("텔레캅", 2),
        ("통신사", 1),
        ("업체", 1),
        ("견적", 2),
        ("세콤비용", 3),
        ("세콤CCTV", 3),
    ],
    "지역특화": [
        ("부산", 3),
        ("서울", 3),
        ("대구", 3),
        ("인천", 3),
        ("광주", 3),
        ("대전", 3),
        ("전국", 2),
    ],
}

# 태그 추출용 키워드 풀
TAG_KEYWORDS: List[str] = [
    "CCTV",
    "렌탈",
    "구매형",
    "설치",
    "비용",
    "해킹",
    "보안",
    "법적",
    "국산",
    "현관",
    "아파트",
    "매장",
    "사무실",
    "농막",
    "외부",
    "태양광",
    "소형",
    "500만화소",
    "세콤",
    "캡스",
    "KT",
    "텔레캅",
    "도어가드",
    "홈캠",
    "타포",
    "가성비",
    "견적",
    "가격",
    "위약금",
    "약정",
]


class PostClassifier:
    """블로그 포스트 자동 분류기"""

    def __init__(
        self,
        category_keywords: Dict[str, List[Tuple[str, int]]] = None,
        tag_keywords: List[str] = None,
    ):
        self.category_keywords = category_keywords or CATEGORY_KEYWORDS
        self.tag_keywords = tag_keywords or TAG_KEYWORDS

    def classify(self, post: BlogArchive) -> BlogArchive:
        """포스트를 분류하고 카테고리/태그/키워드를 설정"""
        text = f"{post.original_title} {post.clean_content or post.original_content}"

        post.category = self._determine_category(text)
        post.tags = self._extract_tags(text)
        post.primary_keyword = self._extract_primary_keyword(post.original_title)

        return post

    def classify_batch(self, posts: List[BlogArchive]) -> List[BlogArchive]:
        """여러 포스트를 일괄 분류"""
        return [self.classify(post) for post in posts]

    def _determine_category(self, text: str) -> str:
        """가중치 점수 기반 카테고리 결정"""
        scores: Dict[str, int] = {}

        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword, weight in keywords:
                count = text.lower().count(keyword.lower())
                if count > 0:
                    score += weight * min(count, 3)  # 최대 3회까지만 카운트
            scores[category] = score

        if not scores or max(scores.values()) == 0:
            return "general"

        return max(scores, key=scores.get)

    def _extract_tags(self, text: str) -> List[str]:
        """본문에서 태그 추출"""
        found_tags = []
        text_lower = text.lower()

        for keyword in self.tag_keywords:
            if keyword.lower() in text_lower:
                found_tags.append(keyword)

        return found_tags[:10]  # 최대 10개

    def _extract_primary_keyword(self, title: str) -> str:
        """제목에서 주요 키워드 추출

        제목의 첫 번째 핵심 명사구를 키워드로 추출합니다.
        """
        # 일반적인 제목 패턴에서 키워드 추출
        # 예: "캡스도어가드 '초기 비용 0원'에 속지 마세요!" → "캡스도어가드"
        # 예: "CCTV 렌탈 '초기비용 0원'의 비극..." → "CCTV 렌탈"
        # 예: "(필독!) 사무실CCTV..." → "사무실CCTV"

        # 괄호/특수문자 접두사 제거
        cleaned = re.sub(r"^[\(\[（【].*?[\)\]）】]\s*!?\s*", "", title)
        cleaned = cleaned.strip()

        # 첫 번째 의미있는 단어(들) 추출
        # 작은따옴표 이전까지의 텍스트
        quote_idx = cleaned.find("'")
        if quote_idx > 0:
            candidate = cleaned[:quote_idx].strip()
            if len(candidate) >= 2:
                return candidate

        # 쉼표/마침표/물음표 이전
        for sep in [",", ".", "?", "!", "…"]:
            sep_idx = cleaned.find(sep)
            if 2 < sep_idx < 30:
                candidate = cleaned[:sep_idx].strip()
                if len(candidate) >= 2:
                    return candidate

        # 공백으로 분리하여 첫 2-3 단어
        words = cleaned.split()
        if len(words) >= 2:
            candidate = " ".join(words[:3])
            if len(candidate) > 20:
                candidate = " ".join(words[:2])
            return candidate

        return cleaned[:20] if cleaned else title[:20]

    def get_distribution(self, posts: List[BlogArchive]) -> Dict[str, int]:
        """분류 결과 분포 반환"""
        dist: Dict[str, int] = {}
        for post in posts:
            cat = post.category or "general"
            dist[cat] = dist.get(cat, 0) + 1
        return dict(sorted(dist.items(), key=lambda x: -x[1]))
