# Claude Code 컨텍스트 - CareOn Blog Writer

> AI 기반 블로그 원고 생성 및 네이버 자동 발행 시스템

---

## 필수: 세션 시작 전 읽을 문서

| 순서 | 문서 | 경로 | 내용 |
|------|------|------|------|
| 1 | 시스템 룰 | `../CLAUDE_RULES.md` | **필수** - 세션 시작/종료 프로토콜 |
| 2 | 마스터 컨텍스트 | `../MASTER_CONTEXT.md` | 전략, 아키텍처, 현재 우선순위 |
| 3 | 의사결정 로그 | `../DECISION_LOG.md` | 최근 피보팅/변경사항 |
| 4 | 프로젝트 상태 | `../PROJECT_STATUS.md` | 각 프로젝트 현재 상태 |
| 5 | API 계약 | `../API_CONTRACTS.md` | 프로젝트 간 API 스펙 |

### 연계 프로젝트

| 프로젝트 | 관계 | CLAUDE.md |
|----------|------|-----------|
| ai-project | 트래픽 트리거 대상 (발행 후 호출) | `../ai-project/CLAUDE.md` |
| blog-archetype | 원고 템플릿/키워드 참조 | `../blog-archetype/CLAUDE.md` |

### 주의사항

> 현재 알림 없음

---

## 프로젝트 개요

**blog-writer**는 CCTV 관련 블로그 콘텐츠를 AI로 자동 생성하고 네이버 블로그에 발행하는 시스템입니다.

### 역할
1. **원고 생성**: DeepSeek API로 CCTV 도메인 특화 콘텐츠 생성
2. **네이버 발행**: CDP(Chrome DevTools Protocol) 기반 자동 발행
3. **트래픽 트리거**: 발행 후 ai-project API 호출로 트래픽 부스팅

---

## 3단계 파이프라인

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  1. 원고 생성   │────▶│  2. 네이버 발행  │────▶│  3. 트래픽 트리거│
│  DeepSeek API   │     │  CDP 자동화     │     │  ai-project API │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Step 1: 원고 생성
```bash
POST /articles/generate
{
  "keyword": "CCTV 설치 비용",
  "template_type": "informational",
  "word_count": 2000
}
```

### Step 2: 네이버 발행
```bash
POST /publish/{article_id}
{
  "blog_id": "your-blog-id",
  "category": "IT/기술"
}
```

### Step 3: 트래픽 트리거
```bash
# 내부적으로 ai-project API 호출
POST http://localhost:8000/traffic/execute
{
  "campaign_id": "auto-created",
  "blog_url": "https://blog.naver.com/..."
}
```

---

## 기술 스택

| 항목 | 기술 |
|------|------|
| 언어 | Python 3.11+ |
| 웹 프레임워크 | FastAPI |
| AI | DeepSeek API |
| 브라우저 자동화 | Playwright + CDP |
| 데이터베이스 | Supabase |

---

## 프로젝트 구조

```
blog-writer/
├── CLAUDE.md                     # 이 문서
├── .env                          # 환경변수 (git 제외)
├── requirements.txt              # Python 의존성
│
├── src/
│   ├── api/
│   │   └── main.py               # FastAPI 서버 (포트 5001)
│   │
│   ├── content/
│   │   ├── generator.py          # ContentGenerator
│   │   └── prompts/
│   │       └── cctv_domain.py    # CCTV 특화 프롬프트
│   │
│   ├── publisher/
│   │   └── naver_publisher.py    # CDP 기반 네이버 발행
│   │
│   └── traffic/
│       └── trigger.py            # ai-project 트리거
│
└── data/
    └── cookies/                  # 네이버 로그인 쿠키
```

---

## 환경변수

```bash
# .env
DEEPSEEK_API_KEY=your-deepseek-api-key
SUPABASE_URL=https://pkehcfbjotctvneordob.supabase.co
SUPABASE_SERVICE_KEY=your-service-key
AI_PROJECT_URL=http://localhost:8000
AI_PROJECT_API_KEY=careon-traffic-engine-2026
NAVER_BLOG_ID=your-blog-id
```

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태 |
| POST | `/articles/generate` | 원고 생성 |
| GET | `/articles/{id}` | 원고 조회 |
| POST | `/publish/{article_id}` | 네이버 발행 |
| POST | `/pipeline/full` | 전체 파이프라인 (생성→발행→트래픽) |

---

## 실행 방법

```bash
# 가상환경 생성
python3.11 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium

# 서버 실행
uvicorn src.api.main:app --host 0.0.0.0 --port 5001 --reload
```

---

## 현재 상태

| 컴포넌트 | 상태 |
|----------|------|
| ContentGenerator | ✅ 완료 |
| NaverPublisher | ✅ 완료 |
| TrafficTrigger | ✅ 완료 |
| 파이프라인 API | ✅ 완료 |
| 네이버 쿠키 설정 | ⏳ 필요 |
| 실 발행 테스트 | ⏳ 필요 |

---

## 다음 작업

1. Ubuntu에서 환경 설정
2. Playwright 브라우저 설치
3. 네이버 로그인 쿠키 저장
4. 원고 생성 → 발행 테스트

---

*마지막 업데이트: 2026-01-10*
