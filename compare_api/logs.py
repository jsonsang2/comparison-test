from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlparse


def _get_first(obj: Dict[str, Any], paths: List[str]) -> Any:
    for path in paths:
        # Support dotted paths like request.url
        parts = path.split(".")
        current: Any = obj
        try:
            for part in parts:
                if current is None:
                    break
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    current = None
                    break
            if current is not None and current != {}:  # Skip empty dicts too
                return current
        except AttributeError:
            # Not a dict somewhere along the way
            continue
    return None


def _normalize_headers(headers: Optional[Dict[str, Any]]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    if not headers:
        return result
    for k, v in headers.items():
        if v is None:
            continue
        result[str(k).lower()] = ",".join(v) if isinstance(v, list) else str(v)
    return result


def _parse_url(url: str) -> Tuple[str, Dict[str, Any]]:
    parsed = urlparse(url)
    path = parsed.path or "/"
    query_items = parse_qsl(parsed.query, keep_blank_values=True)
    query: Dict[str, Any] = {}
    for k, v in query_items:
        if k in query:
            existing = query[k]
            if isinstance(existing, list):
                existing.append(v)
            else:
                query[k] = [existing, v]
        else:
            query[k] = v
    return path, query


def load_logs(path: str, fmt: str = "auto") -> List[Dict[str, Any]]:
    p = Path(path)
    data: List[Dict[str, Any]] = []
    text = p.read_text(encoding="utf-8", errors="ignore")
    effective_fmt = fmt
    if fmt == "auto":
        stripped = text.lstrip()
        if stripped.startswith("["):
            effective_fmt = "json"
        else:
            effective_fmt = "jsonl"
    def _parse_by_object_chunks(source: str) -> List[Dict[str, Any]]:
        # Split concatenated or pretty-printed objects without enclosing array
        items: List[Dict[str, Any]] = []
        s = source
        i = 0
        n = len(s)
        depth = 0
        in_string = False
        escape = False
        start_idx: Optional[int] = None
        while i < n:
            ch = s[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == '{':
                    if depth == 0:
                        start_idx = i
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        chunk = s[start_idx : i + 1]
                        try:
                            obj = json.loads(chunk)
                            if isinstance(obj, dict):
                                items.append(obj)
                        except json.JSONDecodeError:
                            pass
                        start_idx = None
            i += 1
        return items

    if effective_fmt == "json":
        try:
            items = json.loads(text) or []
        except json.JSONDecodeError:
            # Heuristic: file might be a multi-object list missing [ ]
            try:
                items = json.loads("[" + text + "]")
            except json.JSONDecodeError as e:
                # Try chunk-based parsing of objects
                objs = _parse_by_object_chunks(text)
                if objs:
                    items = objs
                else:
                    raise e
        if isinstance(items, dict):
            # Support wrapped arrays or single entry
            if isinstance(items.get("logs"), list):
                items = items.get("logs")
            elif isinstance(items.get("data"), list):
                items = items.get("data")
            else:
                items = [items]
        if not isinstance(items, list):
            raise ValueError("JSON logs must be an array, or a dict wrapping an array, or a single object")
        data = [x for x in items if isinstance(x, dict)]
    elif effective_fmt == "jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    data.append(obj)
            except json.JSONDecodeError:
                continue
        # Fallback: whole file might be a single pretty-printed JSON object/array
        if not data:
            # Fallback to whole content as JSON (object or array)
            try:
                whole = json.loads(text)
                if isinstance(whole, dict):
                    data = [whole]
                elif isinstance(whole, list):
                    data = [x for x in whole if isinstance(x, dict)]
            except json.JSONDecodeError:
                # Heuristic: multi-object list missing [ ]
                try:
                    whole_alt = json.loads("[" + text + "]")
                    if isinstance(whole_alt, list):
                        data = [x for x in whole_alt if isinstance(x, dict)]
                except json.JSONDecodeError:
                    # Finally, split by balanced object chunks
                    objs = _parse_by_object_chunks(text)
                    if objs:
                        data = objs
    else:
        raise ValueError(f"Unsupported log format: {fmt}")
    return data


def filter_dict(d: Dict[str, Any], keys_to_remove: Iterable[str]) -> Dict[str, Any]:
    remove = {k.lower() for k in keys_to_remove}
    result: Dict[str, Any] = {}
    for k, v in (d or {}).items():
        if k.lower() in remove:
            continue
        result[k] = v
    return result


def normalize_query(query: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure simple JSON-serializable values
    result: Dict[str, Any] = {}
    for k, v in (query or {}).items():
        if isinstance(v, (list, tuple)):
            result[k] = list(v)
        else:
            result[k] = v
    return result


def compute_signature(
    method: str,
    path: str,
    query: Dict[str, Any],
    body: Any,
    cfg: Dict[str, Any],
) -> str:
    strategy = cfg.get("deduplication", {}).get("strategy", "method_path_query")
    include_body_for = set(
        (cfg.get("deduplication", {}).get("include_body_for", []) or [])
    )
    key_parts: List[str] = [method.upper(), path]
    if strategy in ["method_path_query", "path_grouped"]:
        from json import dumps

        normalized_query = normalize_query(query)
        key_parts.append(dumps(normalized_query, sort_keys=True, ensure_ascii=False))
    if method.upper() in include_body_for and body is not None:
        try:
            from json import dumps

            key_parts.append(dumps(body, sort_keys=True, ensure_ascii=False))
        except Exception:
            key_parts.append(str(body))
    return "|".join(key_parts)


def extract_testcases(
    raw_logs: List[Dict[str, Any]], cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    mapping = cfg.get("log_input", {}).get("mapping", {})
    req_ign = cfg.get("request_ignores", {})
    dedup_cfg = cfg.get("deduplication", {})
    strategy = dedup_cfg.get("strategy", "method_path_query")

    if strategy == "path_grouped":
        return _extract_path_grouped_testcases(raw_logs, cfg)
    else:
        return _extract_standard_testcases(raw_logs, cfg)


def _extract_standard_testcases(
    raw_logs: List[Dict[str, Any]], cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Extract test cases using the original deduplication strategy."""
    mapping = cfg.get("log_input", {}).get("mapping", {})
    req_ign = cfg.get("request_ignores", {})
    
    seen: set[str] = set()
    cases: List[Dict[str, Any]] = []

    for entry in raw_logs:
        method = _get_first(entry, mapping.get("method", ["method"])) or "GET"
        url = _get_first(entry, mapping.get("url", ["url"]))
        path = _get_first(entry, mapping.get("path", ["path"]))
        headers = _get_first(entry, mapping.get("headers", ["headers"])) or {}
        query = _get_first(entry, mapping.get("query", ["query", "request.query", "parameter"])) or {}
        body = _get_first(entry, mapping.get("body", ["body"]))

        if url and not path:
            path_from_url, query_from_url = _parse_url(url)
            path = path_from_url
            # query merge: explicit query takes precedence
            merged_query = {**query_from_url, **(query or {})}
            query = merged_query
        if not path:
            # cannot form request target
            continue

        norm_headers = _normalize_headers(headers)
        norm_headers = filter_dict(norm_headers, req_ign.get("headers", []))

        # Filter query params
        query = normalize_query(query)
        query = filter_dict(query, req_ign.get("query_params", []))

        sig = compute_signature(method, path, query, body, cfg)
        if sig in seen:
            continue
        seen.add(sig)

        cases.append(
            {
                "method": method.upper(),
                "path": path,
                "query": query,
                "headers": norm_headers,
                "body": body,
            }
        )

    # Stable order helps deterministic runs
    cases.sort(key=lambda c: (c["method"], c["path"]))
    # Assign IDs
    for idx, c in enumerate(cases, start=1):
        c["id"] = idx
    return cases


def _extract_path_grouped_testcases(
    raw_logs: List[Dict[str, Any]], cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Extract test cases grouped by path, with detailed parameter combinations within each path."""
    mapping = cfg.get("log_input", {}).get("mapping", {})
    req_ign = cfg.get("request_ignores", {})
    
    print(f"DEBUG: Processing {len(raw_logs)} log entries")
    print(f"DEBUG: Mapping config: {mapping}")
    
    # Group by path first
    path_groups: Dict[str, List[Dict[str, Any]]] = {}
    
    for i, entry in enumerate(raw_logs):
        method = _get_first(entry, mapping.get("method", ["method"])) or "GET"
        url = _get_first(entry, mapping.get("url", ["url"]))
        path = _get_first(entry, mapping.get("path", ["path"]))
        headers = _get_first(entry, mapping.get("headers", ["headers"])) or {}
        query = _get_first(entry, mapping.get("query", ["query", "request.query", "parameter"])) or {}
        body = _get_first(entry, mapping.get("body", ["body"]))

        print(f"DEBUG: Entry {i}: method={method}, path={path}, query={query}")

        if url and not path:
            path_from_url, query_from_url = _parse_url(url)
            path = path_from_url
            # query merge: explicit query takes precedence
            merged_query = {**query_from_url, **(query or {})}
            query = merged_query
        if not path:
            # cannot form request target
            continue

        norm_headers = _normalize_headers(headers)
        norm_headers = filter_dict(norm_headers, req_ign.get("headers", []))

        # Filter query params
        query = normalize_query(query)
        query = filter_dict(query, req_ign.get("query_params", []))

        print(f"DEBUG: After filtering: query={query}")

        # Create a unique key for this specific request within the path
        request_key = compute_signature(method, path, query, body, cfg)
        
        print(f"DEBUG: Request key: {request_key}")
        
        if path not in path_groups:
            path_groups[path] = []
        
        # Check if this exact request already exists in this path group
        existing_keys = {req["request_key"] for req in path_groups[path]}
        if request_key not in existing_keys:
            path_groups[path].append({
                "method": method.upper(),
                "path": path,
                "query": query,
                "headers": norm_headers,
                "body": body,
                "request_key": request_key,
            })
            print(f"DEBUG: Added to path group {path}")
        else:
            print(f"DEBUG: Skipped duplicate request key: {request_key}")

    print(f"DEBUG: Final path groups: {list(path_groups.keys())}")
    for path, cases in path_groups.items():
        print(f"DEBUG: Path {path} has {len(cases)} cases")

    # Convert to test cases with hierarchical structure
    cases: List[Dict[str, Any]] = []
    case_id = 1
    
    for path in sorted(path_groups.keys()):
        path_cases = path_groups[path]
        
        # Create main test case for this path
        main_case = {
            "id": case_id,
            "type": "path_group",
            "method": path_cases[0]["method"],  # All should have same method for same path
            "path": path,
            "query": {},  # Empty for main case
            "headers": path_cases[0]["headers"],  # Use first case headers
            "body": None,
            "sub_cases": []
        }
        
        # Create sub-cases for each parameter combination
        for i, path_case in enumerate(path_cases):
            sub_case = {
                "id": f"{case_id}.{i+1}",
                "type": "parameter_combination",
                "method": path_case["method"],
                "path": path_case["path"],
                "query": path_case["query"],
                "headers": path_case["headers"],
                "body": path_case["body"],
                "parent_id": case_id
            }
            main_case["sub_cases"].append(sub_case)
        
        cases.append(main_case)
        case_id += 1

    return cases

