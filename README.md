# API Comparison Test

JSON/JSONL 로그에서 API 요청 패턴을 추출하여 두 개의 다른 엔드포인트로 재생하고, 응답 차이를 HTML 리포트로 비교하는 시스템입니다.

## 주요 기능

### 🔍 로그 분석 및 패턴 추출
- **다양한 로그 형식 지원**: JSON Lines, JSON 배열, 들여쓰기된 다중 JSON
- **유연한 매핑**: `request.path`, `request.parameter`, `request.headers` 등 중첩된 구조 지원
- **중복 제거 전략**: 
  - `method_path_query`: 전통적인 방식 (메서드+경로+쿼리 기준)
  - `path_grouped`: **새로운 기능** - 경로별 그룹화 및 파라미터 조합별 서브 케이스

### 🧪 테스트 실행
- **이중 엔드포인트 테스트**: 기존(old) vs 새로운(new) 엔드포인트 동시 호출
- **동시성 실행**: 설정 가능한 동시 실행 수
- **타임아웃 및 재시도**: 안정적인 테스트 실행

### 📊 응답 비교
- **상세 비교**: HTTP 상태 코드, 헤더, 응답 본문
- **무시 규칙**: 특정 헤더, 쿼리 파라미터, JSON 경로 제외 가능
- **Diff 시각화**: HTML 리포트에서 필드별 차이점 명확하게 표시

### 📈 리포트 생성
- **HTML 리포트**: 브라우저에서 보기 편한 형태
- **계층적 구조**: Path Group과 Sub-case를 포함한 테스트 결과
- **JSON 결과**: 프로그래밍 방식으로 결과 처리 가능

## 빠른 시작

### 1. 환경 설정
```bash
# 가상환경 생성 및 활성화
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt
```

### 2. 로그 파일 준비
`logs/requests.jsonl` 파일에 API 호출 로그를 넣어주세요:

```json
[
  {
    "method": "GET",
    "request": {
      "endpoint": "https://api.example.com",
      "path": "/a/b/cd",
      "parameter": {
        "param1": "B",
        "param2": "A"
      },
      "headers": {
        "Content-Type": "application/json",
        "x-app-id": "abcdef"
      }
    },
    "response": { ... }
  }
]
```

### 3. 설정 파일 수정
`examples/config.yml`에서 엔드포인트 정보를 수정하세요:

```yaml
targets:
  left:
    name: old
    base_url: https://your-old-api.com
  right:
    name: new
    base_url: https://your-new-api.com
```

### 4. 테스트 실행

#### 한 번에 실행 (추출 + 실행 + 리포트)
```bash
python -m compare_api.cli from-logs
```

#### 단계별 실행
```bash
# 1단계: 로그에서 테스트 케이스 추출
python -m compare_api.cli extract

# 2단계: 테스트 실행
python -m compare_api.cli run

# 3단계: 매번 로그에서 재추출하며 실행
python -m compare_api.cli run --refresh-from-logs
```

## 설정 가이드

### 로그 매핑 설정
`examples/config.yml`의 `log_input.mapping` 섹션:

```yaml
log_input:
  mapping:
    method: [method, http_method]
    url: [url, request.url, uri]
    path: [path, request.path]
    headers: [headers, request.headers]
    query: [query, request.query, request.parameter]  # 파라미터 추출
    body: [body, request.body, payload]
```

### 중복 제거 전략
```yaml
deduplication:
  strategy: path_grouped  # path_grouped 또는 method_path_query
  include_body_for: [POST, PUT, PATCH]
  query_param_order_insensitive: true
```

#### path_grouped 전략 (권장)
- **Path별 그룹화**: 각 고유한 경로에 대해 하나의 메인 테스트 케이스
- **서브 케이스**: 동일한 경로 내에서 다른 파라미터 조합을 별도 테스트
- **계층적 구조**: 메인 케이스와 서브 케이스로 구성

#### method_path_query 전략
- **전통적인 방식**: 메서드+경로+쿼리 조합으로 고유한 테스트 케이스 생성

### 무시 규칙 설정
```yaml
request_ignores:
  headers: [authorization, user-agent, content-length]
  query_params: [timestamp, nonce, _]
  body_json_paths: []

response_ignores:
  headers: [date, server, set-cookie]
  body_json_paths: []
```

## 출력 파일

### HTML 리포트
- **위치**: `artifacts/report.html`
- **내용**: 
  - 테스트 요약 (통과/실패 수)
  - 각 Path Group별 결과
  - Sub-case별 상세 비교
  - 필드별 diff 시각화

### JSON 결과
- **위치**: `artifacts/results.json`
- **내용**: 
  - 구조화된 테스트 결과
  - 프로그래밍 방식으로 결과 처리 가능
  - API 연동 시 활용

## 사용 예시

### 기본 사용법
```bash
# 로그 파일에서 테스트 케이스 추출
python -m compare_api.cli extract --config examples/config.yml --logs logs/requests.jsonl

# 추출된 테스트 케이스로 테스트 실행
python -m compare_api.cli run --config examples/config.yml

# 브라우저에서 리포트 확인
open artifacts/report.html
```

### 고급 사용법
```bash
# 매번 로그에서 재추출하며 실행
python -m compare_api.cli run --refresh-from-logs

# 특정 설정 파일 사용
python -m compare_api.cli from-logs --config my-config.yml

# 커스텀 로그 파일 사용
python -m compare_api.cli from-logs --logs my-logs.jsonl
```

## 아키텍처

```
compare_api/
├── __init__.py          # 패키지 초기화
├── cli.py              # 명령행 인터페이스
├── config.py            # 설정 파일 로딩
├── logs.py              # 로그 파싱 및 테스트 케이스 추출
├── http_client.py       # HTTP 요청 처리
├── diffing.py           # 응답 비교 및 diff 생성
├── report.py            # HTML 리포트 생성
└── templates/           # Jinja2 템플릿
    └── report.html.j2   # HTML 리포트 템플릿
```

## 로드맵

- [x] Path Grouped 전략 구현
- [x] 계층적 테스트 케이스 구조
- [x] 파라미터 조합별 서브 케이스
- [ ] 정규식 기반 경로/쿼리 가변성 제어
- [ ] 샘플링/가중치 기반 케이스 선택
- [ ] 성능 최적화
- [ ] 더 많은 로그 형식 지원

## 기여하기

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.
