from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "app/electron/frontend/src/components/settings/categories.ts",
    *sorted((ROOT / "app/electron/frontend/src/components/settings/sections").glob("*.tsx")),
]

PATTERNS = [
    re.compile(r'title="[^"{][^"]+"'),
    re.compile(r'description="[^"{][^"]+"'),
    re.compile(r'placeholder="[^"{][^"]+"'),
    re.compile(r'label:\s*["\'][A-Za-z][^"\']*["\']'),
    re.compile(r'description:\s*["\'][A-Za-z][^"\']*["\']'),
]

ALLOWLIST_FILES = {
    "app/electron/frontend/src/components/settings/sections/SectionHeader.tsx",
}


def main() -> int:
    violations: list[str] = []
    for path in TARGETS:
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOWLIST_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("//"):
                continue
            for pattern in PATTERNS:
                if pattern.search(line):
                    violations.append(f"{rel}:{line_number}: {stripped}")
                    break

    if violations:
        print("Renderer hardcoded user-facing strings detected:")
        for violation in violations:
            print(f"  {violation}")
        print(
            "Move user-facing copy into app/electron/frontend/src/strings/en.ts and reference it by key."
        )
        return 1

    print("Renderer string check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
