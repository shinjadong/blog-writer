# Blog Writer - 네이버 블로그 자동 발행 시스템

AI 기반 적응형 네이버 블로그 자동 발행 시스템입니다. CDP(Chrome DevTools Protocol)와 Playwright를 활용하여 브라우저를 제어하고, DOM 파싱을 통해 UI 요소를 동적으로 파악합니다.

## 주요 기능

- **텍스트 입력**: 일반 텍스트, 굵은 텍스트 지원
- **이미지 업로드**: `expect_file_chooser`를 사용한 안정적인 이미지 업로드
- **이미지 링크**: 이미지 클릭 시 URL로 이동하는 링크 추가
- **하이퍼링크**: 텍스트에 URL 링크 삽입
- **인용구**: 스타일이 적용된 인용구 삽입
- **구분선**: 가로 구분선 삽입
- **자동 발행**: 발행 버튼 클릭 및 최종 발행 자동화

## 설치

```bash
# 가상환경 생성
python3 -m venv .venv
source .venv/bin/activate

# 의존성 설치
pip install -r requirements.txt

# Playwright 브라우저 설치
playwright install chromium
```

## 사전 요구사항

1. Chrome 브라우저가 디버깅 모드로 실행되어 있어야 합니다:
```bash
google-chrome --remote-debugging-port=9222
```

2. 네이버에 로그인된 상태여야 합니다.

## 사용법

### 기본 사용법

```python
import asyncio
from publisher.adaptive_publisher import adaptive_publish, PublishConfig

async def main():
    config = PublishConfig(
        blog_id="your_blog_id",
        cdp_url="http://localhost:9222"
    )

    sections = [
        {"type": "text", "content": "안녕하세요!"},
        {"type": "image", "path": "/path/to/image.jpg", "link": "https://example.com"},
        {"type": "quote", "content": "인용구 내용"},
        {"type": "divider"},
        {"type": "link", "url": "https://naver.com", "text": "네이버 바로가기"},
    ]

    result = await adaptive_publish(
        title="블로그 제목",
        sections=sections,
        config=config
    )

    if result.success:
        print(f"발행 성공: {result.blog_url}")
    else:
        print(f"발행 실패: {result.error_message}")

asyncio.run(main())
```

### 섹션 타입

| 타입 | 설명 | 필수 필드 | 선택 필드 |
|------|------|-----------|-----------|
| `text` | 일반 텍스트 | `content` | `format` (["bold"]) |
| `image` | 이미지 업로드 | `path` | `link`, `caption` |
| `link` | 하이퍼링크 | `url` | `text` |
| `quote` | 인용구 | `content` | - |
| `divider` | 구분선 | - | - |

### 이미지에 링크 추가

```python
{
    "type": "image",
    "path": "/path/to/image.jpg",
    "link": "https://example.com",  # 이미지 클릭 시 이동할 URL
    "caption": "이미지 설명"  # 선택사항
}
```

## 프로젝트 구조

```
blog-writer/
├── src/
│   └── publisher/
│       ├── __init__.py
│       ├── adaptive_publisher.py  # 메인 발행 로직
│       └── ai/
│           ├── __init__.py
│           └── ui_analyzer.py     # AI UI 분석기
├── scripts/
│   ├── test_full_publish.py       # 전체 발행 테스트
│   ├── test_image_with_link.py    # 이미지+링크 테스트
│   └── test_all_features.py       # 전체 기능 테스트
├── requirements.txt
└── README.md
```

## 주요 클래스

### PublishConfig

발행 설정을 담는 데이터 클래스입니다.

```python
@dataclass
class PublishConfig:
    blog_id: str                    # 네이버 블로그 ID
    cdp_url: str = "http://localhost:9222"  # CDP URL
    deepseek_api_key: str = None    # DeepSeek API 키 (선택)
    screenshot_dir: str = "data/screenshots"  # 스크린샷 저장 경로
    max_retries: int = 3            # 최대 재시도 횟수
```

### PublishResult

발행 결과를 담는 데이터 클래스입니다.

```python
@dataclass
class PublishResult:
    success: bool                   # 성공 여부
    blog_url: str = None           # 발행된 블로그 URL
    error_message: str = None      # 에러 메시지
    screenshots: List[str] = []    # 스크린샷 경로 목록
```

## 기술 스택

- **Python 3.10+**
- **Playwright**: 브라우저 자동화
- **CDP (Chrome DevTools Protocol)**: 저수준 브라우저 제어
- **aiohttp**: 비동기 HTTP 클라이언트

## 라이선스

MIT License
