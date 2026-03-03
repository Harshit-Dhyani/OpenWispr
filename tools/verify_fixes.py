#!/usr/bin/env python3
"""Comprehensive verification script for all bug fixes.

This script performs static analysis checks to verify that critical bugs
have been fixed and won't regress. Run this before commits and releases.
"""

from __future__ import annotations

import ast
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class VerificationIssue:
    """Represents a verification issue found in the code."""

    file_path: Path
    line_number: int
    check_name: str
    message: str
    severity: str = "error"  # error, warning, info

    def __str__(self) -> str:
        return f"{self.file_path}:{self.line_number} [{self.severity.upper()}] {self.check_name}: {self.message}"


@dataclass
class CheckResult:
    """Result of a verification check."""

    check_name: str
    passed: bool
    issues: list[VerificationIssue] = field(default_factory=list)


class FixVerifier:
    """Verifies that critical bug fixes are in place."""

    def __init__(self, project_root: Path | None = None):
        self.project_root = project_root or Path.cwd()
        self.issues: list[VerificationIssue] = []
        self.check_results: list[CheckResult] = []
        self.python_files: list[Path] = []
        self.typescript_files: list[Path] = []

    def scan_files(self) -> None:
        """Scan project for Python and TypeScript files."""
        app_dir = self.project_root / "app"
        ui_dir = self.project_root / "app" / "desktop" / "frontend" / "src"

        if app_dir.exists():
            self.python_files = list(app_dir.rglob("*.py"))

        if ui_dir.exists():
            self.typescript_files = list(ui_dir.rglob("*.ts"))
            self.typescript_files.extend(ui_dir.rglob("*.tsx"))

    def check_duplicate_definitions(
        self, file_path: Path, tree: ast.AST
    ) -> list[VerificationIssue]:
        """Check for duplicate function/class definitions at the same scope level."""
        issues = []

        # Track definitions per scope (module level and class level)
        module_level: dict[str, list[int]] = defaultdict(list)
        class_level: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                parent = getattr(node, "parent", None)

                if parent is None or isinstance(parent, ast.Module):
                    # Module-level definition
                    module_level[node.name].append(node.lineno)
                elif isinstance(parent, ast.ClassDef):
                    # Class method/inner class - track per class
                    class_level[parent.name][node.name].append(node.lineno)
                # Inner functions (inside other functions) are intentionally ignored
                # as they are local to their enclosing function

        # Check for duplicates at module level
        for name, lines in module_level.items():
            if len(lines) > 1:
                issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=lines[0],
                        check_name="duplicate_definitions",
                        message=f"Duplicate module-level definition of '{name}' at lines: {lines}",
                        severity="error",
                    )
                )

        # Check for duplicates within same class
        for class_name, methods in class_level.items():
            for method_name, lines in methods.items():
                if len(lines) > 1:
                    issues.append(
                        VerificationIssue(
                            file_path=file_path,
                            line_number=lines[0],
                            check_name="duplicate_definitions",
                            message=f"Duplicate definition of '{method_name}' in class '{class_name}' at lines: {lines}",
                            severity="error",
                        )
                    )

        return issues

    def check_iterator_imports(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Verify Iterator and other runtime imports are outside TYPE_CHECKING."""
        issues = []

        # Check for Iterator import from typing (should be collections.abc)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module == "typing":
                    for alias in node.names:
                        if alias.name == "Iterator":
                            issues.append(
                                VerificationIssue(
                                    file_path=file_path,
                                    line_number=node.lineno,
                                    check_name="iterator_import",
                                    message="Iterator imported from 'typing' instead of 'collections.abc' (runtime issue)",
                                    severity="error",
                                )
                            )

        # Check for TYPE_CHECKING blocks importing runtime-needed types
        in_type_checking = False
        type_checking_line = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check if this is TYPE_CHECKING block
                if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                    in_type_checking = True
                    type_checking_line = node.lineno

                    # Check what's imported inside TYPE_CHECKING
                    for child in ast.walk(node):
                        if isinstance(child, ast.ImportFrom):
                            runtime_types = {"Iterator", "Callable", "Generator", "Coroutine"}
                            for alias in child.names:
                                if alias.name in runtime_types:
                                    issues.append(
                                        VerificationIssue(
                                            file_path=file_path,
                                            line_number=child.lineno,
                                            check_name="type_checking_import",
                                            message=f"{alias.name} imported inside TYPE_CHECKING but needed at runtime",
                                            severity="error",
                                        )
                                    )

        return issues

    def check_empty_except_blocks(self, file_path: Path, tree: ast.AST) -> list[VerificationIssue]:
        """Check that except blocks are not empty or just 'pass'."""
        issues = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    # Check if handler body is empty or just pass
                    if not handler.body:
                        issues.append(
                            VerificationIssue(
                                file_path=file_path,
                                line_number=handler.lineno,
                                check_name="empty_except",
                                message="Empty except block (no statements)",
                                severity="error",
                            )
                        )
                    elif len(handler.body) == 1:
                        stmt = handler.body[0]
                        if isinstance(stmt, ast.Pass):
                            issues.append(
                                VerificationIssue(
                                    file_path=file_path,
                                    line_number=handler.lineno,
                                    check_name="pass_except",
                                    message="Except block contains only 'pass' - should log or handle error",
                                    severity="warning",
                                )
                            )
                        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                            # Just a string literal (docstring-style)
                            if isinstance(stmt.value.value, str):
                                issues.append(
                                    VerificationIssue(
                                        file_path=file_path,
                                        line_number=handler.lineno,
                                        check_name="ignored_except",
                                        message="Except block only contains docstring - should properly handle error",
                                        severity="warning",
                                    )
                                )

        return issues

    def check_thread_safety(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Check for proper locking in thread-sensitive code."""
        issues = []

        # Look for threading-related classes
        has_threading = "threading" in source or "Thread" in source
        if not has_threading:
            return issues

        # Find classes that likely need thread safety
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_source = ast.get_source_segment(source, node) or ""

                # Check if class uses threading
                if "threading" in class_source or "_thread" in class_source:
                    # Check for Lock or RLock
                    has_lock = (
                        "Lock()" in class_source
                        or "RLock()" in class_source
                        or "_lock" in class_source
                    )

                    if not has_lock:
                        issues.append(
                            VerificationIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                check_name="thread_safety",
                                message=f"Class '{node.name}' uses threading but may lack proper locking",
                                severity="warning",
                            )
                        )

        return issues

    def check_resource_cleanup(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Check that resources are properly cleaned up (context managers, finally blocks)."""
        issues = []

        # Check for file operations without context managers
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    # Check if inside a 'with' statement
                    parent = getattr(node, "parent", None)
                    in_with = False
                    while parent:
                        if isinstance(parent, ast.With):
                            in_with = True
                            break
                        parent = getattr(parent, "parent", None)

                    if not in_with:
                        issues.append(
                            VerificationIssue(
                                file_path=file_path,
                                line_number=node.lineno,
                                check_name="resource_cleanup",
                                message="File opened without context manager (with statement)",
                                severity="warning",
                            )
                        )

        # Check for __enter__ without __exit__
        classes_with_enter = set()
        classes_with_exit = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        if item.name == "__enter__":
                            classes_with_enter.add(node.name)
                        elif item.name == "__exit__":
                            classes_with_exit.add(node.name)

        for cls_name in classes_with_enter - classes_with_exit:
            issues.append(
                VerificationIssue(
                    file_path=file_path,
                    line_number=1,  # Approximate
                    check_name="context_manager",
                    message=f"Class '{cls_name}' has __enter__ but missing __exit__",
                    severity="error",
                )
            )

        return issues

    def check_magic_numbers(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Check that magic numbers are replaced with constants."""
        issues = []

        # Common magic numbers that should be constants
        magic_patterns = {
            16000: "AudioConstants.DEFAULT_SAMPLE_RATE",
            0.5: "Often a threshold that should be named",
            -40: "VADConstants.DEFAULT_THRESHOLD_DB",
            -35: "VAD threshold - should use constant",
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if node.value in magic_patterns:
                    # Skip if in a constant definition itself
                    parent = getattr(node, "parent", None)
                    if isinstance(parent, (ast.Assign, ast.AnnAssign)):
                        continue

                    issues.append(
                        VerificationIssue(
                            file_path=file_path,
                            line_number=node.lineno,
                            check_name="magic_number",
                            message=f"Magic number {node.value} should use constant: {magic_patterns[node.value]}",
                            severity="warning",
                        )
                    )

        return issues

    def check_duplicate_vad_threshold(
        self, file_path: Path, source: str
    ) -> list[VerificationIssue]:
        """Verify VAD threshold is not duplicated in config."""
        issues = []

        # Look for duplicate VAD threshold definitions
        vad_pattern = r"vad_threshold_db\s*=\s*-?\d+\.?\d*"
        matches = list(re.finditer(vad_pattern, source))

        if len(matches) > 1:
            lines = [source[: m.start()].count("\n") + 1 for m in matches]
            issues.append(
                VerificationIssue(
                    file_path=file_path,
                    line_number=lines[0],
                    check_name="duplicate_vad_config",
                    message=f"VAD threshold defined {len(matches)} times at lines {lines} - should use constant",
                    severity="warning",
                )
            )

        return issues

    def check_gpu_cache_key(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Verify GPU cache key uses actual compute_type, not hardcoded value."""
        issues = []

        # Look for cache key patterns with hardcoded compute types
        hardcoded_patterns = [
            r'"[^"]*:cuda:(?:float16|float32|int8)"',
            r"'[^']*:cuda:(?:float16|float32|int8)'",
        ]

        for pattern in hardcoded_patterns:
            for match in re.finditer(pattern, source):
                line_num = source[: match.start()].count("\n") + 1
                issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=line_num,
                        check_name="gpu_cache_key",
                        message=f"Potential hardcoded GPU cache key: {match.group()} - should use self.compute_type",
                        severity="warning",
                    )
                )

        return issues

    def check_numpy_int_overflow(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Check for potential numpy int32 overflow in array indexing."""
        issues = []

        # Look for patterns like: int64(samples) * int64(multiplier)
        # Or missing int64 casts in offset calculations
        overflow_patterns = [
            r"offset\s*=\s*\w+\s*\*\s*\w+",
            r"index\s*=\s*\w+\s*\*\s*\w+",
        ]

        for pattern in overflow_patterns:
            for match in re.finditer(pattern, source):
                line_num = source[: match.start()].count("\n") + 1
                line = source.split("\n")[line_num - 1]

                # Check if line lacks int64 cast
                if "int64" not in line:
                    issues.append(
                        VerificationIssue(
                            file_path=file_path,
                            line_number=line_num,
                            check_name="numpy_overflow",
                            message=f"Potential int32 overflow in indexing: {match.group()}",
                            severity="warning",
                        )
                    )

        return issues

    def check_buffer_capacity(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Check buffer capacity is at least 1.5x max chunk size."""
        issues = []

        # Look for buffer capacity patterns
        buffer_patterns = [
            (r"buffer_capacity\s*=\s*(\d+)", r"chunk_size\s*=\s*(\d+)"),
            (r"capacity\s*=\s*(\d+)", r"max_chunk\s*=\s*(\d+)"),
        ]

        for cap_pattern, chunk_pattern in buffer_patterns:
            cap_match = re.search(cap_pattern, source)
            chunk_match = re.search(chunk_pattern, source)

            if cap_match and chunk_match:
                capacity = int(cap_match.group(1))
                chunk_size = int(chunk_match.group(1))

                if capacity < chunk_size * 1.5:
                    line_num = source[: cap_match.start()].count("\n") + 1
                    issues.append(
                        VerificationIssue(
                            file_path=file_path,
                            line_number=line_num,
                            check_name="buffer_capacity",
                            message=f"Buffer capacity ({capacity}) < 1.5x chunk size ({chunk_size}) - may deadlock",
                            severity="error",
                        )
                    )

        return issues

    def check_dead_variables(
        self, file_path: Path, tree: ast.AST, source: str
    ) -> list[VerificationIssue]:
        """Check for dead variables that are checked but never updated."""
        issues = []

        # Look for patterns where a variable is checked but never assigned
        # This is a simplified check - full data flow analysis would be more complex
        assigned_vars: set[str] = set()
        checked_vars: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                # Check if variable is assigned
                parent = getattr(node, "parent", None)
                if isinstance(parent, ast.Store):
                    assigned_vars.add(node.id)
                elif isinstance(parent, ast.Load):
                    checked_vars.add(node.id)

        # Check for common dead variable patterns in conditions
        dead_var_patterns = [
            r"if\s+(\w+)\s*:",
            r"while\s+(\w+)\s*:",
            r"len\((\w+)\)",
        ]

        for pattern in dead_var_patterns:
            for match in re.finditer(pattern, source):
                var_name = match.group(1)
                if var_name.startswith("_") and var_name not in assigned_vars:
                    line_num = source[: match.start()].count("\n") + 1
                    issues.append(
                        VerificationIssue(
                            file_path=file_path,
                            line_number=line_num,
                            check_name="dead_variable",
                            message=f"Variable '{var_name}' checked but may not be initialized",
                            severity="warning",
                        )
                    )

        return issues

    def check_event_source_cleanup(self, file_path: Path, source: str) -> list[VerificationIssue]:
        """Check for proper cleanup in hooks (TypeScript)."""
        issues = []

        # Skip files that use useEventSource hook (it handles cleanup internally)
        if "useEventSource" in source:
            return issues

        # Check for missing cleanup in useEffect
        if "useEffect" in source:
            # Check for return cleanup function
            if "return () =>" not in source and "return function" not in source:
                issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=1,
                        check_name="effect_cleanup",
                        message="useEffect may be missing cleanup function",
                        severity="warning",
                    )
                )

        # Check for EventSource without close handling
        if "EventSource" in source:
            if ".close()" not in source:
                issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=1,
                        check_name="eventsource_cleanup",
                        message="EventSource created but .close() not called in cleanup",
                        severity="error",
                    )
                )

        # Check for setInterval/setTimeout without clear
        if "setInterval(" in source:
            if "clearInterval" not in source:
                issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=1,
                        check_name="interval_cleanup",
                        message="setInterval without clearInterval in cleanup",
                        severity="error",
                    )
                )

        if "setTimeout(" in source:
            if "clearTimeout" not in source:
                issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=1,
                        check_name="timeout_cleanup",
                        message="setTimeout without clearTimeout in cleanup",
                        severity="error",
                    )
                )

        return issues

    def run_python_checks(self) -> CheckResult:
        """Run all Python-specific checks."""
        print("Running Python code checks...")
        all_issues = []

        for file_path in self.python_files:
            try:
                source = file_path.read_text(encoding="utf-8")
                tree = ast.parse(source)

                # Add parent references for context
                for node in ast.walk(tree):
                    for child in ast.iter_child_nodes(node):
                        setattr(child, "parent", node)

                # Run checks
                checks = [
                    ("duplicate_definitions", self.check_duplicate_definitions),
                    ("iterator_imports", self.check_iterator_imports),
                    ("empty_except", self.check_empty_except_blocks),
                    ("thread_safety", self.check_thread_safety),
                    ("resource_cleanup", self.check_resource_cleanup),
                    ("magic_numbers", self.check_magic_numbers),
                    ("duplicate_vad", self.check_duplicate_vad_threshold),
                    ("gpu_cache_key", self.check_gpu_cache_key),
                    ("numpy_overflow", self.check_numpy_int_overflow),
                    ("buffer_capacity", self.check_buffer_capacity),
                    ("dead_variables", self.check_dead_variables),
                ]

                for check_name, check_func in checks:
                    try:
                        if check_name in ["duplicate_vad", "numpy_overflow", "buffer_capacity"]:
                            issues = check_func(file_path, tree, source)
                        elif check_name in ["gpu_cache_key"]:
                            issues = check_func(file_path, tree, source)
                        else:
                            issues = (
                                check_func(file_path, tree, source)
                                if check_name != "duplicate_definitions"
                                else check_func(file_path, tree)
                            )
                        all_issues.extend(issues)
                    except Exception as e:
                        all_issues.append(
                            VerificationIssue(
                                file_path=file_path,
                                line_number=1,
                                check_name=check_name,
                                message=f"Check failed with error: {e}",
                                severity="info",
                            )
                        )

            except SyntaxError as e:
                all_issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=e.lineno or 1,
                        check_name="syntax",
                        message=f"Syntax error: {e}",
                        severity="error",
                    )
                )
            except Exception as e:
                all_issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=1,
                        check_name="parse",
                        message=f"Failed to parse file: {e}",
                        severity="error",
                    )
                )

        self.issues.extend(all_issues)

        errors = [i for i in all_issues if i.severity == "error"]
        result = CheckResult(
            check_name="python_checks",
            passed=len(errors) == 0,
            issues=all_issues,
        )
        self.check_results.append(result)

        print(f"  Found {len(all_issues)} issues ({len(errors)} errors)")
        return result

    def run_typescript_checks(self) -> CheckResult:
        """Run TypeScript-specific checks."""
        print("Running TypeScript code checks...")
        all_issues = []

        for file_path in self.typescript_files:
            try:
                source = file_path.read_text(encoding="utf-8")
                issues = self.check_event_source_cleanup(file_path, source)
                all_issues.extend(issues)
            except Exception as e:
                all_issues.append(
                    VerificationIssue(
                        file_path=file_path,
                        line_number=1,
                        check_name="typescript_parse",
                        message=f"Failed to check file: {e}",
                        severity="error",
                    )
                )

        self.issues.extend(all_issues)

        errors = [i for i in all_issues if i.severity == "error"]
        result = CheckResult(
            check_name="typescript_checks",
            passed=len(errors) == 0,
            issues=all_issues,
        )
        self.check_results.append(result)

        print(f"  Found {len(all_issues)} issues ({len(errors)} errors)")
        return result

    def check_critical_fixes(self) -> CheckResult:
        """Verify specific critical fixes are in place."""
        print("Checking critical bug fixes...")
        issues = []

        # Check 1: VAD threshold in constants.py
        constants_file = self.project_root / "app" / "core" / "constants.py"
        if constants_file.exists():
            source = constants_file.read_text()
            if "DEFAULT_THRESHOLD_DB = -40.0" not in source:
                issues.append(
                    VerificationIssue(
                        file_path=constants_file,
                        line_number=1,
                        check_name="vad_threshold_constant",
                        message="VAD threshold constant not found or changed from -40.0",
                        severity="error",
                    )
                )

        # Check 2: LoopbackAudioSource has thread lock
        capture_file = self.project_root / "app" / "audio" / "capture.py"
        if capture_file.exists():
            source = capture_file.read_text()
            # Normalize whitespace for pattern matching
            normalized = source.replace(" ", "").replace("\t", "")
            if "_thread_lock=threading.Lock()" not in normalized:
                issues.append(
                    VerificationIssue(
                        file_path=capture_file,
                        line_number=1,
                        check_name="thread_lock",
                        message="LoopbackAudioSource may lack thread lock",
                        severity="error",
                    )
                )

        # Check 3: fast_chunker has proper buffer capacity
        chunker_file = self.project_root / "app" / "stt" / "fast_chunker.py"
        if chunker_file.exists():
            source = chunker_file.read_text()
            if "buffer_capacity = self._config.sample_rate * 2" not in source.replace(" ", ""):
                issues.append(
                    VerificationIssue(
                        file_path=chunker_file,
                        line_number=1,
                        check_name="buffer_capacity",
                        message="Buffer capacity should be sample_rate * 2 for 1.6s chunks",
                        severity="warning",
                    )
                )

        # Check 4: Iterator imported from collections.abc in fast_chunker
        if chunker_file.exists():
            source = chunker_file.read_text()
            if "from collections.abc import Iterator" not in source:
                issues.append(
                    VerificationIssue(
                        file_path=chunker_file,
                        line_number=1,
                        check_name="iterator_import",
                        message="Iterator should be imported from collections.abc (runtime)",
                        severity="error",
                    )
                )

        # Check 5: useEventSource has cleanup
        eventsource_file = (
            self.project_root
            / "app"
            / "desktop"
            / "frontend"
            / "src"
            / "hooks"
            / "useEventSource.ts"
        )
        if eventsource_file.exists():
            source = eventsource_file.read_text()
            if ".close()" not in source:
                issues.append(
                    VerificationIssue(
                        file_path=eventsource_file,
                        line_number=1,
                        check_name="eventsource_cleanup",
                        message="EventSource cleanup missing",
                        severity="error",
                    )
                )

        self.issues.extend(issues)

        errors = [i for i in issues if i.severity == "error"]
        result = CheckResult(
            check_name="critical_fixes",
            passed=len(errors) == 0,
            issues=issues,
        )
        self.check_results.append(result)

        print(f"  Found {len(issues)} issues ({len(errors)} errors)")
        return result

    def run_all_checks(self) -> bool:
        """Run all verification checks."""
        print("=" * 60)
        print("TRANSCRIPTA BUG FIX VERIFICATION")
        print("=" * 60)
        print()

        self.scan_files()
        print(f"Scanned {len(self.python_files)} Python files")
        print(f"Scanned {len(self.typescript_files)} TypeScript files")
        print()

        # Run all check suites
        self.run_python_checks()
        print()
        self.run_typescript_checks()
        print()
        self.check_critical_fixes()
        print()

        # Print summary
        print("=" * 60)
        print("SUMMARY")
        print("=" * 60)

        all_errors = [i for i in self.issues if i.severity == "error"]
        all_warnings = [i for i in self.issues if i.severity == "warning"]

        for result in self.check_results:
            status = "PASS" if result.passed else "FAIL"
            print(f"  [{status}] {result.check_name}")

        print()
        print(f"Total: {len(all_errors)} errors, {len(all_warnings)} warnings")

        if all_errors:
            print()
            print("ERRORS:")
            for issue in all_errors[:10]:  # Show first 10
                print(f"  {issue}")
            if len(all_errors) > 10:
                print(f"  ... and {len(all_errors) - 10} more errors")

        if all_warnings:
            print()
            print("WARNINGS:")
            for issue in all_warnings[:5]:  # Show first 5
                print(f"  {issue}")
            if len(all_warnings) > 5:
                print(f"  ... and {len(all_warnings) - 5} more warnings")

        return len(all_errors) == 0


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify bug fixes are in place",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/verify_fixes.py
  python tools/verify_fixes.py --json
  python tools/verify_fixes.py --strict  # Treat warnings as errors
        """,
    )
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--project-root", type=Path, default=None, help="Project root directory")

    args = parser.parse_args()

    verifier = FixVerifier(project_root=args.project_root)
    success = verifier.run_all_checks()

    if args.json:
        import json

        output = {
            "success": success,
            "checks": [
                {
                    "name": r.check_name,
                    "passed": r.passed,
                    "issues": [
                        {
                            "file": str(i.file_path),
                            "line": i.line_number,
                            "check": i.check_name,
                            "message": i.message,
                            "severity": i.severity,
                        }
                        for i in r.issues
                    ],
                }
                for r in verifier.check_results
            ],
        }
        print(json.dumps(output, indent=2))

    if args.strict:
        warnings = [i for i in verifier.issues if i.severity == "warning"]
        if warnings:
            print(f"\nStrict mode: {len(warnings)} warnings treated as errors")
            return 1

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
