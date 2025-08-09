from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

from tqdm import tqdm

from .config import ensure_artifacts_dir, load_config
from .diffing import compare_bodies, compare_headers, compare_status
from .http_client import prepare_headers, send_request
from .logs import extract_testcases, load_logs
from .report import render_html


def _find_default_logs() -> str:
    candidates = [
        "logs/requests.jsonl",
        "logs/requests.json",
        "examples/sample_logs.jsonl",
        "examples/sample_logs.json",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    raise FileNotFoundError(
        "No logs provided and none found. Checked: " + ", ".join(candidates)
    )


def _default_testcases_path() -> str:
    return "artifacts/testcases.json"


def cmd_extract(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    logs_path = args.logs or _find_default_logs()
    logs = load_logs(logs_path, cfg.get("log_input", {}).get("format", "auto"))
    cases = extract_testcases(logs, cfg)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(cases)} testcases to {out_path}")
    return 0


def _run_case(case: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, Any]:
    targets = cfg["targets"]
    exec_cfg = cfg.get("execution", {})
    req_ign = cfg.get("request_ignores", {})
    resp_ign = cfg.get("response_ignores", {})

    left_headers = prepare_headers(case.get("headers", {}), targets["left"].get("default_headers", {}))
    right_headers = prepare_headers(case.get("headers", {}), targets["right"].get("default_headers", {}))

    left = send_request(
        base_url=targets["left"]["base_url"],
        method=case["method"],
        path=case["path"],
        query=case.get("query", {}),
        headers=left_headers,
        body=case.get("body"),
        timeout_seconds=exec_cfg.get("timeout_seconds", 30),
        verify_tls=exec_cfg.get("verify_tls", True),
    )

    right = send_request(
        base_url=targets["right"]["base_url"],
        method=case["method"],
        path=case["path"],
        query=case.get("query", {}),
        headers=right_headers,
        body=case.get("body"),
        timeout_seconds=exec_cfg.get("timeout_seconds", 30),
        verify_tls=exec_cfg.get("verify_tls", True),
    )

    status_cmp = compare_status(left["status"], right["status"])
    headers_cmp = compare_headers(left["headers"], right["headers"], resp_ign.get("headers", []))

    left_body = left.get("body_json") if left.get("body_json") is not None else left.get("body_text")
    right_body = right.get("body_json") if right.get("body_json") is not None else right.get("body_text")
    bodies_cmp = compare_bodies(left_body, right_body, resp_ign.get("body_json_paths", []))

    equal = status_cmp["equal"] and headers_cmp["equal"] and bodies_cmp["equal"]

    return {
        "id": case["id"],
        "request": {
            "method": case["method"],
            "path": case["path"],
            "query": case.get("query", {}),
            "headers": case.get("headers", {}),
            "body": case.get("body"),
        },
        "left": {**left, "target": targets["left"]["name"]},
        "right": {**right, "target": targets["right"]["name"]},
        "compare": {
            "status": status_cmp,
            "headers": headers_cmp,
            "bodies": bodies_cmp,
            "equal": equal,
        },
    }


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    artifacts = ensure_artifacts_dir(args.artifacts)

    # Optional refresh from logs each run
    if getattr(args, "refresh_from_logs", False) or (args.testcases is None and args.logs is not None):
        logs_path = args.logs or _find_default_logs()
        logs = load_logs(logs_path, cfg.get("log_input", {}).get("format", "auto"))
        cases = extract_testcases(logs, cfg)
        if args.max and args.max > 0:
            cases = cases[: args.max]
        tmp_cases = artifacts / "testcases.json"
        tmp_cases.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        cases_path_str = args.testcases or _default_testcases_path()
        cases_path = Path(cases_path_str)
        if not cases_path.exists():
            raise FileNotFoundError(
                f"Testcases file not found: {cases_path}. Use --refresh-from-logs or run 'compare-api extract' first."
            )
        cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if args.max and args.max > 0:
        cases = cases[: args.max]

    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=cfg.get("execution", {}).get("concurrency", 8)) as ex:
        futures = {ex.submit(_run_case, c, cfg): c for c in cases}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="Running"):
            try:
                results.append(fut.result())
            except Exception as e:
                c = futures[fut]
                results.append({
                    "id": c["id"],
                    "error": str(e),
                    "request": c,
                    "compare": {"equal": False},
                })

    results.sort(key=lambda r: r["id"])  # restore order
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.get("compare", {}).get("equal")),
        "failed": sum(1 for r in results if not r.get("compare", {}).get("equal")),
    }
    targets_info = {
        "left": {
            "name": cfg["targets"]["left"].get("name", "left"),
            "base_url": cfg["targets"]["left"].get("base_url", "")
        },
        "right": {
            "name": cfg["targets"]["right"].get("name", "right"),
            "base_url": cfg["targets"]["right"].get("base_url", "")
        },
    }

    # Write machine-readable results
    results_json_path = artifacts / "results.json"
    json_payload = {"summary": summary, "results": results, "targets": targets_info}
    results_json_path.write_text(json.dumps(json_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # Render HTML
    html_path = artifacts / "report.html"
    render_html({"summary": summary, "results": results, "targets": targets_info}, html_path)

    print(f"Report: {html_path}")
    print(f"JSON:   {results_json_path}")
    print(f"Passed: {summary['passed']} / {summary['total']}")
    return 0


def cmd_from_logs(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    artifacts = ensure_artifacts_dir(args.artifacts)
    logs_path = args.logs or _find_default_logs()
    logs = load_logs(logs_path, cfg.get("log_input", {}).get("format", "auto"))
    cases = extract_testcases(logs, cfg)
    if args.max and args.max > 0:
        cases = cases[: args.max]

    tmp_cases = artifacts / "testcases.json"
    tmp_cases.write_text(json.dumps(cases, ensure_ascii=False, indent=2), encoding="utf-8")
    # Reuse run flow
    class TmpArgs:
        testcases = str(tmp_cases)
        config = args.config
        artifacts = args.artifacts
        max = None

    return cmd_run(TmpArgs())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="compare-api", description="Compare API responses across two endpoints from log-derived testcases")
    sub = p.add_subparsers(dest="command", required=True)

    p_extract = sub.add_parser("extract", help="Extract unique request patterns from logs")
    p_extract.add_argument("--logs", required=False, default=None, help="Path to JSON/JSONL logs (defaults to logs/requests.json[l] or examples)")
    p_extract.add_argument("--config", required=False, default=None, help="Path to config.yml (defaults: config.yml/config.yaml/examples/config.yml)")
    p_extract.add_argument("--out", required=False, default="artifacts/testcases.json", help="Where to write extracted testcases")
    p_extract.set_defaults(func=cmd_extract)

    p_run = sub.add_parser("run", help="Run testcases against two targets and generate a report")
    p_run.add_argument("--testcases", required=False, default=None, help="Path to extracted testcases JSON (default: artifacts/testcases.json)")
    p_run.add_argument("--refresh-from-logs", action="store_true", help="Re-extract testcases from logs before running")
    p_run.add_argument("--logs", required=False, default=None, help="Path to JSON/JSONL logs when using --refresh-from-logs (defaults to logs/requests.json[l] or examples)")
    p_run.add_argument("--config", required=False, default=None, help="Path to config.yml (defaults: config.yml/config.yaml/examples/config.yml)")
    p_run.add_argument("--artifacts", required=False, default="artifacts", help="Artifacts output directory")
    p_run.add_argument("--max", type=int, required=False, default=None, help="Run only first N cases")
    p_run.set_defaults(func=cmd_run)

    p_all = sub.add_parser("from-logs", help="Extract and run in one step")
    p_all.add_argument("--logs", required=False, default=None, help="Path to JSON/JSONL logs (defaults to logs/requests.json[l] or examples)")
    p_all.add_argument("--config", required=False, default=None, help="Path to config.yml (defaults: config.yml/config.yaml/examples/config.yml)")
    p_all.add_argument("--artifacts", required=False, default="artifacts", help="Artifacts output directory")
    p_all.add_argument("--max", type=int, required=False, default=None, help="Run only first N cases")
    p_all.set_defaults(func=cmd_from_logs)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

