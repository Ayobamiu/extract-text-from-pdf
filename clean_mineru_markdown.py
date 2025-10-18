#!/usr/bin/env python3
"""
Robust post-processor for MinerU-generated Markdown.

Features:
- Repair hyphenation across line breaks
- Merge broken paragraph lines with improved heuristics
- Detect and convert simple table-like blocks into Markdown tables
- Normalize headings and remove repeated headers/footers
- CLI with arguments for input/output and tuning

Usage:
    python clean_mineru_markdown.py -i input.md -o output.cleaned.md
"""

import re
import sys
import argparse
import logging
from collections import Counter
import json
from pathlib import Path

# Spell checker removed to avoid edge cases

# OCR correction removed completely

LOG = logging.getLogger("cleaner")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


def load_markdown(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines()


def save_markdown(lines, path):
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    LOG.info("Saved cleaned Markdown to: %s", path)


def normalize_whitespace(s):
    # collapse multiple spaces, but keep two+ spaces (useful for table detection later)
    s = s.replace("\u00a0", " ")  # non-breaking spaces
    s = re.sub(r"[ \t]+", " ", s)
    s = s.rstrip()
    return s


# OCR correction functions removed


# OCR correction functions removed


# OCR correction functions removed


def remove_repeated_headers(lines, threshold=3, min_len=3):
    """
    Remove lines that repeat across the document more than `threshold` times.
    Useful for headers/footers such as 'STATE OF MICHIGAN' appearing on each page.
    """
    counts = Counter(
        [ln.strip() for ln in lines if ln.strip() and len(ln.strip()) >= min_len]
    )
    repeated = {ln for ln, c in counts.items() if c >= threshold}
    if not repeated:
        return lines
    LOG.info("Removing %d repeated lines (likely headers/footers)", len(repeated))
    new_lines = [ln for ln in lines if ln.strip() not in repeated]
    return new_lines


def is_likely_heading(line):
    stripped = line.strip()
    if not stripped:
        return False
    # if majority uppercase letters and length > 3
    letters = re.sub(r"[^A-Za-z]", "", stripped)
    if len(letters) >= 4:
        upper_ratio = sum(1 for c in letters if c.isupper()) / max(1, len(letters))
        if upper_ratio > 0.6:
            return True
    # or if it's short and Title Case and followed/preceded by blank lines; we'll handle later
    return False


def detect_table_block(lines, idx):
    """
    If the current line looks like a table row (contains two or more occurrences
    of 2+ spaces in a row, or tabs), return the continuous block of table lines.
    """
    table_lines = []
    n = len(lines)
    i = idx
    while i < n:
        ln = lines[i]
        # if contains multiple consecutive spaces (indicating column gaps) or tabs or pipes
        if re.search(r"( {2,}|\t|\|)", ln):
            table_lines.append(ln)
            i += 1
        else:
            break
    return table_lines


def convert_table_lines_to_markdown(table_lines):
    """
    Naive conversion: split on 2+ spaces or tabs or pipe characters and render as markdown table.
    The first row is treated as header if it contains non-numeric text.
    """
    rows = []
    for ln in table_lines:
        # replace tabs with 4 spaces to normalize
        ln_norm = ln.replace("\t", "    ")
        # split by 2+ spaces or pipe
        cols = [c.strip() for c in re.split(r"\s{2,}|\|", ln_norm) if c.strip() != ""]
        rows.append(cols)

    if not rows:
        return table_lines  # fallback

    # determine the max column count
    max_cols = max(len(r) for r in rows)
    # pad rows
    rows = [r + [""] * (max_cols - len(r)) for r in rows]

    # build markdown
    md = []
    header = rows[0]
    md.append("| " + " | ".join(header) + " |")
    md.append("| " + " | ".join(["---"] * max_cols) + " |")
    for r in rows[1:]:
        md.append("| " + " | ".join(r) + " |")
    return md


def repair_hyphenation_and_merge(lines):
    """
    Merge lines into paragraphs with improved heuristics:
    - If a line ends with a hyphen, join removing hyphen.
    - If next line starts lowercase, join.
    - If line doesn't end with terminal punctuation and next line doesn't start uppercase (or is short), join.
    - Preserve blank lines.
    """
    out = []
    buffer = ""
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i].rstrip()
        if not line:
            if buffer:
                out.append(buffer.strip())
                buffer = ""
            out.append("")  # preserve blank line
            i += 1
            continue

        # handle hyphenation
        if line.endswith("-"):
            line = line[:-1].rstrip()
            next_part = lines[i + 1].lstrip() if i + 1 < n else ""
            combined = f"{line}{next_part}"
            # skip next line because merged
            i += 2
            if buffer:
                buffer += " " + combined
            else:
                buffer = combined
            continue

        # peek next line
        next_line = lines[i + 1] if i + 1 < n else ""
        next_stripped = next_line.lstrip()

        # if buffer empty, start buffer
        if not buffer:
            buffer = line
        else:
            # decide whether to join
            join_condition = False
            if buffer and not re.search(
                r"[\.:\?!]$", buffer
            ):  # no terminal punctuation
                # join if next starts lowercase or is short (likely continuation)
                if re.match(r"^[a-z0-9\(\[]", next_stripped):
                    join_condition = True
                elif len(next_stripped.split()) < 6:
                    # short line could be continuation (e.g., address)
                    join_condition = True

            if join_condition:
                buffer += " " + next_stripped
                i += 1  # we consumed next line
                # note: do not increment here because we want to continue with updated i via while
                # but we've already consumed next line, so continue
                continue
            else:
                out.append(buffer.strip())
                buffer = ""
                # do not skip next line; let it be processed normally
        i += 1

    if buffer:
        out.append(buffer.strip())
    return out


def clean_lines_pipeline(lines, args):
    # normalize whitespace first
    lines = [normalize_whitespace(ln) for ln in lines]

    # remove repeated headers/footers
    lines = remove_repeated_headers(lines, threshold=args.header_repeat_threshold)

    # OCR correction removed

    # convert potential table blocks
    i = 0
    out = []
    while i < len(lines):
        ln = lines[i]
        if re.search(r"( {2,}|\t|\|)", ln):
            tbl = detect_table_block(lines, i)
            if len(tbl) >= args.min_table_rows:
                md_table = convert_table_lines_to_markdown(tbl)
                out.extend(md_table)
                i += len(tbl)
                continue
        out.append(ln)
        i += 1

    # repair hyphenation and merge paragraphs
    out = repair_hyphenation_and_merge(out)

    # normalize headings
    final = []
    for ln in out:
        if is_likely_heading(ln):
            # Title case the heading, but keep acronyms upper
            title = " ".join(
                [
                    w if w.isupper() and len(w) <= 4 else w.capitalize()
                    for w in ln.split()
                ]
            )
            final.append("## " + title)
        else:
            final.append(ln)
    return final


def build_arg_parser():
    p = argparse.ArgumentParser(description="Robust MinerU Markdown cleaner")
    p.add_argument("-i", "--input", required=True, help="Input markdown file")
    p.add_argument("-o", "--output", required=True, help="Output cleaned markdown")
    p.add_argument(
        "--min-table-rows",
        dest="min_table_rows",
        type=int,
        default=2,
        help="Minimum consecutive table-like rows to consider as a table",
    )
    p.add_argument(
        "--header-repeat-threshold",
        dest="header_repeat_threshold",
        type=int,
        default=3,
        help="Number of times a short line must appear to be considered header/footer",
    )
    p.add_argument("--debug", action="store_true", help="Enable debug logging")
    p.add_argument(
        "--middle-json",
        help="Optional path to MinerU middle.json for table reconstruction",
    )
    # Spell checking removed to avoid edge cases
    return p


def patch_tables_with_middle_json(md_lines, middle_path):
    """Replace poorly formatted tables in markdown with properly formatted ones from middle.json."""
    try:
        with open(middle_path, "r", encoding="utf-8") as f:
            middle_data = json.load(f)

        # Navigate to the correct structure: pdf_info -> preproc_blocks
        pdf_info = middle_data.get("pdf_info", [])
        if not pdf_info:
            LOG.warning("No pdf_info found in middle.json")
            return md_lines

        tables_found = 0
        patched_lines = list(md_lines)  # Start with original lines

        # Collect all tables from all pages first
        all_tables = []
        for page_idx, page_data in enumerate(pdf_info):
            preproc_blocks = page_data.get("preproc_blocks", [])

            # Find table blocks and their preceding titles
            for i, block in enumerate(preproc_blocks):
                if block.get("type") == "table":
                    tables_found += 1

                    # Look for title block just before this table
                    table_title = _extract_table_title(preproc_blocks, i)

                    # Extract HTML table from spans
                    html_table = _extract_html_table_from_block(block)
                    if html_table:
                        # Convert HTML table to Markdown
                        markdown_table = _html_table_to_markdown(html_table)
                        if markdown_table:
                            all_tables.append(
                                {
                                    "title": table_title,
                                    "markdown_table": markdown_table,
                                    "page_idx": page_idx,
                                    "block_idx": i,
                                }
                            )

        # Process all tables in order, preferring more complete tables
        tables_replaced = 0
        replaced_positions = {}  # Track which line positions have been replaced and their completeness

        # Sort tables by completeness (more rows = more complete)
        all_tables.sort(key=lambda t: len(t["markdown_table"]), reverse=True)

        for table_info in all_tables:
            # Try to find and replace the table in-place
            result_lines, was_replaced, replaced_line = _replace_table_in_place(
                patched_lines, table_info["title"], table_info["markdown_table"]
            )

            if was_replaced:
                current_completeness = len(table_info["markdown_table"])

                # Check if original table at this line is more complete
                original_completeness = _get_original_table_completeness(
                    patched_lines, replaced_line
                )

                # Only replace if this position hasn't been replaced, or if this table is more complete than both
                # the previous replacement AND the original table
                should_replace = (
                    replaced_line not in replaced_positions
                    or current_completeness > replaced_positions[replaced_line]
                ) and current_completeness >= original_completeness

                if should_replace:
                    patched_lines = result_lines
                    tables_replaced += 1
                    replaced_positions[replaced_line] = current_completeness
                    LOG.info(
                        "Replaced table %d/%d (page %d, block %d) at line %d with %d rows (original had %d)",
                        tables_replaced,
                        len(all_tables),
                        table_info["page_idx"],
                        table_info["block_idx"],
                        replaced_line,
                        current_completeness,
                        original_completeness,
                    )
                else:
                    # Original table is more complete, convert it to Markdown instead
                    if original_completeness > current_completeness:
                        # Convert the original HTML table to Markdown
                        original_html = _extract_original_html_table(
                            patched_lines, replaced_line
                        )
                        if original_html:
                            original_markdown = _html_table_to_markdown(original_html)
                            if original_markdown:
                                # Replace with converted original table
                                replacement_lines = []
                                replacement_lines.append("")  # Empty line before table
                                if table_info["title"]:
                                    replacement_lines.append(
                                        f"### {table_info['title']}"
                                    )
                                    replacement_lines.append("")
                                replacement_lines.extend(original_markdown)
                                replacement_lines.append("")  # Empty line after table

                                patched_lines = (
                                    patched_lines[:replaced_line]
                                    + replacement_lines
                                    + patched_lines[replaced_line + 1 :]
                                )
                                tables_replaced += 1
                                LOG.info(
                                    "Converted original HTML table to Markdown at line %d with %d rows",
                                    replaced_line,
                                    original_completeness,
                                )
                            else:
                                LOG.info(
                                    "Skipped table (page %d, block %d) - %d rows vs original %d rows at line %d",
                                    table_info["page_idx"],
                                    table_info["block_idx"],
                                    current_completeness,
                                    original_completeness,
                                    replaced_line,
                                )
                        else:
                            LOG.info(
                                "Skipped table (page %d, block %d) - %d rows vs original %d rows at line %d",
                                table_info["page_idx"],
                                table_info["block_idx"],
                                current_completeness,
                                original_completeness,
                                replaced_line,
                            )
                    else:
                        LOG.info(
                            "Skipped table (page %d, block %d) - %d rows vs original %d rows at line %d",
                            table_info["page_idx"],
                            table_info["block_idx"],
                            current_completeness,
                            original_completeness,
                            replaced_line,
                        )

        LOG.info(
            "Patched tables from middle.json: %d found, %d replaced",
            tables_found,
            tables_replaced,
        )
        return patched_lines

    except Exception as e:
        LOG.warning(f"Failed to patch tables from middle.json: {e}")
        return md_lines


def _replace_table_in_place(md_lines, table_title, markdown_table):
    """Find and replace poorly formatted table with properly formatted one."""
    try:
        import re

        # Create the replacement content
        replacement_lines = []
        replacement_lines.append("")  # Empty line before table

        # Add title if found
        if table_title:
            replacement_lines.append(f"### {table_title}")
            replacement_lines.append("")

        replacement_lines.extend(markdown_table)
        replacement_lines.append("")  # Empty line after table

        # Try to find the table to replace using different strategies
        result_lines, was_replaced, replaced_line = _find_and_replace_table(
            md_lines, replacement_lines
        )

        return result_lines, was_replaced, replaced_line

    except Exception as e:
        LOG.warning(f"Failed to replace table in-place: {e}")
        return md_lines, False, -1


def _find_and_replace_table(md_lines, replacement_lines):
    """Find table-like content and replace it with properly formatted table."""
    try:
        import re

        # Strategy 1: Look for HTML tables FIRST (highest priority)
        html_table_pattern = r"<table>.*?</table>"
        for i, line in enumerate(md_lines):
            if re.search(html_table_pattern, line, re.DOTALL | re.IGNORECASE):
                # Found HTML table, replace it
                new_lines = md_lines[:i] + replacement_lines + md_lines[i + 1 :]
                LOG.info(f"Replaced HTML table at line {i}")
                return new_lines, True, i

        # Strategy 2: Look for existing markdown tables (| | | format)
        table_pattern = r"^\s*\|.*\|.*$"
        table_start = None
        table_end = None

        for i, line in enumerate(md_lines):
            if re.match(table_pattern, line):
                if table_start is None:
                    table_start = i
                table_end = i
            elif (
                table_start is not None
                and not re.match(table_pattern, line)
                and line.strip()
            ):
                # End of table block
                break

        if table_start is not None and table_end is not None:
            # Replace the found table
            new_lines = (
                md_lines[:table_start] + replacement_lines + md_lines[table_end + 1 :]
            )
            LOG.info(f"Replaced markdown table at lines {table_start}-{table_end}")
            return new_lines, True, table_start

        # Strategy 3: Look for table-like text patterns (multiple columns separated by spaces)
        for i, line in enumerate(md_lines):
            # Look for lines that might be table rows (multiple words separated by spaces)
            words = line.strip().split()
            if len(words) >= 3 and all(len(word) > 0 for word in words):
                # Check if next few lines also look like table rows
                table_candidates = [line]
                for j in range(i + 1, min(i + 10, len(md_lines))):
                    next_line = md_lines[j].strip()
                    if not next_line:  # Empty line ends table
                        break
                    next_words = next_line.split()
                    if len(next_words) >= 3:
                        table_candidates.append(next_line)
                    else:
                        break

                # If we found multiple table-like lines, replace them
                if len(table_candidates) >= 2:
                    new_lines = (
                        md_lines[:i]
                        + replacement_lines
                        + md_lines[i + len(table_candidates) :]
                    )
                    LOG.info(
                        f"Replaced text table at lines {i}-{i + len(table_candidates) - 1}"
                    )
                    return new_lines, True, i

        # Strategy 4: If no table found, append at the end (fallback)
        LOG.warning("No table found to replace, appending at end")
        return md_lines + replacement_lines, True, len(md_lines)

    except Exception as e:
        LOG.warning(f"Error in table replacement: {e}")
        return md_lines, False, -1


def _get_original_table_completeness(md_lines, line_index):
    """Get the completeness (row count) of the original table at the given line."""
    try:
        import re

        if line_index >= len(md_lines):
            return 0

        line = md_lines[line_index]

        # Check for HTML table
        html_table_pattern = r"<table>.*?</table>"
        html_match = re.search(html_table_pattern, line, re.DOTALL | re.IGNORECASE)
        if html_match:
            html_table = html_match.group()
            return html_table.count("<tr>")

        # Check for markdown table
        table_pattern = r"^\s*\|.*\|.*$"
        if re.match(table_pattern, line):
            # Count consecutive markdown table lines
            count = 0
            for i in range(line_index, len(md_lines)):
                if re.match(table_pattern, md_lines[i]):
                    count += 1
                elif md_lines[i].strip() and count > 0:
                    break
            return count

        return 0

    except Exception:
        return 0


def _extract_original_html_table(md_lines, line_index):
    """Extract the original HTML table content from the given line."""
    try:
        import re

        if line_index >= len(md_lines):
            return None

        line = md_lines[line_index]

        # Check for HTML table
        html_table_pattern = r"<table>.*?</table>"
        html_match = re.search(html_table_pattern, line, re.DOTALL | re.IGNORECASE)
        if html_match:
            return html_match.group()

        return None

    except Exception:
        return None


def _extract_table_title(preproc_blocks, table_index):
    """Extract title from the block just before the table."""
    try:
        import re

        # Look at the previous block
        if table_index > 0:
            prev_block = preproc_blocks[table_index - 1]
            if prev_block.get("type") == "title":
                # Extract text from title block
                lines = prev_block.get("lines", [])
                title_parts = []

                for line in lines:
                    spans = line.get("spans", [])
                    for span in spans:
                        if span.get("type") == "text":
                            content = span.get("content", "").strip()
                            if content:
                                title_parts.append(content)

                if title_parts:
                    # Join title parts and clean up
                    title = " ".join(title_parts).strip()
                    # Remove extra whitespace
                    title = re.sub(r"\s+", " ", title)
                    return title if title else None

        return None
    except Exception:
        return None


def _extract_html_table_from_block(block):
    """Extract HTML table content from a table block."""
    try:
        blocks = block.get("blocks", [])
        for sub_block in blocks:
            if sub_block.get("type") == "table_body":
                lines = sub_block.get("lines", [])
                for line in lines:
                    spans = line.get("spans", [])
                    for span in spans:
                        if span.get("type") == "table":
                            return span.get("html", "")
        return None
    except Exception:
        return None


def _html_table_to_markdown(html_table):
    """Convert HTML table to Markdown table format."""
    try:
        import re

        # Extract table rows using regex
        row_pattern = r"<tr[^>]*>(.*?)</tr>"
        rows = re.findall(row_pattern, html_table, re.DOTALL | re.IGNORECASE)

        if not rows:
            return None

        markdown_rows = []

        for i, row_html in enumerate(rows):
            # Extract cell content
            cell_pattern = r"<td[^>]*>(.*?)</td>"
            cells = re.findall(cell_pattern, row_html, re.DOTALL | re.IGNORECASE)

            if not cells:
                continue

            # Clean cell content
            cleaned_cells = []
            for cell in cells:
                # Remove any remaining HTML tags
                clean_cell = re.sub(r"<[^>]+>", "", cell)
                # Decode HTML entities
                clean_cell = clean_cell.replace("&nbsp;", " ").replace("&amp;", "&")
                # Strip whitespace
                clean_cell = clean_cell.strip()
                cleaned_cells.append(clean_cell)

            # Create markdown row
            markdown_row = "| " + " | ".join(cleaned_cells) + " |"
            markdown_rows.append(markdown_row)

            # Add header separator after first row
            if i == 0:
                separator = "| " + " | ".join(["---"] * len(cleaned_cells)) + " |"
                markdown_rows.append(separator)

        return markdown_rows if markdown_rows else None

    except Exception as e:
        LOG.warning(f"Failed to convert HTML table to Markdown: {e}")
        return None


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.debug:
        LOG.setLevel(logging.DEBUG)
        LOG.debug("Debug logging enabled")

    LOG.info("Loading markdown: %s", args.input)
    lines = load_markdown(args.input)
    LOG.info("Lines loaded: %d", len(lines))

    cleaned = clean_lines_pipeline(lines, args)

    # if args.middle_json:
    #     LOG.info("Patching tables from middle.json: %s", args.middle_json)
    #     cleaned = patch_tables_with_middle_json(cleaned, args.middle_json)

    LOG.info("Final lines: %d", len(cleaned))
    save_markdown(cleaned, args.output)


if __name__ == "__main__":
    main()
