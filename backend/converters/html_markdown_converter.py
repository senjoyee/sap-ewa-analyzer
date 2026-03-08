"""
HTML to Markdown Converter for SAP EWA Reports

Converts EWA .htm files (exported from Word as "filtered HTML") to Markdown.
All rating icons (GIF images) are classified by pixel color analysis and
replaced with text labels like [GREEN], [YELLOW], [RED], etc.

Key Features:
- Runtime pixel analysis of icon GIFs using Pillow (works with any EWA report)
- Preserves document structure: headings, tables, lists, links
- Converts rating icons to text labels for LLM consumption
- Handles progress bar images (32x15 and 41x100)
- Charts and large images become [CHART] or [IMAGE] placeholders
"""

import os
import re
import hashlib
import logging
from pathlib import Path
from typing import Optional

from PIL import Image
from bs4 import BeautifulSoup, Tag, NavigableString

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Icon classification
# ---------------------------------------------------------------------------

# Thresholds for classifying small icons by average non-background pixel color
_ICON_MAX_WIDTH = 20   # 16x14 and 16x16 icons
_BAR_HORIZ_SIZE = (32, 15)
_BAR_VERT_WIDTH = 41

# Minimum non-background pixel count to consider an image non-trivial
_MIN_COLOR_PIXELS = 5

# Pre-computed icon pixel-hash table (MD5 of RGBA pixel data).
# Covers all known EWA rating icons so classification works without
# runtime pixel analysis for recognised icons.
# Generated from sample EWA report: SHP_20474620_850648038_2026-03-02_R_EWA
_KNOWN_ICON_HASHES: dict[str, str] = {
    # BLUE (16x14)
    "d7d279bb48a8d71c85d42d5f43003be2": "[BLUE]",
    "30de9c8658582bd738b675b0037bd7d7": "[BLUE]",
    "3965494858d3faeae6b307cddd5cbdc7": "[BLUE]",
    # GRAY (16x14)
    "2c3c964fa29df911943e6006c15eab06": "[GRAY]",
    "e1b96877094368da9e37f4932e728534": "[GRAY]",
    "7f217c88c5c04f24f88c71cf493fca41": "[GRAY]",
    "f99b403e8a06fc5f9aa8bb8bfe4aa90b": "[GRAY]",
    "2ab2293e5d0e5249e9a4de7fc05b221a": "[GRAY]",
    "74fa9460acfd3927de758b4f048d6d4f": "[GRAY]",
    # GRAY_BAR (32x15)
    "2b1afc2199f9a582a105a78a32767454": "[GRAY_BAR]",
    "c96cfb4e2f7430b1fcc72033f3eab189": "[GRAY_BAR]",
    "b45dc0d3a603bee9776759ae11439b9b": "[GRAY_BAR]",
    # GREEN (16x14)
    "6e21cb214337562288a80e7e5a43b7b1": "[GREEN]",
    "ae6d4835c58c4f2ea0b08dc0582ef785": "[GREEN]",
    "a4746d0befe413daa879df446913fa86": "[GREEN]",
    "6b61822904f7eda0bb13a5d859be794c": "[GREEN]",
    "3e8e0805dfb3b5ef239ea8efb237e7a6": "[GREEN]",
    "32b1da78d539893900610b5adadcfafb": "[GREEN]",
    "0e3cc76c7d6cfc20f77f12521296e79e": "[GREEN]",
    "dda2cec40dca5d0ca0c7afb9041d2f72": "[GREEN]",
    "ea6de01a481241168d7880494344c7db": "[GREEN]",
    "ea6d7ea285f0754007d4d753306df8cb": "[GREEN]",
    "537ea033b8b1b1f797e2ce9ab59fb473": "[GREEN]",
    # GREEN_BAR (32x15 / 41x100)
    "3246c1d94713d64f42e9258aa648599c": "[GREEN_BAR]",
    "46882c7f941acb354df7a66a7fd71785": "[GREEN_BAR]",
    "1c634918d5d042b683c06d07a276e5c4": "[GREEN_BAR]",
    "04586bc109d86c64a3b44001694080be": "[GREEN_BAR]",
    "c55e8c5e75f305c58b4f3a5f6bc5641e": "[GREEN_BAR]",
    "4bccdc1eeaa1f0c31ca5f22b584276e1": "[GREEN_BAR]",
    "9f2ee22b943a41f856c1476295d40016": "[GREEN_BAR]",
    # NOT_RATED (16x14 / 16x16)
    "423b0448e5a27a9c5b40a3581b034cce": "[NOT_RATED]",
    "54ee8b9f5e84d049112e327cb1532a04": "[NOT_RATED]",
    "eee9cc45a2ad0128e0c4224f20254b2d": "[NOT_RATED]",
    "17b4ebb1dc8381d26be3c4a9e5e033d1": "[NOT_RATED]",
    # RED (16x14)
    "59d85d6ff36d8d22cc171a4be6b4dab4": "[RED]",
    "0dcb043d93362db34e18e43973a4dbe1": "[RED]",
    "dc3022b77b8645a56fd7b187bdbd5d34": "[RED]",
    "3bdf0d49a7602e32279f886df405da9d": "[RED]",
    "4bfca9ff9e6b2e1ceb55ed42c6c7122b": "[RED]",
    "4f892c34e4678233f406174667f0288e": "[RED]",
    # RED_BAR (32x15 / 41x100)
    "f28580d67f0b2bbd42c42ae43cb30518": "[RED_BAR]",
    "9a31964d762fb4a9b3e9c1fff98a7d2d": "[RED_BAR]",
    "53f5fdfb8fcc2208659fe6dc5d66c28c": "[RED_BAR]",
    # YELLOW (16x14)
    "40e0e93b8137ce3fd6a141f6d54820b5": "[YELLOW]",
    "40f3550a8c89a140f6778ed483bd6364": "[YELLOW]",
    "6fb6ddacd322bff285eec76f056389da": "[YELLOW]",
    "3e8048b4ad9aa0bcdb594299007f9e77": "[YELLOW]",
    "f57a970ec12e8559b1725dc34a1eafbd": "[YELLOW]",
    "cdf2b795a9435e8168dfa9829f6a1472": "[YELLOW]",
    "01e11723d2e469c058ff784a3ab60e14": "[YELLOW]",
    "6da615e518feadce1c3a1a88ff9bd6f5": "[YELLOW]",
    "2f68b97fb71eb5864bad46f1ac28c8d9": "[YELLOW]",
    "bd58e5727cc4d9de2b128453d6e072c5": "[YELLOW]",
    "82d74b2fb7e669f039120330126330b6": "[YELLOW]",
    "0573e7bccba7e3bf979769519f430d7d": "[YELLOW]",
    # YELLOW_BAR (41x100)
    "94293253a4f8cb8c7c2900440a811555": "[YELLOW_BAR]",
    "f5fdc0e0f155a1906b8e2793e0052feb": "[YELLOW_BAR]",
    "bb78b1c845e571253b2218b9e737625c": "[YELLOW_BAR]",
}


def _avg_color(image_path: str) -> tuple[Optional[tuple[int, int, int]], int, int]:
    """Return (avg_rgb, width, height) for non-transparent/non-white pixels."""
    try:
        img = Image.open(image_path).convert("RGBA")
    except Exception as exc:
        logger.warning("Cannot open image %s: %s", image_path, exc)
        return None, 0, 0

    w, h = img.size
    pixels = list(img.getdata())

    color_pixels = []
    for r, g, b, a in pixels:
        if a < 50:
            continue
        if r > 240 and g > 240 and b > 240:
            continue
        color_pixels.append((r, g, b))

    if len(color_pixels) < _MIN_COLOR_PIXELS:
        return None, w, h

    n = len(color_pixels)
    avg_r = sum(r for r, _, _ in color_pixels) // n
    avg_g = sum(g for _, g, _ in color_pixels) // n
    avg_b = sum(b for _, _, b in color_pixels) // n
    return (avg_r, avg_g, avg_b), w, h


def _classify_bar(image_path: str) -> str:
    """Classify a progress-bar image by pixel color ratios."""
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return "[BAR]"

    pixels = list(img.getdata())
    total = len(pixels)
    if total == 0:
        return "[BAR]"

    red = sum(1 for r, g, b in pixels if r > 150 and g < 100 and b < 100)
    green = sum(1 for r, g, b in pixels if g > 100 and r < 100 and b < 100)
    yellow = sum(1 for r, g, b in pixels if r > 200 and g > 150 and b < 50)

    pct_r, pct_g, pct_y = red / total, green / total, yellow / total

    if pct_g > 0.04:
        return "[GREEN_BAR]"
    if pct_r > 0.04:
        return "[RED_BAR]"
    if pct_y > 0.04:
        return "[YELLOW_BAR]"
    return "[GRAY_BAR]"


def _pixel_hash(image_path: str) -> Optional[str]:
    """Compute MD5 hash of RGBA pixel data for an image file."""
    try:
        img = Image.open(image_path).convert("RGBA")
        return hashlib.md5(img.tobytes()).hexdigest()
    except Exception:
        return None


def classify_icon(image_path: str) -> str:
    """
    Classify an icon GIF by its dominant pixel color.

    Uses a pre-computed hash table for instant lookup of known icons.
    Falls back to runtime pixel analysis for unrecognised images.
    """
    # Fast path: check pre-computed hash table first
    ph = _pixel_hash(image_path)
    if ph and ph in _KNOWN_ICON_HASHES:
        return _KNOWN_ICON_HASHES[ph]

    # Slow path: runtime pixel analysis for unknown icons
    avg, w, h = _avg_color(image_path)

    # Large images are charts / decorations
    if w > 50 and h > 50:
        return _classify_bar(image_path) if w <= _BAR_VERT_WIDTH else "[IMAGE]"

    # Progress bars (32x15 horizontal or 41xN vertical)
    if (w, h) == _BAR_HORIZ_SIZE or w == _BAR_VERT_WIDTH:
        return _classify_bar(image_path)

    # Decorative / separator images (very wide but short)
    if w > 100 and h < 20:
        return "[SEPARATOR]"

    # Large decorative images
    if w > 50:
        return "[IMAGE]"

    # If we couldn't determine color → not rated
    if avg is None:
        return "[NOT_RATED]"

    r, g, b = avg

    # Black / dash icon (avg very dark, all channels low)
    if r < 20 and g < 20 and b < 20:
        return "[NOT_RATED]"

    # Red icon: high red, low green and blue
    if r > 100 and g < 60 and b < 60:
        return "[RED]"

    # Blue icon: high blue, low red and green
    if b > 100 and r < 60 and g < 60:
        return "[BLUE]"

    # Yellow icon: high red, high green, low blue
    if r > 100 and g > 80 and b < 60:
        return "[YELLOW]"

    # Green icon: green channel dominant
    if g > 50 and r < 80 and b < 50:
        return "[GREEN]"

    # Gray icon: all channels roughly equal and mid-range
    if abs(r - g) < 30 and abs(g - b) < 30:
        return "[GRAY]"

    return "[NOT_RATED]"


def build_icon_map(images_dir: str) -> dict[str, str]:
    """Pre-scan all GIFs in the companion folder and build {filename: label}."""
    icon_map: dict[str, str] = {}
    if not os.path.isdir(images_dir):
        logger.warning("Images directory not found: %s", images_dir)
        return icon_map

    for fname in os.listdir(images_dir):
        if fname.lower().endswith((".gif", ".png", ".jpg", ".jpeg")):
            full = os.path.join(images_dir, fname)
            icon_map[fname] = classify_icon(full)

    logger.info(
        "Classified %d images in %s",
        len(icon_map),
        images_dir,
    )
    return icon_map


# ---------------------------------------------------------------------------
# HTML → Markdown conversion
# ---------------------------------------------------------------------------


def _detect_encoding(html_bytes: bytes) -> str:
    """Detect encoding from HTML meta tag, defaulting to windows-1252."""
    head = html_bytes[:2048].decode("ascii", errors="ignore")
    match = re.search(r'charset=(["\']?)([^"\'\s;>]+)', head, re.IGNORECASE)
    if match:
        return match.group(2)
    return "windows-1252"


def _resolve_image_src(src: str, html_dir: str) -> Optional[str]:
    """Resolve relative image src to an absolute path."""
    if not src:
        return None
    # Handle relative or absolute paths
    resolved = os.path.normpath(os.path.join(html_dir, src))
    if os.path.isfile(resolved):
        return resolved
    return None


def _cell_text(td: Tag, icon_map: dict[str, str], html_dir: str) -> str:
    """Extract text content of a <td>, replacing <img> with icon labels."""
    parts: list[str] = []
    for child in td.descendants:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                parts.append(text)
        elif isinstance(child, Tag) and child.name == "img":
            src = child.get("src", "")
            fname = os.path.basename(src)
            label = icon_map.get(fname)
            if label is None:
                resolved = _resolve_image_src(src, html_dir)
                label = classify_icon(resolved) if resolved else "[IMAGE]"
            parts.append(label)
    return " ".join(parts)


def _convert_table(table: Tag, icon_map: dict[str, str], html_dir: str) -> str:
    """Convert an HTML <table> to a Markdown table."""
    rows = table.find_all("tr")
    if not rows:
        return ""

    md_rows: list[list[str]] = []
    for tr in rows:
        cells = tr.find_all(["td", "th"])
        row_data = []
        for cell in cells:
            text = _cell_text(cell, icon_map, html_dir)
            # Clean up whitespace
            text = re.sub(r"\s+", " ", text).strip()
            # Escape pipe characters in cell content
            text = text.replace("|", "\\|")
            row_data.append(text)
        if row_data:
            md_rows.append(row_data)

    if not md_rows:
        return ""

    # Determine max columns
    max_cols = max(len(r) for r in md_rows)

    # Pad rows to same length
    for row in md_rows:
        while len(row) < max_cols:
            row.append("")

    lines: list[str] = []
    # First row as header
    header = md_rows[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join("---" for _ in header) + " |")

    for row in md_rows[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _inline_text(element: Tag, icon_map: dict[str, str], html_dir: str) -> str:
    """Recursively extract inline text from an element, replacing imgs."""
    parts: list[str] = []

    for child in element.children:
        if isinstance(child, NavigableString):
            text = str(child)
            # Collapse whitespace but preserve single spaces
            text = re.sub(r"\s+", " ", text)
            if text.strip():
                parts.append(text.strip())
        elif isinstance(child, Tag):
            if child.name == "img":
                src = child.get("src", "")
                fname = os.path.basename(src)
                label = icon_map.get(fname)
                if label is None:
                    resolved = _resolve_image_src(src, html_dir)
                    label = classify_icon(resolved) if resolved else "[IMAGE]"
                parts.append(label)
            elif child.name == "br":
                parts.append("\n")
            elif child.name in ("b", "strong"):
                inner = _inline_text(child, icon_map, html_dir)
                if inner.strip():
                    parts.append(f"**{inner.strip()}**")
            elif child.name in ("i", "em"):
                inner = _inline_text(child, icon_map, html_dir)
                if inner.strip():
                    parts.append(f"*{inner.strip()}*")
            elif child.name == "a":
                href = child.get("href", "")
                inner = _inline_text(child, icon_map, html_dir)
                text_content = inner.strip()
                if text_content and href and not href.startswith("#"):
                    parts.append(f"[{text_content}]({href})")
                elif text_content:
                    parts.append(text_content)
            elif child.name == "span":
                inner = _inline_text(child, icon_map, html_dir)
                if inner.strip():
                    parts.append(inner)
            elif child.name in ("sub", "sup"):
                inner = _inline_text(child, icon_map, html_dir)
                if inner.strip():
                    parts.append(inner.strip())
            elif child.name == "table":
                # Nested table — convert inline
                parts.append("\n" + _convert_table(child, icon_map, html_dir) + "\n")
            else:
                # Recursively handle other inline elements (font, div, p inside td, etc.)
                inner = _inline_text(child, icon_map, html_dir)
                if inner.strip():
                    parts.append(inner)

    return " ".join(parts)


def convert_html_to_markdown(
    html_path: str,
    output_path: Optional[str] = None,
) -> str:
    """
    Convert an EWA HTML file to Markdown with icon text replacements.

    Args:
        html_path: Path to the .htm/.html file.
        output_path: Optional output path. Defaults to same name with .md extension.

    Returns:
        The generated Markdown content as a string.
    """
    html_path = os.path.abspath(html_path)
    html_dir = os.path.dirname(html_path)

    if output_path is None:
        output_path = os.path.splitext(html_path)[0] + ".md"

    # Locate the companion images folder
    # Word uses the pattern: filename_files/
    base_name = os.path.splitext(os.path.basename(html_path))[0]
    images_dir = os.path.join(html_dir, base_name + "_files")
    if not os.path.isdir(images_dir):
        # Try alternate naming: filename.files
        images_dir = os.path.join(html_dir, base_name + ".files")

    # Build icon classification map
    icon_map = build_icon_map(images_dir) if os.path.isdir(images_dir) else {}
    logger.info("Icon map has %d entries", len(icon_map))

    # Read HTML
    raw_bytes = Path(html_path).read_bytes()
    encoding = _detect_encoding(raw_bytes)
    html_text = raw_bytes.decode(encoding, errors="replace")

    # Parse with BeautifulSoup
    soup = BeautifulSoup(html_text, "html.parser")

    # Collect markdown output
    md_lines: list[str] = []

    # Process body
    body = soup.find("body")
    if body is None:
        body = soup  # fallback

    # Track which elements have been processed to avoid duplicates
    _processed: set[int] = set()

    def _process_element(element: Tag, md_out: list[str]) -> None:
        """Recursively walk the DOM tree, emitting markdown for each block element."""
        elem_id = id(element)
        if elem_id in _processed:
            return
        _processed.add(elem_id)

        tag = element.name

        # Headings
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            level = int(tag[1])
            text = _inline_text(element, icon_map, html_dir).strip()
            if text:
                md_out.append("")
                md_out.append(f"{'#' * level} {text}")
                md_out.append("")
            return

        # Tables — convert as a unit, don't recurse into children
        if tag == "table":
            table_md = _convert_table(element, icon_map, html_dir)
            if table_md.strip():
                md_out.append("")
                md_out.append(table_md)
                md_out.append("")
            # Mark all descendant elements as processed
            for desc in element.find_all(True):
                _processed.add(id(desc))
            return

        # Lists
        if tag in ("ul", "ol"):
            md_out.append("")
            items = element.find_all("li", recursive=False)
            for idx, li in enumerate(items, 1):
                text = _inline_text(li, icon_map, html_dir).strip()
                if tag == "ol":
                    md_out.append(f"{idx}. {text}")
                else:
                    md_out.append(f"- {text}")
            md_out.append("")
            for desc in element.find_all(True):
                _processed.add(id(desc))
            return

        # Standalone images
        if tag == "img":
            src = element.get("src", "")
            fname = os.path.basename(src)
            label = icon_map.get(fname)
            if label is None:
                resolved = _resolve_image_src(src, html_dir)
                label = classify_icon(resolved) if resolved else "[IMAGE]"
            md_out.append(label)
            return

        # For divs and other container elements: check if they contain
        # block-level children (headings, tables, other divs, etc.)
        # If so, recurse into children individually.
        block_tags = {"h1", "h2", "h3", "h4", "h5", "h6", "table",
                      "div", "ul", "ol", "p", "img"}
        has_block_children = any(
            isinstance(c, Tag) and c.name in block_tags
            for c in element.children
        )

        if has_block_children:
            # Process children individually to handle mixed content
            for child in element.children:
                if isinstance(child, NavigableString):
                    text = str(child).strip()
                    text = re.sub(r"\s+", " ", text)
                    if text:
                        md_out.append(text)
                elif isinstance(child, Tag):
                    _process_element(child, md_out)
        else:
            # Leaf block element (e.g., a <p> with only inline content)
            text = _inline_text(element, icon_map, html_dir).strip()
            if text:
                md_out.append("")
                md_out.append(text)

    # Kick off recursive processing of body
    for child in body.children:
        if isinstance(child, NavigableString):
            text = str(child).strip()
            if text:
                md_lines.append(text)
        elif isinstance(child, Tag):
            _process_element(child, md_lines)

    # Join and clean up extra blank lines
    markdown = "\n".join(md_lines)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip() + "\n"

    # Write output
    Path(output_path).write_text(markdown, encoding="utf-8")
    logger.info("Wrote markdown to %s", output_path)

    return markdown


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    """CLI entry point for standalone conversion."""
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python -m converters.html_markdown_converter <input.htm> [output.md]")
        sys.exit(1)

    html_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None

    if not os.path.isfile(html_path):
        print(f"Error: File not found: {html_path}")
        sys.exit(1)

    md = convert_html_to_markdown(html_path, output_path)

    # Print summary statistics
    icon_labels = re.findall(r"\[(?:GREEN|YELLOW|RED|BLUE|GRAY|NOT_RATED|GREEN_BAR|RED_BAR|YELLOW_BAR|GRAY_BAR|IMAGE|CHART|SEPARATOR)\]", md)
    from collections import Counter
    counts = Counter(icon_labels)

    print(f"\nConversion complete!")
    print(f"  Output: {output_path or os.path.splitext(html_path)[0] + '.md'}")
    print(f"  Total icon labels inserted: {len(icon_labels)}")
    for label, count in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {label}: {count}")


if __name__ == "__main__":
    main()
