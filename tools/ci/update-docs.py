#!/usr/bin/env python3
"""
Docs Auto-Update Script
Updates all documentation to match current codebase state.
Run this to regenerate API docs, settings schema, and detect drift.
"""

import subprocess
import sys
import re
import yaml
from pathlib import Path
from datetime import datetime

DOCS_DIR = Path("docs")
REPORTS_DIR = Path("reports")
DATE_STR = datetime.now().strftime("%Y-%m-%d")


def run_verify():
    """Run docs verification and return (success, output)."""
    result = subprocess.run(["python", "tools/ci/verify-docs.py"], capture_output=True, text=True)
    return result.returncode == 0, result.stdout + result.stderr


def regenerate_api_docs():
    """Regenerate API endpoints documentation."""
    print("[Phase 2.1] Checking API endpoints...")

    # Check if regeneration needed
    result = subprocess.run(
        ["python", "tools/ci/generate-api-docs.py", "--check"], capture_output=True, text=True
    )

    if result.returncode == 0:
        print("  [PASS] API docs up to date")
        return False, ""

    print("  [UPDATE] Regenerating API docs...")

    # Generate new content
    gen_result = subprocess.run(
        ["python", "tools/ci/generate-api-docs.py"], capture_output=True, text=True
    )

    if gen_result.returncode != 0:
        print(f"  [FAIL] Generation failed: {gen_result.stderr}")
        return False, "generation_failed"

    # Read current file
    endpoints_file = DOCS_DIR / "api" / "endpoints.md"
    content = endpoints_file.read_text()

    # Replace between markers
    new_content = re.sub(
        r"(<!-- GENERATED: api-routes -->\n).*?(\n<!-- END GENERATED -->)",
        r"\1" + gen_result.stdout + r"\2",
        content,
        flags=re.DOTALL,
    )

    # Update last_verified date
    new_content = re.sub(
        r"last_verified: \d{4}-\d{2}-\d{2}", f"last_verified: {DATE_STR}", new_content
    )

    endpoints_file.write_text(new_content)
    print(f"  [DONE] Updated {endpoints_file}")
    return True, "regenerated"


def regenerate_settings_docs():
    """Regenerate settings schema documentation."""
    print("[Phase 2.2] Checking settings schema...")

    result = subprocess.run(
        ["python", "tools/ci/generate-settings-docs.py", "--check"], capture_output=True, text=True
    )

    if result.returncode == 0:
        print("  [PASS] Settings docs up to date")
        return False, ""

    print("  [UPDATE] Regenerating settings docs...")

    gen_result = subprocess.run(
        ["python", "tools/ci/generate-settings-docs.py"], capture_output=True, text=True
    )

    if gen_result.returncode != 0:
        print(f"  [FAIL] Generation failed: {gen_result.stderr}")
        return False, "generation_failed"

    config_file = DOCS_DIR / "reference" / "config.md"
    content = config_file.read_text()

    new_content = re.sub(
        r"(<!-- GENERATED: settings-schema -->\n).*?(\n<!-- END GENERATED -->)",
        r"\1" + gen_result.stdout + r"\2",
        content,
        flags=re.DOTALL,
    )

    new_content = re.sub(
        r"last_verified: \d{4}-\d{2}-\d{2}", f"last_verified: {DATE_STR}", new_content
    )

    config_file.write_text(new_content)
    print(f"  [DONE] Updated {config_file}")
    return True, "regenerated"


def update_inventory():
    """Update inventory with new last_updated date."""
    print("[Phase 5] Updating inventory...")

    inventory_file = DOCS_DIR / "_inventory.yml"
    content = inventory_file.read_text()

    # Update last_updated
    new_content = re.sub(r"last_updated: \d{4}-\d{2}-\d{2}", f"last_updated: {DATE_STR}", content)

    # Update last_verified for changed files
    # (This would track which files were modified)

    inventory_file.write_text(new_content)
    print(f"  [DONE] Updated {inventory_file}")


def generate_report(changes):
    """Generate update report."""
    report_file = REPORTS_DIR / f"docs-update-{DATE_STR}.md"

    report = f"""# Docs Auto-Update Report - {DATE_STR}

## Summary
- Date: {DATE_STR}
- Auto-updates: {len([c for c in changes if c["auto"]])}
- Flagged for review: {len([c for c in changes if not c["auto"]])}

## Changes

| File | Type | Status |
|------|------|--------|
"""

    for change in changes:
        status = "Auto-updated" if change["auto"] else "Flagged"
        report += f"| {change['file']} | {change['type']} | {status} |\n"

    report += f"""
## Verification

```
{run_verify()[1]}
```
"""

    report_file.write_text(report)
    print(f"[DONE] Report saved to {report_file}")


def main():
    print("=" * 60)
    print("Docs Auto-Update")
    print("=" * 60)

    changes = []

    # Phase 1: Verification
    print("[Phase 1] Running verification...")
    success, verify_output = run_verify()
    if success:
        print("  [PASS] All docs up to date")
    else:
        print("  [WARN] Verification found issues (will attempt to fix)")

    # Phase 2: Regenerate
    updated, status = regenerate_api_docs()
    if updated:
        changes.append({"file": "api/endpoints.md", "type": "generated", "auto": True})

    updated, status = regenerate_settings_docs()
    if updated:
        changes.append({"file": "reference/config.md", "type": "generated", "auto": True})

    # Phase 5: Update inventory
    update_inventory()

    # Phase 6: Report
    if changes:
        generate_report(changes)
    else:
        print("\n[RESULT] No updates needed - all docs current")

    # Final verification
    print("\n[Final] Running verification...")
    success, _ = run_verify()

    if success:
        print("[SUCCESS] All docs up to date")
        return 0
    else:
        print("[WARNING] Some issues remain - check output above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
