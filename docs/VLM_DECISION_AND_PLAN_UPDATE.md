# VLM 모델 선정 및 플랜 수정 결정 문서

> **문서 목적**: OpenManus 스타일 AdaptivePublisher 전면 재설계 플랜의 VLM 레이어 결정사항을 기록한다.
> Claude Code가 이 문서를 읽고 기존 플랜(`~/.claude/plans/optimized-moseying-neumann.md`)의 맥락을 이어받아 구현할 수 있도록 작성되었다.
>
> **작성일**: 2026-02-05
> **상태**: Approved — 구현 진행 가능

---

## 1. 배경: 왜 VLM 모델을 재검토했는가

기존 플랜은 **DeepSeek VL2**를 VLM 백엔드로 사용하도록 설계되었다. 그러나 2026년 2월 현시점 기준 리서치 결과, 다음 문제가 확인되었다:

1. **DeepSeek 공식 API에 멀티모달 엔드포인트가 없음** — deepseek-chat, deepseek-reasoner만 지원
2. Replicate 호스팅 시 ~$5.60/월 + cold start latency 1-3초
3. 셀프호스팅 시 80GB+ VRAM 필요 (풀 모델 기준)
4. 동일 예산 내 4배 이상 저렴하고 한국어 성능이 더 우수한 대안 존재

**전체 리서치 보고서**: `docs/VLM_브라우저자동화_분석_2026.md` 참조

---

## 2. 결정사항: Qwen2.5-VL-7B 로컬 + Skyvern 스타일 경로 기억

### 2-1. VLM 모델: Qwen2.5-VL-7B (4-bit 양자화, 로컬)

**선정 이유**:

| 기준 | DeepSeek VL2 | Qwen2.5-VL-7B (4-bit) |
|------|-------------|----------------------|
| API 가용성 | ❌ 공식 API 없음 | ✅ 로컬 Ollama 서빙 |
| VRAM 요구 | 80GB+ (풀) | **4.5GB** |
| 한국어 OCR | 양호 | **우수** (29개 언어 명시 학습, CJK 강세) |
| 월 비용 | $5.60 (Replicate) | **$0** (로컬) |
| Latency | 1-3초 (네트워크) | **0.5-1초** (로컬 추론) |
| JSON 구조화 출력 | 불안정 | 안정 |

**개발 머신 사양 (배포 대상)**:

```
CPU: Intel i9
GPU: NVIDIA RTX 4070 (12GB VRAM)
RAM: 32GB
OS: Windows 11 Pro
Hostname: tlswkehd-laptop
```

**VRAM 예산**:
- Qwen2.5-VL-7B AWQ 4-bit: ~4.5GB
- KV 캐시 + 이미지 인코딩: ~2-3GB
- **총 사용량: ~7-8GB / 12GB** → 충분한 여유

**로컬 서빙 방법**:
```bash
# Ollama (가장 간단)
ollama pull qwen2.5-vl:7b

# 또는 vLLM (배치 처리 시 더 빠름)
pip install vllm
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen2.5-VL-7B-Instruct-AWQ \
  --quantization awq \
  --max-model-len 4096
```

**Fallback 전략**:
1. 1차: Qwen2.5-VL-7B 로컬 (Ollama)
2. 2차: Qwen3-VL-Flash API ($0.05/1M input tokens) — 로컬 모델 장애 시
3. 3차: 텍스트+DOM 전용 모드 — VLM 완전 불가 시

### 2-2. 비용 최적화: Skyvern 스타일 경로 기억 (Compile-to-Code)

**핵심 개념**: 매 발행마다 20-30회 VLM을 호출하는 대신, 성공한 경로를 Playwright 스크립트로 컴파일하여 이후 발행에서는 VLM 호출 없이 재생한다.

```
[1회차 — 탐색 모드]
  스크린샷 → Qwen2.5-VL-7B → 행동 결정 → 실행 → 결과 관찰
  ↓ (모든 성공 스텝을 RouteMemory에 기록)
  
[2회차~ — 재생 모드]  
  컴파일된 Playwright 스크립트 순차 실행
    ├─ 스텝 성공 → 다음 스텝
    └─ 스텝 실패 → VLM 재개입 → 새 경로 탐색 → 스크립트 업데이트
```

**왜 네이버 블로그 발행에 적합한가**:
- 발행 워크플로우의 **~95%가 고정 패턴** (글쓰기 → 제목 → 본문 → 이미지 → 태그 → 발행)
- 동적인 부분은 콘텐츠 입력(제목/본문/태그/이미지)과 예약시간 설정뿐
- 네이버 UI 변경은 수개월에 1회 수준 → 스크립트 재컴파일 빈도 극히 낮음

**실질적 VLM 호출 절감**:
- 기존 플랜: 월 ~4,000회 (200포스트 × 20호출)
- 경로 기억 적용 후: 월 **~50-100회** (초기 탐색 + 간헐적 실패 복구)

---

## 3. 플랜 파일 구조 수정사항

### 3-1. 변경되는 파일

```
src/publisher/
├── llm/
│   ├── __init__.py
│   ├── vision_client.py      # ← 변경: DeepSeekVisionLLM → OllamaVisionLLM
│   └── fallback_client.py    # ← 신규: Qwen3-VL-Flash API fallback
├── tools/
│   ├── __init__.py
│   ├── browser_tool.py       # 유지
│   ├── tool_result.py        # 유지
│   └── route_compiler.py     # ← 신규: 성공 경로 → Playwright 스크립트 컴파일
├── agent/
│   ├── __init__.py
│   ├── base_agent.py         # ← 수정: 경로 기억 로직 통합
│   ├── publish_agent.py      # ← 수정: 탐색/재생 모드 분기
│   └── prompts.py            # 유지 (프롬프트 구조 동일)
├── schema.py                 # ← 수정: RouteStep, RouteMemory 추가
├── adaptive_publisher.py     # 유지 (얇은 래퍼)
```

### 3-2. schema.py 추가 사항

기존 Message, Memory, AgentState에 더해:

```python
@dataclass
class RouteStep:
    """컴파일된 경로의 단일 스텝"""
    step_name: str                    # "click_publish_button"
    action_type: str                  # "click" | "type" | "upload" | ...
    selector: Optional[str] = None    # CSS selector (DOM 기반 매칭)
    coordinates: Optional[Tuple[int, int]] = None  # 좌표 (스크린샷 기반 매칭)
    value: Optional[str] = None       # 입력값 (type 액션)
    template_var: Optional[str] = None  # "{title}", "{body}" 등 — 동적 치환
    wait_after_ms: int = 500          # 실행 후 대기시간
    verify_condition: Optional[str] = None  # 성공 검증 조건 (JS expression)

@dataclass
class RouteMemory:
    """발행 워크플로우의 컴파일된 경로"""
    route_id: str                     # "naver_blog_publish_v1"
    steps: List[RouteStep]
    last_compiled: datetime
    success_count: int = 0            # 연속 성공 횟수
    failure_count: int = 0            # 연속 실패 횟수 (3회 초과 시 재탐색)
    naver_editor_version: Optional[str] = None  # 에디터 버전 추적

    def save(self, path: str): ...    # JSON 직렬화
    def load(cls, path: str): ...     # JSON 역직렬화
```

### 3-3. llm/vision_client.py 변경

```python
# Before (기존 플랜)
class DeepSeekVisionLLM:
    def __init__(self, api_key, model="deepseek-chat"):
        self.base_url = "https://api.deepseek.com/v1"
        ...

# After (수정안)
class OllamaVisionLLM:
    """Ollama 로컬 서버를 통한 Qwen2.5-VL-7B 호출
    
    Ollama는 OpenAI-compatible API를 제공하므로,
    기존 코드의 API 호출 구조를 최소한으로 변경.
    """
    def __init__(self, model="qwen2.5-vl:7b", base_url="http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        # Ollama의 OpenAI-compatible endpoint 사용
        self.api_url = f"{base_url}/v1/chat/completions"
    
    async def chat(self, messages: List[Message]) -> Message:
        """멀티모달 채팅 — Ollama API 호출
        
        Ollama는 base64 이미지를 직접 지원:
        {"role": "user", "content": "...", "images": ["base64..."]}
        """
        ...
    
    async def health_check(self) -> bool:
        """Ollama 서버 상태 확인"""
        ...
```

### 3-4. llm/fallback_client.py (신규)

```python
class QwenCloudVisionLLM:
    """Qwen3-VL-Flash API — 로컬 Ollama 장애 시 fallback
    
    알리바바 클라우드 DashScope API 사용.
    월 $1.40 수준으로 예산 내 충분히 감당 가능.
    """
    def __init__(self, api_key, model="qwen3-vl-flash"):
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        ...
```

### 3-5. tools/route_compiler.py (신규)

```python
class RouteCompiler:
    """성공한 에이전트 경로를 재사용 가능한 스크립트로 컴파일
    
    Skyvern의 compile-to-code 철학:
    - AI가 1회 탐색 → 성공 경로 기록
    - 경로를 RouteMemory로 직렬화
    - 이후 발행에서 RouteMemory를 재생
    - 실패 시에만 AI 재개입
    """
    
    def compile(self, agent_history: List[Dict]) -> RouteMemory:
        """에이전트의 성공 히스토리 → RouteMemory 변환
        
        동적 값(제목, 본문, 태그 등)은 template_var로 치환:
        - 실제 제목 "CCTV 가격 비교" → "{title}"
        - 실제 본문 "..." → "{body}"  
        - 실제 태그 "CCTV,보안" → "{tags}"
        """
        ...
    
    def replay(self, route: RouteMemory, variables: Dict) -> AsyncGenerator:
        """컴파일된 경로를 변수 치환하여 재생
        
        Yields: (step_name, action) tuples
        각 스텝 실행 후 verify_condition으로 성공 검증.
        검증 실패 시 StepFailure 예외 → 에이전트 재개입 트리거.
        """
        ...
```

### 3-6. agent/base_agent.py 수정

```python
class BaseAgent:
    def __init__(self, llm, browser_tool, system_prompt, 
                 route_memory: Optional[RouteMemory] = None,  # ← 추가
                 max_steps=30):
        ...
        self.route_memory = route_memory
        self.exploration_history = []  # 탐색 기록 (컴파일용)
    
    async def run(self, task: str) -> AgentState:
        """메인 에이전트 루프 — 재생/탐색 모드 분기"""
        
        if self.route_memory and self.route_memory.failure_count < 3:
            # 재생 모드: 컴파일된 경로 실행
            result = await self._replay_route(task)
            if result.status == "completed":
                self.route_memory.success_count += 1
                return result
            else:
                # 재생 실패 → 탐색 모드로 전환
                self.route_memory.failure_count += 1
                logger.warning(f"경로 재생 실패 (연속 {self.route_memory.failure_count}회)")
        
        # 탐색 모드: 기존 think → act 루프
        return await self._explore(task)
    
    async def _replay_route(self, task: str) -> AgentState:
        """컴파일된 경로 재생"""
        compiler = RouteCompiler()
        variables = self._extract_variables(task)  # {title, body, tags, ...}
        
        async for step_name, action in compiler.replay(self.route_memory, variables):
            result = await self.act(action)
            if not result.success:
                return AgentState(status="failed", error=f"Step '{step_name}' failed")
        
        return AgentState(status="completed")
    
    async def _explore(self, task: str) -> AgentState:
        """기존 think → act 탐색 루프 (exploration_history에 기록)"""
        # ... 기존 run() 로직과 동일 ...
        # 성공 시 exploration_history → RouteCompiler.compile() 호출
```

### 3-7. agent/publish_agent.py 수정

```python
class PublishAgent(BaseAgent):
    ROUTE_FILE = "data/routes/naver_publish_route.json"
    
    def __init__(self, config: PublishConfig, ...):
        # 기존 경로 파일 로드 시도
        route_memory = RouteMemory.load(self.ROUTE_FILE) if Path(self.ROUTE_FILE).exists() else None
        
        # Ollama 로컬 → Qwen Cloud fallback 체인
        llm = self._create_llm_chain(config)
        
        super().__init__(llm, browser_tool, PUBLISH_SYSTEM_PROMPT, 
                        route_memory=route_memory)
    
    def _create_llm_chain(self, config) -> VisionLLM:
        """LLM fallback 체인 구성"""
        primary = OllamaVisionLLM(model="qwen2.5-vl:7b")
        fallback = QwenCloudVisionLLM(api_key=config.qwen_api_key) if config.qwen_api_key else None
        return FallbackLLM(primary=primary, fallback=fallback)
```

---

## 4. 구현 순서 (수정된 Phase)

기존 플랜의 Phase 1-8에서 **Phase 4(VLM 클라이언트)만 교체**하고, **Phase 5.5(경로 컴파일러)를 추가**한다.

| 순서 | 파일 | 설명 | 변경 유형 |
|------|------|------|----------|
| 1 | schema.py | Message, Memory, AgentState + **RouteStep, RouteMemory** | 기존 + 추가 |
| 2 | tools/tool_result.py | ToolResult | 유지 |
| 3 | tools/browser_tool.py | CDP 액션 + 상태 캡처 | 유지 |
| **4** | **llm/vision_client.py** | **OllamaVisionLLM** (Qwen2.5-VL-7B 로컬) | **변경** |
| **4.5** | **llm/fallback_client.py** | **QwenCloudVisionLLM** (Qwen3-VL-Flash API) | **신규** |
| 5 | agent/prompts.py | 프롬프트 (네이버 에디터 특화) | 유지 |
| **5.5** | **tools/route_compiler.py** | **RouteCompiler + RouteMemory 직렬화** | **신규** |
| 6 | agent/base_agent.py | 에이전트 루프 + **재생/탐색 모드 분기** | 기존 + 추가 |
| 7 | agent/publish_agent.py | 발행 특화 + **경로 파일 로드/저장** | 기존 + 추가 |
| 8 | adaptive_publisher.py | 얇은 래퍼 | 유지 |

---

## 5. 검증 계획

```bash
# 0. Ollama 서버 구동 확인
ollama serve
ollama pull qwen2.5-vl:7b

# 1. VLM 클라이언트 단독 테스트
python -m pytest tests/test_vision_client.py -v

# 2. 탐색 모드 단일 발행 (경로 파일 없는 상태)
python scripts/daily_publish.py --limit 1 --skip-preflight
# → data/routes/naver_publish_route.json 생성 확인

# 3. 재생 모드 단일 발행 (경로 파일 있는 상태)
python scripts/daily_publish.py --limit 1 --skip-preflight
# → VLM 호출 0회 확인 (로그에서 "replay mode" 확인)

# 4. 예약발행 테스트
python scripts/daily_publish.py --limit 1 --schedule --skip-preflight

# 5. 배치 테스트
python scripts/daily_publish.py --limit 6 --schedule
```

---

## 6. 환경 변수 / 설정

```env
# .env 추가/변경 사항

# 기존 (제거)
# DEEPSEEK_API_KEY=...

# 신규
OLLAMA_BASE_URL=http://localhost:11434     # Ollama 서버 주소
OLLAMA_MODEL=qwen2.5-vl:7b                # 사용 모델
QWEN_CLOUD_API_KEY=...                     # Fallback용 (선택)
ROUTE_FILE_PATH=data/routes/naver_publish_route.json

# 유지
NAVER_COOKIE_FILE=...
SCREENSHOT_DIR=...
```

---

## 7. UI 특화 모델 관련 참고사항 (미래 고려)

현 시점에서는 Qwen2.5-VL-7B를 선택했지만, 리서치에서 발견된 **UI-TARS-7B**이 GUI 자동화에서 압도적 성능(ScreenSpot-Pro 61.6% vs GPT-4o 0.8%)을 보였다.

- 현재 선택하지 않은 이유: 8-bit 양자화 시 ~16GB VRAM → RTX 4070(12GB)에서 OOM 위험
- **향후 GPU 업그레이드(RTX 4090 24GB) 시 즉시 전환 고려**
- 전환 시 변경점: `OLLAMA_MODEL=ui-tars:7b`만 변경하면 됨 (아키텍처 동일)

---

## 8. 참고 리소스

- **전체 VLM 리서치 보고서**: `docs/VLM_브라우저자동화_분석_2026.md`
- **기존 아키텍처 플랜**: `~/.claude/plans/optimized-moseying-neumann.md`
- **Skyvern compile-to-code 참고**: https://github.com/Skyvern-AI/skyvern
- **Qwen2.5-VL 모델 카드**: https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct
- **Ollama Qwen VL 문서**: https://ollama.com/library/qwen2.5-vl
