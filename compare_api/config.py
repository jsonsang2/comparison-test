from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


DEFAULT_CONFIG: Dict[str, Any] = {
    "targets": {
        "left": {
            "name": "left",
            "base_url": "http://localhost:8080",
            "default_headers": {},
        },
        "right": {
            "name": "right",
            "base_url": "http://localhost:8081",
            "default_headers": {},
        },
    },
    "request_ignores": {
        "headers": [
            "authorization",
            "user-agent",
            "accept-encoding",
            "content-length",
            "host",
            "connection",
            "x-request-id",
        ],
        "query_params": [
            "timestamp",
            "nonce",
            "_",
        ],
        # DeepDiff style, e.g. root['meta']['traceId']
        "body_json_paths": [],
    },
    "response_ignores": {
        "headers": [
            "date",
            "server",
            "x-request-id",
            "cf-ray",
            "set-cookie",
        ],
        # DeepDiff style, e.g. root['meta']['generatedAt']
        "body_json_paths": [],
    },
    "deduplication": {
        "strategy": "method_path_query",  # or method_path_only
        "include_body_for": ["POST", "PUT", "PATCH"],
        "query_param_order_insensitive": True,
    },
    "log_input": {
        "format": "auto",  # jsonl | json | auto
        "mapping": {
            "method": ["method", "http_method"],
            "url": ["url", "request.url", "uri", "request.endpoint"],
            "path": ["path", "request.path"],
            "headers": ["headers", "request.headers"],
            "query": ["query", "request.query", "request.parameter"],
            "body": ["body", "request.body", "payload"],
        },
    },
    "execution": {
        "concurrency": 8,
        "timeout_seconds": 30,
        "verify_tls": True,
        "retries": 1,
        "backoff_seconds": 0.2,
    },
}


def deep_merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in (override or {}).items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(value, dict)
        ):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if path is None:
        # Try common defaults
        for candidate in ["config.yml", "config.yaml", "examples/config.yml"]:
            if Path(candidate).exists():
                path = candidate
                break
    if path is None:
        return copy.deepcopy(DEFAULT_CONFIG)

    with open(path, "r", encoding="utf-8") as f:
        user_cfg = yaml.safe_load(f) or {}
    return deep_merge_dicts(DEFAULT_CONFIG, user_cfg)


def ensure_artifacts_dir(artifacts_dir: str | Path) -> Path:
    path = Path(artifacts_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path

