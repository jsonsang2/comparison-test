from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .diffing import is_xml_content, pretty_format_xml


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def format_xml_if_applicable(content: str) -> str:
    """Jinja2 filter to format XML content if it's XML, otherwise return as-is."""
    if isinstance(content, str) and is_xml_content(content):
        return pretty_format_xml(content)
    return content


def render_html(results: Dict[str, Any], out_path: str | Path) -> Path:
    env = Environment(
        loader=FileSystemLoader(str(_templates_dir())),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    
    # Add custom filter for XML formatting
    env.filters['format_xml'] = format_xml_if_applicable
    
    template = env.get_template("report.html.j2")
    html = template.render(**results)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out

