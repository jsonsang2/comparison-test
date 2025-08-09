# comparison-test

JSON/JSONL 로그에서 요청 패턴을 추출해 양쪽 엔드포인트로 재생하고, 응답 차이를 HTML 리포트로 비교합니다.

## Features
- JSON Lines, JSON 배열, 들여쓰기된 다중 JSON 지원
- 메서드/경로/쿼리 기준 중복 제거(설정 가능), 바디 포함 조건 설정 가능
- 요청/응답 무시 규칙: 헤더, 쿼리 파라미터, 응답 바디 JSON 경로
- 좌/우 엔드포인트 동시 호출 및 비교, 동시성 실행
- HTML 리포트: 요약/타깃 정보/필드별 diff

## Quickstart
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# logs/requests.jsonl 또는 logs/requests.json에 로그를 두고
# endpoints는 examples/config.yml의 targets.*.base_url을 수정

# 한 번에: 추출 + 실행 + 리포트
python -m compare_api.cli from-logs

# 분리 실행
python -m compare_api.cli extract
python -m compare_api.cli run

# 매 실행시 재추출
python -m compare_api.cli run --refresh-from-logs
```

## Configuration
`examples/config.yml` 참고
- `targets.left/right.base_url`, `default_headers`
- `request_ignores`, `response_ignores`
- `log_input.mapping` (예: `request.endpoint`, `request.path`, `request.parameter`, `request.headers`, `request.body`)

## Output
- HTML: `artifacts/report.html`
- JSON: `artifacts/results.json`

## Roadmap
- Pattern 분석 최적화
- 경로/쿼리 가변성 제어(정규식/마스킹)
- 샘플링/가중치 기반 케이스 선택
