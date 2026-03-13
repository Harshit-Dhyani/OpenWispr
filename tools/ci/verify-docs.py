#!/usr/bin/env python3
"""
Documentation Quality Gate

Validates documentation frontmatter, inventory sync, and internal links.
Exit code 0 on success, 1 on failure.
"""

import re
import sys
from pathlib import Path

import yaml

DOCS_DIR = Path("docs")
INVENTORY_FILE = DOCS_DIR / "_inventory.yml"
REQUIRED_FRONTMATTER_FIELDS = {"title", "audience", "last_verified", "source_of_truth"}
VALID_AUDIENCES = {"developers", "operators", "security", "all"}
DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def error(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)


def check_frontmatter(file_path: Path) -> list[str]:
    """
    Validate YAML frontmatter in a markdown file.
    Returns list of error messages.
    """
    errors = []
    content = file_path.read_text(encoding="utf-8")

    # Skip non-markdown files
    if file_path.suffix != ".md":
        return errors

    # Skip files that don't need frontmatter (like _style.md, _inventory.yml)
    if file_path.name.startswith("_"):
        return errors

    # Check for frontmatter
    if not content.startswith("---"):
        errors.append(f"{file_path}: Missing frontmatter block (must start with ---)")
        return errors

    # Extract frontmatter
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        errors.append(f"{file_path}: Malformed frontmatter block (no closing ---)")
        return errors

    frontmatter_text = content[3 : 3 + end_match.start()]

    try:
        frontmatter = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError as e:
        errors.append(f"{file_path}: Invalid YAML in frontmatter: {e}")
        return errors

    if not isinstance(frontmatter, dict):
        errors.append(f"{file_path}: Frontmatter must be a YAML mapping")
        return errors

    # Check required fields
    missing_fields = REQUIRED_FRONTMATTER_FIELDS - set(frontmatter.keys())
    if missing_fields:
        errors.append(f"{file_path}: Missing required fields: {', '.join(sorted(missing_fields))}")

    # Validate audience
    if "audience" in frontmatter:
        audience = frontmatter["audience"]
        if audience not in VALID_AUDIENCES:
            errors.append(
                f"{file_path}: Invalid audience '{audience}'. Must be one of: {', '.join(sorted(VALID_AUDIENCES))}"
            )

    # Validate date format (handles both string and date objects from YAML)
    if "last_verified" in frontmatter:
        date = frontmatter["last_verified"]
        if hasattr(date, "strftime"):
            # It's a date object, format as string
            date_str = date.strftime("%Y-%m-%d")
        else:
            date_str = str(date)
        if not DATE_PATTERN.match(date_str):
            errors.append(f"{file_path}: Invalid last_verified format '{date_str}'. Use YYYY-MM-DD")

    # Validate source_of_truth is a list
    if "source_of_truth" in frontmatter:
        sot = frontmatter["source_of_truth"]
        if not isinstance(sot, list):
            errors.append(f"{file_path}: source_of_truth must be a list of paths")
        elif sot:  # If not empty, validate each path exists
            for path in sot:
                if not isinstance(path, str):
                    errors.append(f"{file_path}: source_of_truth entries must be strings")
                    break

    return errors


def check_inventory_sync() -> list[str]:
    """
    Verify all .md files in docs/ are listed in _inventory.yml
    Returns list of error messages.
    """
    errors = []

    if not INVENTORY_FILE.exists():
        errors.append(f"Inventory file not found: {INVENTORY_FILE}")
        return errors

    try:
        inventory = yaml.safe_load(INVENTORY_FILE.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML in {INVENTORY_FILE}: {e}")
        return errors

    if "docs" not in inventory:
        errors.append(f"{INVENTORY_FILE}: Missing 'docs' key")
        return errors

    # Build set of inventoried paths (relative to docs/)
    inventoried_paths = set()
    for doc in inventory.get("docs", []):
        path = doc.get("path", "")
        if path:
            inventoried_paths.add(path)

    # Find all .md files in docs/
    md_files = []
    for md_file in DOCS_DIR.rglob("*.md"):
        # Skip files starting with _
        if md_file.name.startswith("_"):
            continue
        # Get path relative to docs/
        rel_path = md_file.relative_to(DOCS_DIR).as_posix()
        md_files.append(rel_path)

    # Check for missing files in inventory
    for md_file in md_files:
        if md_file not in inventoried_paths:
            errors.append(f"File not in _inventory.yml: {md_file}")

    # Check for orphaned inventory entries
    for inv_path in inventoried_paths:
        full_path = DOCS_DIR / inv_path
        if not full_path.exists():
            errors.append(f"Inventory entry missing file: {inv_path}")

    return errors


def check_links() -> list[str]:
    """
    Validate internal markdown links point to existing files.
    Returns list of error messages.
    """
    errors = []

    for md_file in DOCS_DIR.rglob("*.md"):
        if md_file.name.startswith("_"):
            continue

        content = md_file.read_text(encoding="utf-8")
        rel_dir = md_file.relative_to(DOCS_DIR).parent

        for match in LINK_PATTERN.finditer(content):
            link_text = match.group(1)
            link_target = match.group(2)

            # Skip external links, anchors-only, and mailto
            if link_target.startswith(("http://", "https://", "mailto:")):
                continue
            if link_target.startswith("#"):
                continue

            # Handle relative paths
            if link_target.startswith("../"):
                # Count how many levels up
                parts = link_target.split("/")
                up_levels = sum(1 for p in parts if p == "..")
                remaining = [p for p in parts if p != ".."]
                base = DOCS_DIR
                for _ in range(up_levels - len(rel_dir.parts)):
                    base = base.parent
                target_path = base / "/".join(remaining)
            elif link_target.startswith("./"):
                target_path = DOCS_DIR / rel_dir / link_target[2:]
            else:
                target_path = DOCS_DIR / rel_dir / link_target

            # Remove anchor if present
            target_path_str = str(target_path).split("#")[0]
            target_path = Path(target_path_str)

            if not target_path.exists():
                rel_md = md_file.relative_to(DOCS_DIR)
                errors.append(f"Broken link in {rel_md}: '{link_target}' -> file not found")

    return errors


def main() -> int:
    """
    Run all checks and return exit code.
    """
    all_errors = []

    print("=" * 60)
    print("Documentation Quality Gate")
    print("=" * 60)

    # Check 1: Frontmatter validation
    print("\n[1/3] Validating frontmatter...")
    md_files = [f for f in DOCS_DIR.rglob("*.md") if not f.name.startswith("_")]
    frontmatter_errors = []
    for md_file in md_files:
        frontmatter_errors.extend(check_frontmatter(md_file))

    if frontmatter_errors:
        print(f"  [FAIL] Found {len(frontmatter_errors)} frontmatter error(s)")
        all_errors.extend(frontmatter_errors)
    else:
        print(f"  [PASS] All {len(md_files)} files have valid frontmatter")

    # Check 2: Inventory sync
    print("\n[2/3] Checking inventory sync...")
    sync_errors = check_inventory_sync()
    if sync_errors:
        print(f"  [FAIL] Found {len(sync_errors)} inventory sync error(s)")
        all_errors.extend(sync_errors)
    else:
        print("  [PASS] Inventory is synchronized")

    # Check 3: Link validation
    print("\n[3/3] Validating internal links...")
    link_errors = check_links()
    if link_errors:
        print(f"  [FAIL] Found {len(link_errors)} broken link(s)")
        all_errors.extend(link_errors)
    else:
        print("  [PASS] All internal links are valid")

    # Summary
    print("\n" + "=" * 60)
    if all_errors:
        print(f"FAILURE: {len(all_errors)} error(s) found")
        print("=" * 60)
        for err in all_errors:
            print(f"  - {err}")
        return 1
    else:
        print("SUCCESS: All documentation checks passed")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
