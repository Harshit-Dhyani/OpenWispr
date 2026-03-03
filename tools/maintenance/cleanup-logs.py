#!/usr/bin/env python3
"""
Log Cleanup Tool for Transcripta
Removes old log files and temporary data

Usage:
    python tools/maintenance/cleanup-logs.py [--days 30] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class CleanupResult:
    """Result of cleanup operation."""

    path: Path
    size_bytes: int
    deleted: bool
    error: str | None = None


class LogCleaner:
    """Clean up old log files."""

    LOG_PATTERNS = [
        "*.log",
        "*.log.*",
        "logs/**/*",
        "tmp/**/*",
        ".cache/**/*.tmp",
        "__pycache__/**/*",
        "*.pyc",
        ".pytest_cache/**/*",
        ".mypy_cache/**/*",
    ]

    def __init__(self, days: int = 30, dry_run: bool = False, verbose: bool = False):
        self.days = days
        self.dry_run = dry_run
        self.verbose = verbose
        self.cutoff_date = datetime.now() - timedelta(days=days)
        self.results: list[CleanupResult] = []

    def _find_files(self, project_root: Path) -> list[Path]:
        """Find files matching cleanup patterns."""
        files_to_check: list[Path] = []

        for pattern in self.LOG_PATTERNS:
            matches = list(project_root.rglob(pattern))
            files_to_check.extend(matches)

        return [f for f in files_to_check if f.is_file()]

    def _should_delete(self, file_path: Path) -> bool:
        """Check if file should be deleted based on age."""
        try:
            stat = file_path.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            return mtime < self.cutoff_date
        except Exception:
            return False

    def cleanup(self, project_root: Path | None = None) -> list[CleanupResult]:
        """Run cleanup operation."""
        if project_root is None:
            project_root = Path.cwd()

        files = self._find_files(project_root)

        if self.verbose:
            print(f"Found {len(files)} files to check")
            print(f"Cutoff date: {self.cutoff_date.strftime('%Y-%m-%d')}")
            if self.dry_run:
                print("DRY RUN - no files will be deleted")

        for file_path in files:
            if self._should_delete(file_path):
                try:
                    size = file_path.stat().st_size

                    if not self.dry_run:
                        file_path.unlink()

                    result = CleanupResult(
                        path=file_path, size_bytes=size, deleted=not self.dry_run
                    )

                    if self.verbose:
                        action = "Would delete" if self.dry_run else "Deleted"
                        print(f"  {action}: {file_path} ({size / 1024:.1f} KB)")

                except Exception as e:
                    result = CleanupResult(
                        path=file_path, size_bytes=0, deleted=False, error=str(e)
                    )
                    if self.verbose:
                        print(f"  Error: {file_path} - {e}")

                self.results.append(result)

        return self.results

    def print_summary(self) -> None:
        """Print cleanup summary."""
        deleted = [r for r in self.results if r.deleted or self.dry_run]
        total_size = sum(r.size_bytes for r in deleted)
        errors = [r for r in self.results if r.error]

        print(f"\n{'=' * 60}")
        print("CLEANUP SUMMARY")
        print(f"{'=' * 60}")
        print(f"Files to delete: {len(deleted)}")
        print(f"Total size: {total_size / 1024 / 1024:.2f} MB")

        if errors:
            print(f"Errors: {len(errors)}")

        if self.dry_run:
            print("\nThis was a dry run. No files were actually deleted.")
            print("Run without --dry-run to delete files.")

    def to_json(self) -> dict:
        """Export results as JSON."""
        deleted = [r for r in self.results if r.deleted or self.dry_run]
        total_size = sum(r.size_bytes for r in deleted)

        return {
            "dry_run": self.dry_run,
            "files_found": len(self.results),
            "files_to_delete": len(deleted),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "files": [
                {
                    "path": str(r.path),
                    "size_bytes": r.size_bytes,
                    "deleted": r.deleted,
                    "error": r.error,
                }
                for r in self.results
            ],
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean up old log files for Transcripta",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/maintenance/cleanup-logs.py --dry-run    # Preview what would be deleted
  python tools/maintenance/cleanup-logs.py --days 7     # Delete files older than 7 days
  python tools/maintenance/cleanup-logs.py              # Delete files older than 30 days
        """,
    )
    parser.add_argument("--days", type=int, default=30, help="Delete files older than N days")
    parser.add_argument("--dry-run", action="store_true", help="Preview without deleting")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")

    args = parser.parse_args()

    cleaner = LogCleaner(
        days=args.days, dry_run=args.dry_run, verbose=args.verbose or not args.json
    )

    cleaner.cleanup()

    if args.json:
        print(json.dumps(cleaner.to_json(), indent=2))
    else:
        cleaner.print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
