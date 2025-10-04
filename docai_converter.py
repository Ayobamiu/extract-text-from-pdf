#!/usr/bin/env python3
"""
Document AI to Markdown Converter
Extracted from docai_to_markdown-3.py for integration with Flask API
"""

import math
import re
from typing import Any, Dict, List, Tuple


def _get(d: Dict[str, Any], *keys, default=None):
    for k in keys:
        if isinstance(d, dict) and k in d:
            return d[k]
    return default


def _doc_obj(obj: Dict[str, Any]) -> Dict[str, Any]:
    # JSON can be either top-level Document or {"document": Document}
    return obj["document"] if isinstance(obj, dict) and "document" in obj else obj


def _segments(anchor: Dict[str, Any]) -> List[Tuple[int, int]]:
    if not anchor:
        return []
    segs = _get(anchor, "textSegments", "text_segments", default=[]) or []
    out = []
    for s in segs:
        a = _get(s, "startIndex", "start_index", default=0) or 0
        b = _get(s, "endIndex", "end_index", default=None)
        if b is None:
            continue
        out.append((int(a), int(b)))
    return out


def _layout_segments(layout: Dict[str, Any]) -> List[Tuple[int, int]]:
    if not layout:
        return []
    return _segments(_get(layout, "textAnchor", "text_anchor", default=None))


def _merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []
    intervals = sorted(intervals)
    merged = [intervals[0]]
    for s, e in intervals[1:]:
        ls, le = merged[-1]
        if s <= le:
            merged[-1] = (ls, max(le, e))
        else:
            merged.append((s, e))
    return merged


def _union_segments(
    a: List[Tuple[int, int]], b: List[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    return _merge_intervals((a or []) + (b or []))


def _subtract_intervals(
    include: List[Tuple[int, int]], exclude: List[Tuple[int, int]]
) -> List[Tuple[int, int]]:
    if not include:
        return []
    if not exclude:
        return include[:]
    exc = _merge_intervals(exclude)
    out = []
    for s, e in include:
        cur = s
        for xs, xe in exc:
            if xe <= cur:  # exclusion before cur
                continue
            if xs >= e:  # exclusion after this include
                break
            if xs > cur:  # keep left piece
                out.append((cur, xs))
            cur = max(cur, xe)  # jump right
            if cur >= e:
                break
        if cur < e:
            out.append((cur, e))
    return out


def _text_from_segments(full_text: str, segs: List[Tuple[int, int]]) -> str:
    parts = []
    for s, e in segs:
        s = max(0, min(len(full_text), s))
        e = max(0, min(len(full_text), e))
        parts.append(full_text[s:e])
    return "".join(parts)


def _norm_vertices(poly: Dict[str, Any]) -> List[Tuple[float, float]]:
    if not poly:
        return []
    vs = _get(poly, "normalizedVertices", "normalized_vertices", default=None)
    if vs:
        return [(float(v.get("x", 0.0)), float(v.get("y", 0.0))) for v in vs]
    vs2 = _get(poly, "vertices", default=None)
    if vs2:
        xs = [v.get("x", 0) for v in vs2 if "x" in v]
        ys = [v.get("y", 0) for v in vs2 if "y" in v]
        W = max(xs) if xs else 1.0
        H = max(ys) if ys else 1.0
        return [(float(v.get("x", 0)) / W, float(v.get("y", 0)) / H) for v in vs2]
    return []


def _bbox_from_layout(layout: Dict[str, Any]) -> Tuple[float, float, float, float]:
    poly = _get(layout, "boundingPoly", "bounding_poly", default=None)
    pts = _norm_vertices(poly)
    if not pts:
        return (math.inf, math.inf, -math.inf, -math.inf)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))  # (x1,y1,x2,y2)


def _center_x(box):
    return (box[0] + box[2]) / 2.0


def _escape_md(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\r", " ").strip()


def _cleanup_text(s: str) -> str:
    if not s:
        return ""
    # Normalize whitespace, keep line breaks
    s = s.replace("\r", "")
    # Join hyphenation line-breaks: "exam-\nple" -> "example"
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)
    # Collapse excessive blank lines
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _is_heading_like(line: str) -> bool:
    if not line:
        return False
    if len(line) < 3 or len(line) > 80:
        return False
    if line.endswith("."):
        return False
    letters = re.sub(r"[^A-Za-z]", "", line)
    if not letters:
        return False
    upper_ratio = sum(1 for ch in letters if ch.isupper()) / max(1, len(letters))
    if upper_ratio >= 0.85:
        return True
    # Title Case & short
    if line.istitle() and len(line.split()) <= 8:
        return True
    return False


def _table_to_renderable(table: Dict[str, Any], full_text: str):
    header_rows = _get(table, "headerRows", "header_rows", default=[]) or []
    body_rows = _get(table, "bodyRows", "body_rows", default=[]) or []
    any_span = False
    rows = []
    all_spans = []
    bbox = (math.inf, math.inf, -math.inf, -math.inf)

    def cell_info(c):
        layout = _get(c, "layout", default=c)
        segs = _layout_segments(layout)
        txt = _escape_md(_text_from_segments(full_text, segs))
        rspan = int(_get(c, "rowSpan", "row_span", default=1) or 1)
        cspan = int(_get(c, "colSpan", "col_span", default=1) or 1)
        box = _bbox_from_layout(layout)
        return txt, rspan, cspan, segs, box

    # collect rows
    for r in header_rows + body_rows:
        r_cells = []
        for c in _get(r, "cells", "cells", default=[]) or []:
            txt, rspan, cspan, segs, box = cell_info(c)
            if rspan > 1 or cspan > 1:
                any_span = True
            r_cells.append({"text": txt, "rowSpan": rspan, "colSpan": cspan})
            all_spans = _union_segments(all_spans, segs)
            bbox = _merge_bbox(bbox, box)
        rows.append(r_cells)

    # normalize widths for markdown (ignore spans)
    width = max((len(r) for r in rows), default=0)
    for r in rows:
        r += [{"text": "", "rowSpan": 1, "colSpan": 1}] * (width - len(r))

    return {"rows": rows, "any_span": any_span, "bbox": bbox, "segs": all_spans}


def _merge_bbox(a, b):
    return (min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))


def _render_table_md(tbl) -> List[str]:
    """Markdown table (no col/row spans)."""
    lines = []
    rows = tbl["rows"]
    if not rows:
        return lines
    header = [c["text"] for c in rows[0]]
    if not any(header):
        header = [f"Col {i + 1}" for i in range(len(header))]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    for r in rows[1:]:
        lines.append("| " + " | ".join(c["text"] for c in r) + " |")
    return lines


def _render_table_html(tbl) -> List[str]:
    """HTML table with support for rowSpan/colSpan."""
    lines = ["<table>"]
    rows = tbl["rows"]
    if rows:
        # header guess: first row
        lines.append("  <thead>")
        lines.append("    <tr>")
        for c in rows[0]:
            attrs = []
            if c["colSpan"] > 1:
                attrs.append(f'colspan="{c["colSpan"]}"')
            if c["rowSpan"] > 1:
                attrs.append(f'rowspan="{c["rowSpan"]}"')
            attr = (" " + " ".join(attrs)) if attrs else ""
            lines.append(f"      <th{attr}>{c['text']}</th>")
        lines.append("    </tr>")
        lines.append("  </thead>")
        if len(rows) > 1:
            lines.append("  <tbody>")
            for r in rows[1:]:
                lines.append("    <tr>")
                for c in r:
                    attrs = []
                    if c["colSpan"] > 1:
                        attrs.append(f'colspan="{c["colSpan"]}"')
                    if c["rowSpan"] > 1:
                        attrs.append(f'rowspan="{c["rowSpan"]}"')
                    attr = (" " + " ".join(attrs)) if attrs else ""
                    lines.append(f"      <td{attr}>{c['text']}</td>")
                lines.append("    </tr>")
            lines.append("  </tbody>")
    lines.append("</table>")
    return lines


def _fields_to_groups(
    fields: List[Dict[str, Any]], full_text: str, row_threshold: float
):
    """
    Group form fields that lie on approximately the same horizontal band (row).
    Each group is rendered as a compact two-column KV Markdown table.
    """

    def field_tuple(ff):
        name = _get(ff, "fieldName", "field_name", default={})
        value = _get(ff, "fieldValue", "field_value", default={})
        nlay = _get(name, "layout", default=name)
        vlay = _get(value, "layout", default=value)
        nbox = _bbox_from_layout(nlay)
        vbox = _bbox_from_layout(vlay)

        ymid = (
            ((vbox[1] + vbox[3]) / 2.0)
            if vbox[1] != math.inf
            else ((nbox[1] + nbox[3]) / 2.0)
        )
        xleft = min(nbox[0], vbox[0])

        k = _escape_md(_text_from_segments(full_text, _layout_segments(nlay)))
        v = _escape_md(_text_from_segments(full_text, _layout_segments(vlay)))
        if k.endswith(":"):
            k = k[:-1].rstrip()

        segs = _union_segments(_layout_segments(nlay), _layout_segments(vlay))
        bbox = _merge_bbox(nbox, vbox)
        return dict(y=ymid, x=xleft, key=k, val=v, segs=segs, bbox=bbox)

    tuples = [field_tuple(f) for f in fields if f]
    tuples = [t for t in tuples if t["key"] or t["val"]]
    tuples.sort(key=lambda t: (round(t["y"], 4), round(t["x"], 4)))

    groups = []
    cur = None
    for t in tuples:
        if cur is None:
            cur = {
                "rows": [(t["key"], t["val"])],
                "segs": t["segs"],
                "bbox": t["bbox"],
                "y": t["y"],
                "x": t["x"],
            }
            continue
        if abs(t["y"] - cur["y"]) <= row_threshold:
            cur["rows"].append((t["key"], t["val"]))
            cur["segs"] = _union_segments(cur["segs"], t["segs"])
            cur["bbox"] = _merge_bbox(cur["bbox"], t["bbox"])
        else:
            groups.append(cur)
            cur = {
                "rows": [(t["key"], t["val"])],
                "segs": t["segs"],
                "bbox": t["bbox"],
                "y": t["y"],
                "x": t["x"],
            }
    if cur:
        groups.append(cur)
    groups.sort(key=lambda g: (g["y"], g["x"]))
    return groups


def _maybe_two_columns(
    items: List[Dict[str, Any]], col_gap_threshold: float
) -> Tuple[bool, float]:
    """
    Detect a two-column layout by finding a large gap in x-centers.
    Returns (is_two_col, split_x).
    """
    if len(items) < 6:  # too few to decide
        return (False, 0.5)
    xs = sorted(_center_x(it["bbox"]) for it in items if "bbox" in it)
    gaps = [(xs[i + 1] - xs[i], i) for i in range(len(xs) - 1)]
    if not gaps:
        return (False, 0.5)
    biggest_gap, idx = max(gaps, key=lambda g: g[0])
    # If the biggest gap is wide, split between xs[idx] and xs[idx+1]
    if biggest_gap >= col_gap_threshold:
        split_x = (xs[idx] + xs[idx + 1]) / 2.0
        return (True, split_x)
    return (False, 0.5)


def _assign_column(it, split_x: float) -> int:
    cx = _center_x(it["bbox"])
    return 0 if cx <= split_x else 1


def convert_document_ai_to_markdown(
    document_ai_json: Dict[str, Any],
    kv_row_threshold: float = 0.018,
    col_gap_threshold: float = 0.18,
    include_kv_header: bool = True,
    label_tables: bool = False,
    page_sep: bool = False,
    header_heuristics: bool = True,
    debug_spans: bool = False,
) -> str:
    """
    Convert Document AI JSON response to Markdown using V3 algorithm.

    Args:
        document_ai_json: Document AI JSON response
        kv_row_threshold: Vertical proximity to group KV rows
        col_gap_threshold: Normalized x-gap to detect 2-column layout
        include_kv_header: Include 'Field | Value' header for KV groups
        label_tables: Add '### Table' label before each table
        page_sep: Insert '---' between pages
        header_heuristics: Enable heading heuristics in text blocks
        debug_spans: Emit HTML comments with text span indices

    Returns:
        Markdown string
    """
    doc = _doc_obj(document_ai_json)
    pages = doc.get("pages", [])
    full_text = doc.get("text", "")

    md = []
    title = _get(doc, "documentSchema", "document_schema", default={})
    title = _get(title, "displayName", "display_name", default="") or "Document"
    md.append(f"# {_escape_md(title)}\n")

    for p_idx, page in enumerate(pages, start=1):
        tables = _get(page, "tables", "tables", default=[]) or []
        form_fields = _get(page, "formFields", "form_fields", default=[]) or []

        # Prefer blocks; fallback to paragraphs; fallback to lines
        blocks = _get(page, "blocks", default=None)
        paragraphs = _get(page, "paragraphs", default=None)
        lines = _get(page, "lines", default=None)
        text_containers = (
            blocks
            if isinstance(blocks, list)
            else (paragraphs if isinstance(paragraphs, list) else (lines or []))
        )

        items = []
        consumed = []

        # tables
        tcount = 0
        for t in tables:
            tinfo = _table_to_renderable(t, full_text)
            titem = {
                "type": "table",
                "rows": tinfo["rows"],
                "any_span": tinfo["any_span"],
                "bbox": tinfo["bbox"],
                "y": tinfo["bbox"][1],
                "x": tinfo["bbox"][0],
                "segs": tinfo["segs"],
                "label_index": tcount,
            }
            items.append(titem)
            consumed = _merge_intervals(consumed + tinfo["segs"])
            tcount += 1

        # kv groups
        kv_groups = _fields_to_groups(form_fields, full_text, kv_row_threshold)
        for g in kv_groups:
            items.append(
                {
                    "type": "kv",
                    "rows": g["rows"],
                    "bbox": g["bbox"],
                    "y": g["y"],
                    "x": g["x"],
                    "segs": g["segs"],
                }
            )
            consumed = _merge_intervals(consumed + g["segs"])

        # text containers (residual text)
        for c in text_containers:
            lay = _get(c, "layout", default=c)
            segs = _layout_segments(lay)
            residual = _subtract_intervals(segs, consumed)
            if not residual:
                continue
            text = _text_from_segments(full_text, residual)
            text = _cleanup_text(text)
            if not text.strip():
                continue
            bbox = _bbox_from_layout(lay)
            items.append(
                {
                    "type": "text",
                    "text": text,
                    "bbox": bbox,
                    "y": bbox[1],
                    "x": bbox[0],
                    "segs": residual,
                }
            )

        # Two-column ordering (only affects text + kv; tables remain by bbox)
        # We consider all items; if two columns detected, sort by (col, y, x)
        two_col, split_x = _maybe_two_columns(
            [it for it in items if "bbox" in it], col_gap_threshold
        )

        # final sort
        if two_col:
            items.sort(
                key=lambda it: (
                    _assign_column(it, split_x),
                    round(it["y"], 4),
                    round(it["x"], 4),
                )
            )
        else:
            items.sort(key=lambda it: (round(it["y"], 4), round(it["x"], 4)))

        # render page
        md.append(f"\n## Page {p_idx}\n")
        for it in items:
            if it["type"] == "text":
                # Bullet detection (per line)
                out_lines = []
                for ln in it["text"].splitlines():
                    s = ln.strip()
                    if not s:
                        out_lines.append("")
                        continue
                    if s.startswith(("• ", "· ", "- ", "* ")):
                        out_lines.append("- " + s.lstrip("•·*- ").strip())
                    elif header_heuristics and _is_heading_like(s):
                        out_lines.append(f"### {s}")
                    else:
                        out_lines.append(s)
                md.append("\n".join(out_lines) + "\n")
                if debug_spans:
                    md.append(f"<!-- spans: {it['segs']} -->")
            elif it["type"] == "kv":
                rows = it["rows"]
                if not rows:
                    continue
                if include_kv_header:
                    md.append("| Field | Value |")
                    md.append("|---|---|")
                for k, v in rows:
                    md.append(f"| {_escape_md(k)} | {_escape_md(v)} |")
                md.append("")
                if debug_spans:
                    md.append(f"<!-- spans: {it['segs']} -->")
            elif it["type"] == "table":
                if label_tables:
                    md.append("### Table")
                if it["any_span"]:
                    md += _render_table_html(it)
                else:
                    md += _render_table_md(it)
                md.append("")
                if debug_spans:
                    md.append(f"<!-- spans: {it['segs']} -->")

        if page_sep and p_idx < len(pages):
            md.append("\n---\n")

    return "\n".join(md)
