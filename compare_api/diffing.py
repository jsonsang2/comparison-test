from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Tuple

from deepdiff import DeepDiff


def normalize_headers(h: Dict[str, str], ignore: List[str]) -> Dict[str, str]:
    ignore_set = {k.lower() for k in (ignore or [])}
    result: Dict[str, str] = {}
    for k, v in (h or {}).items():
        lk = k.lower()
        if lk in ignore_set:
            continue
        result[lk] = v
    return result


def compare_headers(
    left: Dict[str, str], right: Dict[str, str], ignore: List[str]
) -> Dict[str, Any]:
    l = normalize_headers(left, ignore)
    r = normalize_headers(right, ignore)
    keys = set(l) | set(r)
    diffs: List[Dict[str, Any]] = []
    for k in sorted(keys):
        lv = l.get(k)
        rv = r.get(k)
        if lv != rv:
            diffs.append({"key": k, "left": lv, "right": rv})
    return {
        "equal": len(diffs) == 0,
        "diffs": diffs,
        "left": l,
        "right": r,
    }


def compare_status(left: int, right: int) -> Dict[str, Any]:
    return {"equal": left == right, "left": left, "right": right}


def compare_bodies(
    left: Dict[str, Any] | str | None,
    right: Dict[str, Any] | str | None,
    ignore_paths: List[str],
) -> Dict[str, Any]:
    # Three modes:
    # - Both JSON-like (dict/list)
    # - Otherwise compare string forms
    if isinstance(left, (dict, list)) and isinstance(right, (dict, list)):
        # Deep copy to avoid mutating originals
        l = copy.deepcopy(left)
        r = copy.deepcopy(right)
        diff = DeepDiff(
            l,
            r,
            exclude_paths=set(ignore_paths or []),
            ignore_order=True,
            view="tree",
        )
        equal = not bool(diff)
        return {
            "mode": "json",
            "equal": equal,
            "diff": json.loads(diff.to_json()) if diff else {},
            "left_pretty": json.dumps(l, indent=2, ensure_ascii=False, sort_keys=True),
            "right_pretty": json.dumps(r, indent=2, ensure_ascii=False, sort_keys=True),
        }
    else:
        # fallback to text
        ls = "" if left is None else (left if isinstance(left, str) else json.dumps(left))
        rs = "" if right is None else (right if isinstance(right, str) else json.dumps(right))
        equal = ls == rs
        return {
            "mode": "text",
            "equal": equal,
            "left_text": ls,
            "right_text": rs,
        }

