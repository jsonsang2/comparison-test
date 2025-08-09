from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import requests


def _join_url(base_url: str, path: str) -> str:
    if base_url.endswith("/") and path.startswith("/"):
        return base_url[:-1] + path
    if not base_url.endswith("/") and not path.startswith("/"):
        return base_url + "/" + path
    return base_url + path


HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
    "content-length",
    "host",
}


def prepare_headers(base_headers: Dict[str, str], overrides: Dict[str, str]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for k, v in (base_headers or {}).items():
        lk = k.lower()
        if lk in HOP_BY_HOP:
            continue
        result[lk] = v
    for k, v in (overrides or {}).items():
        result[k.lower()] = v
    return result


def send_request(
    *,
    base_url: str,
    method: str,
    path: str,
    query: Dict[str, Any],
    headers: Dict[str, str],
    body: Any,
    timeout_seconds: int,
    verify_tls: bool,
) -> Dict[str, Any]:
    url = _join_url(base_url, path)
    params = []
    for k, v in (query or {}).items():
        if isinstance(v, list):
            for item in v:
                params.append((k, item))
        else:
            params.append((k, v))

    data = None
    json_body = None
    if body is None:
        pass
    elif isinstance(body, (dict, list)):
        json_body = body
    elif isinstance(body, (str, bytes)):
        data = body
    else:
        # best-effort: string cast
        data = str(body)

    session = requests.Session()
    start = time.perf_counter()
    resp = session.request(
        method=method.upper(),
        url=url,
        params=params,
        headers=headers,
        data=data,
        json=json_body,
        timeout=timeout_seconds,
        verify=verify_tls,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    # Normalize headers to lower-case keys, join multi-values
    norm_headers: Dict[str, str] = {}
    for k, v in resp.headers.items():
        norm_headers[k.lower()] = v if isinstance(v, str) else ",".join(v)

    text: Optional[str] = None
    body_json: Optional[Any] = None
    content_type = norm_headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_json = resp.json()
        except Exception:
            text = resp.text
    else:
        text = resp.text

    return {
        "status": resp.status_code,
        "headers": norm_headers,
        "elapsed_ms": elapsed_ms,
        "body_text": text,
        "body_json": body_json,
    }

