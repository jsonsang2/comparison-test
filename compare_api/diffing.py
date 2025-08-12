from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple

from deepdiff import DeepDiff


def normalize_xml(xml_string: str) -> str:
    """
    Normalize XML string by parsing and reformatting with consistent structure.
    This helps compare XML responses that are functionally identical but formatted differently.
    """
    try:
        # Remove leading/trailing whitespace
        xml_string = xml_string.strip()
        if not xml_string:
            return xml_string
            
        # Parse XML
        root = ET.fromstring(xml_string)
        
        # Sort attributes for consistent ordering
        def sort_attributes_and_normalize(elem):
            # Sort attributes by key for consistent ordering
            if elem.attrib:
                sorted_attribs = sorted(elem.attrib.items())
                elem.attrib.clear()
                elem.attrib.update(sorted_attribs)
            
            # Process children recursively
            for child in elem:
                sort_attributes_and_normalize(child)
            
            # Normalize text content (strip whitespace but preserve content)
            if elem.text:
                elem.text = elem.text.strip() or None
            if elem.tail:
                elem.tail = elem.tail.strip() or None
        
        sort_attributes_and_normalize(root)
        
        # Convert back to string
        xml_str = ET.tostring(root, encoding='unicode', method='xml')
        
        # Remove XML declaration if present and normalize
        if xml_str.startswith('<?xml'):
            xml_str = xml_str.split('?>', 1)[1]
        
        return xml_str.strip()
        
    except ET.ParseError:
        # If it's not valid XML, return as-is
        return xml_string
    except Exception:
        # For any other errors, return as-is
        return xml_string


def pretty_format_xml(xml_string: str) -> str:
    """
    Format XML string with proper indentation for display purposes.
    This makes XML more readable in the HTML report.
    """
    try:
        import xml.dom.minidom
        
        # Remove leading/trailing whitespace
        xml_string = xml_string.strip()
        if not xml_string:
            return xml_string
            
        # Parse and pretty print
        dom = xml.dom.minidom.parseString(xml_string)
        pretty_xml = dom.toprettyxml(indent="  ", encoding=None)
        
        # Remove empty lines and the XML declaration if we don't want it
        lines = [line for line in pretty_xml.split('\n') if line.strip()]
        
        # Remove XML declaration line if it exists
        if lines and lines[0].startswith('<?xml'):
            lines = lines[1:]
            
        return '\n'.join(lines)
        
    except Exception:
        # If parsing fails, return original
        return xml_string


def is_xml_content(content: str) -> bool:
    """Check if content appears to be XML based on basic patterns."""
    if not isinstance(content, str):
        return False
    content = content.strip()
    return content.startswith('<') and content.endswith('>')


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
    # Four modes:
    # - Both JSON-like (dict/list)
    # - Both XML-like strings
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
        # Convert to string representation
        ls = "" if left is None else (left if isinstance(left, str) else json.dumps(left))
        rs = "" if right is None else (right if isinstance(right, str) else json.dumps(right))
        
        # Check if both look like XML and normalize them for comparison
        if is_xml_content(ls) and is_xml_content(rs):
            # Normalize XML for comparison
            ls_normalized = normalize_xml(ls)
            rs_normalized = normalize_xml(rs)
            equal = ls_normalized == rs_normalized
            
            return {
                "mode": "xml",
                "equal": equal,
                "left_text": ls,  # Keep original for display
                "right_text": rs,  # Keep original for display
                "left_normalized": ls_normalized,  # For debugging if needed
                "right_normalized": rs_normalized,  # For debugging if needed
            }
        else:
            # fallback to text comparison
            equal = ls == rs
            return {
                "mode": "text",
                "equal": equal,
                "left_text": ls,
                "right_text": rs,
            }

