"""
ZIP extractor for EWA HTML reports.

EWA HTML exports from Word are typically distributed as a ZIP containing:
  - A single .htm or .html file (the report)
  - A companion folder ({stem}_files/ or {stem}.files/) with GIF icons and images

Usage:
    html_path, images_dir = extract_ewa_zip(zip_path, extract_dir)
    # html_path  -> Path to the extracted .htm file
    # images_dir -> Path to the companion images dir (or None if not found)
"""

import zipfile
from pathlib import Path


def extract_ewa_zip(zip_path: Path, extract_dir: Path) -> tuple[Path, Path | None]:
    """
    Extract an EWA ZIP archive and locate the HTML file + companion images folder.

    The ZIP is extracted into *extract_dir*.  The function then finds the first
    .htm/.html file (preferring ones at the root of the archive over nested ones)
    and resolves the companion images directory using Word's naming convention:
      {stem}_files/   (most common)
      {stem}.files/   (alternate)

    Args:
        zip_path:    Path to the source .zip file.
        extract_dir: Directory to extract into (created if it does not exist).

    Returns:
        (html_path, images_dir)
        - html_path  : absolute Path to the extracted HTML file
        - images_dir : absolute Path to the companion images directory,
                       or None if no companion directory was found

    Raises:
        ValueError: if no .htm/.html file is found in the archive.
    """
    extract_dir = Path(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)

    # Collect all HTML files; prefer shallower paths (root of archive)
    html_candidates = sorted(
        list(extract_dir.glob("*.htm")) +
        list(extract_dir.glob("*.html")) +
        list(extract_dir.rglob("*.htm")) +
        list(extract_dir.rglob("*.html")),
        key=lambda p: len(p.parts),
    )

    # Deduplicate while preserving order
    seen: set[Path] = set()
    html_files: list[Path] = []
    for p in html_candidates:
        if p not in seen:
            seen.add(p)
            html_files.append(p)

    if not html_files:
        raise ValueError(
            f"No .htm/.html file found in ZIP archive: {zip_path}. "
            "Expected an EWA HTML export with a companion _files/ folder."
        )

    html_path = html_files[0]
    stem = html_path.stem
    parent = html_path.parent

    # Some ZIPs contain an HTML file named like "*_files.htm" alongside the real
    # Word companion folder. Normalize that back to the report stem so downstream
    # markdown/tree filenames stay aligned.
    if stem.endswith("_files"):
        candidate = parent / f"{stem[:-6]}.htm"
        if candidate.exists():
            html_path = candidate
            stem = html_path.stem

    # Resolve companion images directory
    images_dir: Path | None = None
    for candidate in (parent / f"{stem}_files", parent / f"{stem}.files"):
        if candidate.is_dir():
            images_dir = candidate
            break

    return html_path, images_dir
