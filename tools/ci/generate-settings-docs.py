#!/usr/bin/env python3
"""Generate settings schema documentation from settings definitions.

This script parses the settings dataclasses and generates markdown documentation.
Can be run with --check to verify against reference/config.md
"""

from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Any


@dataclass
class FieldInfo:
    """Information about a settings field."""

    name: str
    field_type: str
    default: Any
    category: str
    description: str = ""


@dataclass
class SettingClassInfo:
    """Information about a settings dataclass."""

    name: str
    category: str
    description: str
    fields: list[FieldInfo]


# Mapping of category to display name and order
CATEGORY_ORDER = {
    "general": ("General", 1),
    "transcription": ("Transcription", 2),
    "audio": ("Audio", 3),
    "refiner": ("Refiner", 4),
    "hotkey": ("Hotkey", 5),
    "coach": ("Coach", 6),
    "advanced": ("Advanced", 7),
}

# Type mapping from Python types to readable types
TYPE_MAPPING = {
    "str": "string",
    "int": "integer",
    "float": "float",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "Any": "any",
}


def get_type_name(annotation: Any) -> str:
    """Get readable type name from annotation."""
    if hasattr(annotation, "__name__"):
        return TYPE_MAPPING.get(annotation.__name__, annotation.__name__)
    elif hasattr(annotation, "__origin__"):
        origin = annotation.__origin__
        if origin is list:
            args = getattr(annotation, "__args__", ())
            if args:
                inner = get_type_name(args[0])
                return f"array<{inner}>"
            return "array"
        elif origin is dict:
            return "object"
    return "any"


def extract_defaults_from_registry() -> dict[str, Any]:
    """Extract default values from SETTINGS_REGISTRY by importing the module."""
    try:
        # Add app to path if needed
        app_dir = Path(__file__).parent.parent.parent / "app"
        if str(app_dir.parent) not in sys.path:
            sys.path.insert(0, str(app_dir.parent))

        from app.config.settings import SETTINGS_REGISTRY

        defaults = {}
        for name, defn in SETTINGS_REGISTRY.items():
            defaults[name] = defn.default
        return defaults
    except Exception as exc:
        print(f"Warning: Could not import SETTINGS_REGISTRY: {exc}", file=sys.stderr)
        return {}


def parse_settings_registry(file_path: Path) -> list[SettingClassInfo]:
    """Parse settings from SETTINGS_REGISTRY by importing the module."""
    import sys
    from pathlib import Path as P

    repo_root = P(__file__).parent.parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    try:
        from app.config.settings import SETTINGS_REGISTRY

        classes_by_category = {}

        for name, defn in SETTINGS_REGISTRY.items():
            category = defn.category

            if category not in classes_by_category:
                classes_by_category[category] = SettingClassInfo(
                    name=category.title() + "Settings",
                    category=category,
                    description=category.title() + " settings.",
                    fields=[],
                )

            field_type_map = {
                "string": "string",
                "number": "number",
                "boolean": "boolean",
                "enum": "string",
                "range": "number",
                "object": "object",
                "array": "array",
            }
            field_type = field_type_map.get(defn.type, defn.type)

            field_info = FieldInfo(
                name=name,
                field_type=field_type,
                default=defn.default,
                category=category,
                description="",
            )
            classes_by_category[category].fields.append(field_info)

        return list(classes_by_category.values())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return []


def parse_settings_dataclasses(file_path: Path) -> list[SettingClassInfo]:
    """Parse settings dataclasses from the settings_manager.py file."""
    content = file_path.read_text(encoding="utf-8")
    tree = ast.parse(content)

    classes = []
    category_map = {
        "GeneralSettings": "general",
        "TranscriptionSettings": "transcription",
        "AudioSettings": "audio",
        "RefinerSettings": "refiner",
        "HotkeySettings": "hotkey",
        "CoachSettings": "coach",
        "AdvancedSettings": "advanced",
    }

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_dataclass = any(
                decorator.id == "dataclass"
                for decorator in node.decorator_list
                if isinstance(decorator, ast.Name)
            )

            if not is_dataclass:
                continue

            class_name = node.name
            if class_name not in category_map:
                continue

            category = category_map[class_name]
            description = ""

            # Get docstring
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                doc = node.body[0].value
                description = str(doc.value or "").strip()

            fields_list = []

            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    field_name = item.target.id
                    field_type = "any"
                    if item.annotation:
                        if isinstance(item.annotation, ast.Name):
                            field_type = TYPE_MAPPING.get(item.annotation.id, item.annotation.id)
                        elif isinstance(item.annotation, ast.Subscript):
                            if isinstance(item.annotation.value, ast.Name):
                                base = item.annotation.value.id
                                if base == "list":
                                    field_type = "array"
                                elif base == "dict":
                                    field_type = "object"

                    # Extract setting name from lambda default_factory
                    setting_ref = None
                    if item.value and isinstance(item.value, ast.Call):
                        for keyword in item.value.keywords:
                            if keyword.arg == "default_factory":
                                if isinstance(keyword.value, ast.Lambda):
                                    # Try to extract setting name from get_setting("name").default
                                    body = keyword.value.body
                                    if isinstance(body, ast.Attribute) and body.attr == "default":
                                        if isinstance(body.value, ast.Call):
                                            call = body.value
                                            if (
                                                isinstance(call.func, ast.Name)
                                                and call.func.id == "get_setting"
                                            ):
                                                if call.args and isinstance(
                                                    call.args[0], ast.Constant
                                                ):
                                                    setting_ref = str(call.args[0].value)

                    if setting_ref:
                        default_value = f"__REF:{setting_ref}__"
                    else:
                        default_value = "<computed>"

                    fields_list.append(
                        FieldInfo(
                            name=field_name,
                            field_type=field_type,
                            default=default_value,
                            category=category,
                            description="",
                        )
                    )

            classes.append(
                SettingClassInfo(
                    name=class_name,
                    category=category,
                    description=description,
                    fields=fields_list,
                )
            )

    return classes


def resolve_defaults(classes: list[SettingClassInfo], registry_defaults: dict[str, Any]) -> None:
    """Resolve default values from registry."""
    for cls in classes:
        for field in cls.fields:
            if (
                isinstance(field.default, str)
                and field.default.startswith("__REF:")
                and field.default.endswith("__")
            ):
                setting_name = field.default[6:-2]
                if setting_name in registry_defaults:
                    field.default = registry_defaults[setting_name]
                elif "[" in setting_name:
                    # Handle coach_overrides["tone"] pattern
                    base = setting_name.split("[")[0]
                    if base in registry_defaults:
                        base_val = registry_defaults[base]
                        if isinstance(base_val, dict):
                            # Extract key
                            import re

                            match = re.search(r'\["([^"]+)"\]|\[\'([^\']+)\'\]', setting_name)
                            if match:
                                key = match.group(1) or match.group(2)
                                if key in base_val:
                                    field.default = base_val[key]
                else:
                    field.default = f"<{setting_name}>"


def format_default_for_display(default: Any) -> str:
    """Format a default value for display in markdown."""
    if default is None:
        return "null"
    elif isinstance(default, bool):
        return str(default)
    elif isinstance(default, str):
        if len(default) > 40:
            return repr(default[:37] + "...")
        return repr(default)
    elif isinstance(default, float):
        # Round to avoid floating point precision issues
        rounded = round(default, 10)
        # Format with at least one decimal place for floats
        s = str(rounded)
        if "." in s:
            s = s.rstrip("0").rstrip(".")
            if "." not in s:
                s += ".0"
        return s
    elif isinstance(default, int):
        return str(default)
    elif isinstance(default, (list, dict)):
        if not default:
            return repr(default)
        return "*computed*"
    elif isinstance(default, str) and default.startswith("<") and default.endswith(">"):
        return f"*{default[1:-1]}*"
    return repr(default)


def generate_complete_documentation(classes: list[SettingClassInfo]) -> str:
    """Generate complete documentation with registry values."""
    lines = []

    sorted_classes = sorted(
        classes, key=lambda c: CATEGORY_ORDER.get(c.category, (c.category, 99))[1]
    )

    for cls in sorted_classes:
        display_name = CATEGORY_ORDER.get(cls.category, (cls.category, 0))[0]
        lines.append(f"## {display_name} Settings")
        lines.append("")
        if cls.description:
            lines.append(cls.description)
            lines.append("")

        lines.append("| Field | Type | Default | Description |")
        lines.append("|-------|------|---------|-------------|")

        for field in cls.fields:
            default = format_default_for_display(field.default)
            default = str(default).replace("|", "\\|")
            lines.append(f"| `{field.name}` | {field.field_type} | {default} | |")

        lines.append("")

    return "\n".join(lines)


def load_existing_config(config_path: Path) -> str:
    """Load existing config and extract generated section."""
    if not config_path.exists():
        return ""

    content = config_path.read_text(encoding="utf-8")

    start_marker = "<!-- GENERATED: settings-schema -->"
    end_marker = "<!-- END GENERATED -->"

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 or end_idx == -1:
        return ""

    return content[start_idx + len(start_marker) : end_idx].strip()


def check_against_reference(generated: str, config_path: Path) -> bool:
    """Check generated content against reference config."""
    existing = load_existing_config(config_path)

    if not existing:
        print(f"ERROR: Could not find generated section in {config_path}")
        return False

    gen_lines = [line.rstrip() for line in generated.strip().split("\n")]
    exist_lines = [line.rstrip() for line in existing.strip().split("\n")]

    if gen_lines != exist_lines:
        print("ERROR: Generated documentation does not match reference!")
        print("\n--- Diff ---")

        for i, (g, e) in enumerate(zip(gen_lines, exist_lines)):
            if g != e:
                print(f"Line {i + 1}:")
                print(f"  Generated: {g!r}")
                print(f"  Existing:  {e!r}")

        if len(gen_lines) != len(exist_lines):
            print(f"\nLength mismatch: {len(gen_lines)} vs {len(exist_lines)}")
            max_lines = max(len(gen_lines), len(exist_lines))
            for i in range(min(len(gen_lines), len(exist_lines)), max_lines):
                if i < len(gen_lines):
                    print(f"Extra generated line {i + 1}: {gen_lines[i]!r}")
                else:
                    print(f"Extra existing line {i + 1}: {exist_lines[i]!r}")

        return False

    print("SUCCESS: Documentation is up to date!")
    return True


def main():
    parser = argparse.ArgumentParser(description="Generate settings schema documentation")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if documentation matches reference/config.md",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output file path (default: print to stdout)",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("docs/reference/config.md"),
        help="Reference config file for --check",
    )
    parser.add_argument(
        "--settings-manager",
        type=Path,
        default=Path("app/config/settings.py"),
        help="Path to settings.py (settings registry)",
    )

    args = parser.parse_args()

    # Parse settings registry
    classes = parse_settings_registry(args.settings_manager)

    # Generate documentation
    generated = generate_complete_documentation(classes)

    if args.check:
        success = check_against_reference(generated, args.reference)
        sys.exit(0 if success else 1)

    if args.output:
        args.output.write_text(generated, encoding="utf-8")
        print(f"Documentation written to {args.output}")
    else:
        print(generated)


if __name__ == "__main__":
    main()
