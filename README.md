# API Comparison Test

JSON/JSONL 로그에서 API 요청 패턴을 추출하여 두 개의 다른 엔드포인트로 재생하고, 응답 차이를 HTML 리포트로 비교하는 시스템입니다.

## 주요 기능

### 🔍 로그 분석 및 패턴 추출
- **다양한 로그 형식 지원**: JSON Lines, JSON 배열, 들여쓰기된 다중 JSON
- **유연한 매핑**: `request.path`, `request.parameter`, `request.headers` 등 중첩된 구조 지원
- **MIME Type 자동 추출**: 로그에서 `http.request.mime_type` 값을 자동으로 Content-Type 헤더로 설정
- **요청 Body 정규화**: 공백 정리 및 원본 내용 보존 (XML, JSON 등)
- **중복 제거 전략**: 
  - `method_path_query`: 전통적인 방식 (메서드+경로+쿼리 기준)
  - `path_grouped`: **새로운 기능** - 경로별 그룹화 및 파라미터 조합별 서브 케이스

### 🧪 테스트 실행
- **이중 엔드포인트 테스트**: 기존(old) vs 새로운(new) 엔드포인트 동시 호출
- **동시성 실행**: 설정 가능한 동시 실행 수
- **타임아웃 및 재시도**: 안정적인 테스트 실행

### 📊 응답 비교
- **상세 비교**: HTTP 상태 코드, 헤더, 응답 본문
- **XML 정규화**: XML 응답의 인덴트, 속성 순서, 공백 차이를 정규화하여 기능적 차이만 비교
- **무시 규칙**: 특정 헤더, 쿼리 파라미터, JSON 경로 제외 가능
- **Diff 시각화**: HTML 리포트에서 필드별 차이점 명확하게 표시

### 📈 리포트 생성
- **HTML 리포트**: 브라우저에서 보기 편한 형태
- **개선된 레이아웃**: 좌우 비교를 위한 그리드 레이아웃, XML/JSON 태그 정확한 렌더링
- **XML 예쁜 출력**: XML 응답을 자동으로 인덴트 적용하여 읽기 쉽게 포맷팅
- **계층적 구조**: Path Group과 Sub-case를 포함한 테스트 결과
- **요청/응답 상세 보기**: 각 테스트별 파라미터, 헤더, 본문 내용 표시
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
    "http": {
      "request": {
        "method": "POST",
        "mime_type": "application/xml",
        "body": {
          "content": "<request><param1>B</param1><param2>A</param2></request>"
        }
      }
    },
    "url": {
      "domain": "https://api.example.com",
      "path": "/a/b/cd",
      "query": {
        "param1": "B",
        "param2": "A"
      }
    },
    "headers": {
      "x-app-id": "abcdef"
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
  format: json  # auto, json, jsonl
  mapping:
    method: [http.request.method, method]
    url: [url.domain, url, request.url]
    path: [url.path, path, request.path]
    headers: [headers, request.headers]
    query: [url.query, query, request.query, request.parameter]  # 파라미터 추출
    body: [http.request.body.content, request.body, body, payload]
    mime_type: [http.request.mime_type, http.request.content_type, request.mime_type, request.content_type]  # MIME type 추출
```

**주요 매핑 경로**:
- `http.request.mime_type`: HTTP 요청의 MIME type (자동으로 Content-Type 헤더로 설정)
- `url.domain`, `url.path`, `url.query`: URL 구성 요소별 분리 추출
- `http.request.body.content`: HTTP 요청 본문 내용

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
  - **좌우 비교 레이아웃**: Left/Right 응답을 나란히 표시
  - **XML/JSON 태그 정확한 렌더링**: HTML 엔티티 인코딩으로 태그가 브라우저에서 올바르게 표시
  - **XML 자동 포맷팅**: XML 응답을 인덴트가 적용된 읽기 쉬운 형태로 표시
  - **XML 정규화 비교**: 포맷 차이는 무시하고 기능적 차이만 표시

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

### XML API 비교 예시
XML 응답을 반환하는 API의 경우, 다음과 같은 이점이 있습니다:

```xml
<!-- Left API 응답 -->
<response><status>success</status><data id="1" name="test">
<item>value</item></data></response>

<!-- Right API 응답 (포맷팅 차이만 있음) -->
<response>
  <status>success</status>
  <data name="test" id="1">
    <item>value</item>
  </data>
</response>
```

- **정규화**: 위 두 XML은 포맷은 다르지만 기능적으로 동일하므로 "동일" 판정
- **예쁜 출력**: 리포트에서 인덴트가 적용된 읽기 쉬운 형태로 표시
- **속성 순서**: XML 속성 순서 차이는 무시됨

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
- [x] MIME type 자동 추출 및 Content-Type 헤더 설정
- [x] 요청 Body 정규화 (공백 처리, 원본 내용 보존)
- [x] HTML 리포트 UI 개선 (좌우 비교, XML 태그 렌더링)
- [x] XML 응답 정규화 (인덴트, 속성 순서, 공백 차이 무시)
- [x] XML 응답 예쁜 출력 (HTML 리포트에서 포맷팅)
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
