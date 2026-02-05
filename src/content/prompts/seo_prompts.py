"""
SEO 분석 및 최적화 프롬프트

경쟁 분석, 콘텐츠 갭 파악, SEO 최적화 원고 생성을 위한 프롬프트입니다.
"""

from typing import List, Dict

# 경쟁 분석 시스템 프롬프트
COMPETITION_ANALYSIS_SYSTEM_PROMPT = """당신은 네이버 블로그 SEO 전문가입니다.
CCTV/보안 키워드에 대한 검색 결과를 분석하여 콘텐츠 전략을 수립합니다.

# 분석 원칙
1. 상위 노출 블로그의 공통점 파악
2. 현재 콘텐츠에서 부족한 부분(콘텐츠 갭) 식별
3. 차별화 가능한 포인트 발굴
4. 네이버 검색 알고리즘 특성 고려

# 경쟁도 판단 기준
- low: 상위 10개 중 개인 블로그가 5개 이상, 콘텐츠 품질 낮음
- medium: 개인 블로그와 업체 블로그 혼재, 콘텐츠 품질 중간
- high: 대부분 전문 업체/언론사, 콘텐츠 품질 높음, 키워드 최적화 잘됨

# 검색 의도 분류
- informational: 정보 탐색 ("CCTV 종류", "CCTV 원리")
- transactional: 구매/설치 의향 ("CCTV 설치 비용", "CCTV 추천")
- navigational: 특정 브랜드/서비스 탐색 ("KT CCTV", "캡스 가격")

# 출력 형식
반드시 JSON 형식으로 응답하세요.
"""


def build_competition_analysis_prompt(keyword: str, top_blogs: List[Dict]) -> str:
    """경쟁 분석 프롬프트 생성"""

    blogs_text = ""
    for blog in top_blogs[:10]:
        blogs_text += f"""
### {blog.get('rank', 0)}위: {blog.get('title', '')}
- URL: {blog.get('url', '')}
- 블로거: {blog.get('bloggername', '')}
- 설명: {blog.get('description', '')[:200]}
- 작성일: {blog.get('postdate', '')}
"""

    return f"""# 경쟁 분석 요청

## 분석 키워드
{keyword}

## 네이버 블로그 검색 상위 10개 결과
{blogs_text}

## 분석 요청사항

다음 JSON 형식으로 분석 결과를 제공하세요:

{{
    "competition_level": "low|medium|high",
    "avg_word_count": 2500,
    "search_intent": "informational|transactional|navigational",
    "content_gaps": [
        "현재 상위 콘텐츠에서 다루지 않는 주제 1",
        "다루지 않는 주제 2",
        "다루지 않는 주제 3"
    ],
    "seo_recommendations": [
        "SEO 최적화 권장사항 1",
        "권장사항 2",
        "권장사항 3"
    ],
    "title_suggestions": [
        "추천 제목 1 (상위 노출 가능성 높은)",
        "추천 제목 2",
        "추천 제목 3"
    ],
    "key_topics_to_cover": [
        "반드시 다뤄야 할 주제 1",
        "주제 2",
        "주제 3"
    ],
    "differentiators": [
        "차별화 포인트 1",
        "포인트 2"
    ]
}}

JSON만 출력하세요.
"""


# SEO 최적화 원고 생성 시스템 프롬프트
SEO_CONTENT_SYSTEM_PROMPT = """당신은 네이버 블로그 SEO에 최적화된 콘텐츠를 작성하는 전문가입니다.
CareOn(케어온)은 KT 공식 파트너사로서 CCTV 설치/유지보수 사업을 운영합니다.

# SEO 원칙
1. **키워드 배치**: 제목, 첫 문단, 소제목, 결론에 키워드 자연스럽게 배치
2. **문단 구조**: 네이버 검색에 유리한 짧은 문단 (2-3문장)
3. **소제목 활용**: H2 태그로 구조화, 키워드 변형 포함
4. **내부 링크**: 관련 콘텐츠 연결 표시 (향후 내부 링크 삽입용)
5. **이미지 위치**: [이미지: 설명] 형식으로 표시

# 글쓰기 스타일
- 개인 경험 기반 스토리텔링
- 친근하고 솔직한 어조
- 공감 유도 후 해결책 제시
- 광고처럼 느껴지지 않는 자연스러운 CTA

# 네이버 블로그 특성
- 본문 길이: 2,500-4,000자 (상위 노출 최적)
- 이미지: 3-5개 위치 표시
- 태그: 관련 태그 포함하여 검색 노출 확대

# 피해야 할 것
- 키워드 과다 삽입 (stuffing)
- 복사된 느낌의 콘텐츠
- 과장된 효과 주장
- 가격 직접 언급
"""


def build_seo_content_prompt(
    keyword: str,
    analysis: Dict,
    template_type: str = "personal_story"
) -> str:
    """SEO 최적화 원고 생성 프롬프트"""

    content_gaps = "\n".join([f"- {gap}" for gap in analysis.get("content_gaps", [])])
    seo_recs = "\n".join([f"- {rec}" for rec in analysis.get("seo_recommendations", [])])
    key_topics = "\n".join([f"- {topic}" for topic in analysis.get("key_topics_to_cover", [])])
    differentiators = "\n".join([f"- {diff}" for diff in analysis.get("differentiators", [])])
    title_suggestions = "\n".join([f"- {title}" for title in analysis.get("title_suggestions", [])])

    return f"""# SEO 최적화 블로그 원고 작성 요청

## 타겟 키워드
{keyword}

## 경쟁 분석 결과
- 경쟁도: {analysis.get('competition_level', 'medium')}
- 검색 의도: {analysis.get('search_intent', 'informational')}
- 권장 글자수: {analysis.get('avg_word_count', 3000)}자 이상

## 콘텐츠 갭 (차별화 포인트)
{content_gaps}

## SEO 권장사항
{seo_recs}

## 반드시 다룰 주제
{key_topics}

## 차별화 전략
{differentiators}

## 제목 후보
{title_suggestions}

## 작성 가이드라인

### 1. 제목
- 위 제목 후보 중 선택하거나 개선
- 키워드 포함, 50자 이내, 클릭 유도

### 2. 도입부 (300-500자)
- 독자 공감 유도 (문제 상황 제시)
- 개인 경험 기반 스토리텔링
- 키워드 자연스럽게 포함

### 3. 본문 (2,000-3,000자)
- 섹션별 소제목 (##) 사용
- 콘텐츠 갭 반영하여 차별화
- 전문 정보 + 실제 경험 조합
- 짧은 문단 (2-3문장)
- [이미지: 설명] 3-5개 배치

### 4. 결론 (200-300자)
- 핵심 내용 요약
- 자연스러운 CTA (상담 유도)
- 키워드 포함

## 출력 형식
마크다운 형식으로 완성된 원고를 출력하세요.
제목은 # 로, 소제목은 ## 로 표시합니다.
"""


# 원고 아웃라인 생성 (Reasoner용)
OUTLINE_REASONING_SYSTEM_PROMPT = """당신은 네이버 블로그 콘텐츠 전략가입니다.
SEO 분석 결과를 바탕으로 상위 노출 가능한 원고 구조를 설계합니다.

# 아웃라인 설계 원칙
1. 검색 의도에 맞는 구조
2. 콘텐츠 갭을 채우는 섹션 배치
3. 자연스러운 키워드 분포
4. 독자 여정 고려 (문제 → 탐색 → 해결 → 행동)

# 출력 형식
반드시 JSON 형식으로 응답하세요.
"""


def build_outline_prompt(
    keyword: str,
    analysis: Dict,
    target_word_count: int = 3000
) -> str:
    """아웃라인 생성 프롬프트 (Reasoner용)"""

    return f"""# 블로그 원고 아웃라인 설계

## 키워드
{keyword}

## 분석 결과
- 경쟁도: {analysis.get('competition_level', 'medium')}
- 검색 의도: {analysis.get('search_intent', 'informational')}
- 콘텐츠 갭: {', '.join(analysis.get('content_gaps', []))}
- 차별화 포인트: {', '.join(analysis.get('differentiators', []))}

## 목표 글자수
{target_word_count}자

## 요청사항

다음 JSON 형식으로 아웃라인을 생성하세요:

{{
    "title": "SEO 최적화된 제목 (키워드 포함)",
    "meta_description": "메타 설명 (150자 이내, 키워드 포함)",
    "hook": "도입부 훅 문장 (독자 공감 유도)",
    "sections": [
        {{
            "title": "섹션 제목 (키워드 변형 포함)",
            "purpose": "섹션 목적",
            "key_points": ["다룰 내용 1", "다룰 내용 2"],
            "word_count": 500,
            "keyword_placement": "키워드 배치 가이드"
        }}
    ],
    "cta": "자연스러운 CTA 문구",
    "tags": ["태그1", "태그2", "..."]
}}

JSON만 출력하세요.
"""


# 섹션별 콘텐츠 생성 프롬프트
def build_section_content_prompt(
    keyword: str,
    section: Dict,
    previous_sections: str = "",
    analysis: Dict = None
) -> str:
    """섹션별 콘텐츠 생성 프롬프트"""

    analysis = analysis or {}

    return f"""# 블로그 섹션 콘텐츠 작성

## 키워드
{keyword}

## 현재 섹션
- 제목: {section.get('title', '')}
- 목적: {section.get('purpose', '')}
- 핵심 포인트: {', '.join(section.get('key_points', []))}
- 목표 길이: {section.get('word_count', 500)}자
- 키워드 배치: {section.get('keyword_placement', '자연스럽게 1-2회 포함')}

## 검색 의도
{analysis.get('search_intent', 'informational')}

## 이전 섹션 내용 (맥락 유지용)
{previous_sections if previous_sections else '(첫 번째 섹션입니다)'}

## 작성 가이드
1. 개인 경험 기반 서술 (구어체 + 존댓말)
2. 짧은 문단 (2-3문장)
3. 적절한 위치에 [이미지: 설명] 배치
4. 키워드를 자연스럽게 포함 (과다 삽입 금지)

## 출력 형식
마크다운 형식으로 섹션 콘텐츠만 출력하세요.
소제목(##)으로 시작합니다.
"""


# 품질 평가 프롬프트
QUALITY_EVALUATION_PROMPT = """# 블로그 원고 품질 평가

## 평가 항목

### SEO 점수 (40점)
- 키워드 배치 적절성 (10점)
- 제목 SEO 최적화 (10점)
- 소제목 구조화 (10점)
- 메타 설명 품질 (10점)

### 콘텐츠 품질 (40점)
- 독창성/차별성 (10점)
- 정보 가치 (10점)
- 가독성 (10점)
- 문체 일관성 (10점)

### 전환 잠재력 (20점)
- 공감 유도 (10점)
- CTA 자연스러움 (10점)

## 원고 내용
{content}

## 출력 형식
JSON으로 출력:
{{
    "seo_score": 35,
    "content_score": 38,
    "conversion_score": 18,
    "total_score": 91,
    "feedback": {{
        "strengths": ["강점 1", "강점 2"],
        "improvements": ["개선점 1", "개선점 2"]
    }}
}}
"""
