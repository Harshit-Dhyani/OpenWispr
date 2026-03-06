#!/usr/bin/env python3
"""
API Documentation Generator for Transcripta

Parses app/api/server.py for route decorators and generates markdown table of routes.
Can be run with --check to verify against docs/api/endpoints.md

Usage:
    python tools/ci/generate-api-docs.py              # Generate docs/api/endpoints.md
    python tools/ci/generate-api-docs.py --check      # Verify docs are up to date
    python tools/ci/generate-api-docs.py --stdout     # Print to stdout
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class RouteInfo:
    method: str
    path: str
    handler: str
    request_model: str | None = None
    response_model: str | None = None
    description: str = ""
    line_no: int = 0


class RouteExtractor(ast.NodeVisitor):
    """Extract FastAPI routes from server.py AST."""

    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.routes: list[RouteInfo] = []
        self.current_decorator: ast.Call | None = None
        self.source_lines = source_path.read_text(encoding="utf-8").split("\n")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        for decorator in node.decorator_list:
            route_info = self._extract_route_info(decorator, node)
            if route_info:
                route_info.line_no = node.lineno
                self.routes.append(route_info)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)  # type: ignore[arg-type]

    def _extract_route_info(
        self, decorator: ast.expr, node: ast.AsyncFunctionDef | ast.FunctionDef
    ) -> RouteInfo | None:
        if not isinstance(decorator, ast.Call):
            return None

        func = decorator.func
        if not isinstance(func, ast.Attribute):
            return None

        method_map = {
            "get": "GET",
            "post": "POST",
            "put": "PUT",
            "delete": "DELETE",
            "websocket": "WebSocket",
        }

        http_method = method_map.get(func.attr)
        if not http_method:
            return None

        path = ""
        for kw in decorator.keywords:
            if kw.arg == "path":
                if isinstance(kw.value, ast.Constant):
                    path = str(kw.value.value)
                    break

        if not path:
            for arg in decorator.args:
                if isinstance(arg, ast.Constant):
                    path = str(arg.value)
                    break

        if not path:
            return None

        # Extract docstring as description
        description = ""
        if (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
        ):
            doc = node.body[0].value.value
            if isinstance(doc, str):
                description = doc.split("\n")[0].strip()

        # Extract request/response models from annotations
        request_model = None
        response_model = None

        # Check for request model in parameters
        for arg in node.args.args:
            if arg.arg == "request" and arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    request_model = arg.annotation.id

        # Check for response model in return annotation
        if node.returns:
            if isinstance(node.returns, ast.Name):
                response_model = node.returns.id
            elif isinstance(node.returns, ast.Subscript) and isinstance(
                node.returns.value, ast.Name
            ):
                if node.returns.value.id == "dict":
                    response_model = "dict[str, Any]"
                elif node.returns.value.id == "StreamingResponse":
                    response_model = "StreamingResponse"

        return RouteInfo(
            method=http_method,
            path=path,
            handler=node.name,
            request_model=request_model,
            response_model=response_model,
            description=description,
        )


def extract_routes(source_path: Path) -> tuple[list[RouteInfo], list[RouteInfo], list[RouteInfo]]:
    """Extract REST, WebSocket, and SSE routes from server.py."""
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    extractor = RouteExtractor(source_path)
    extractor.visit(tree)

    rest_routes: list[RouteInfo] = []
    ws_routes: list[RouteInfo] = []
    sse_routes: list[RouteInfo] = []

    for route in extractor.routes:
        if route.method == "WebSocket":
            ws_routes.append(route)
        elif route.path == "/api/events" or route.path == "/api/transcription/hotkey/events":
            # SSE endpoints identified by StreamingResponse return type
            sse_routes.append(route)
        else:
            rest_routes.append(route)

    return rest_routes, ws_routes, sse_routes


def generate_markdown(
    rest_routes: list[RouteInfo],
    ws_routes: list[RouteInfo],
    sse_routes: list[RouteInfo],
    source_of_truth: list[str],
) -> str:
    """Generate markdown documentation."""
    today = __import__("datetime").date.today().isoformat()

    content = f"""---
title: API Endpoints Reference
audience: developers
last_verified: {today}
source_of_truth:
{chr(10).join(f"  - {src}" for src in source_of_truth)}
---

# API Endpoints Reference

Auto-generated documentation of all API endpoints.

<!-- GENERATED: api-routes -->

## REST Endpoints

| Method | Path | Handler | Request | Response | Description |
|--------|------|---------|---------|----------|-------------|
"""

    for route in sorted(rest_routes, key=lambda r: (r.path, r.method)):
        req = route.request_model or "-"
        resp = route.response_model or "-"
        desc = route.description or "-"
        content += (
            f"| {route.method} | `{route.path}` | `{route.handler}` | {req} | {resp} | {desc} |\n"
        )

    content += """
## WebSocket Endpoints

| Path | Handler | Description |
|------|---------|-------------|
"""

    for route in sorted(ws_routes, key=lambda r: r.path):
        desc = route.description or "-"
        content += f"| `{route.path}` | `{route.handler}` | {desc} |\n"

    content += """
## SSE (Server-Sent Events) Endpoints

| Method | Path | Handler | Response | Description |
|--------|------|---------|----------|-------------|
"""

    for route in sorted(sse_routes, key=lambda r: r.path):
        resp = route.response_model or "-"
        desc = route.description or "-"
        content += f"| {route.method} | `{route.path}` | `{route.handler}` | {resp} | {desc} |\n"

    content += """
<!-- END GENERATED -->

## Manual Sections

### Authentication

Currently, the API does not require authentication. The server is intended to run
locally on the user's machine.

### Common Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| 200 | OK | Request succeeded |
| 400 | Bad Request | Invalid request parameters |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource already exists or state conflict |
| 503 | Service Unavailable | Service not ready or initializing |

### Request/Response Models

Key Pydantic models used in API requests and responses:

**StartSessionRequest**
- `title`: str
- `output_root`: str
- `model_name`: str
- `language_mode`: str
- `capture_source`: "microphone" | "system" | null
- `device_id`: str | null
- `live_mode`: str = "balanced"
- `execution_mode`: str = "auto"

**HotkeyStartRequest**
- `capture_source`: "microphone" | "system" | null
- `device_id`: str | null
- `model_name`: str | null
- `language_mode`: str = "auto"
- `execution_mode`: str = "auto"

**HotkeyStopResponse**
- `session_id`: str | null
- `status`: str = "idle"
- `final_transcription`: str
- `composed_text`: str = ""
- `paste_text`: str = ""
- `refined_transcription`: str | null
- `coach_result`: CoachResult | null
- `duration_ms`: int
- `segment_count`: int

### WebSocket Message Types

WebSocket connections use the following message types:

- `transcription_partial` - Streaming partial transcription
- `transcription_final` - Final transcription segment
- `transcription_segment` - Complete segment with metadata
- `audio_level` - Audio level for visualization
- `audio_spectrum` - Frequency spectrum data
- `settings_update` - Settings change notification
- `health_metrics` - System health metrics
- `session_started` - Session start event
- `session_stopped` - Session stop event
- `hotkey_started` - Hotkey recording started
- `hotkey_stopped` - Hotkey recording stopped
- `hotkey_partial` - Hotkey partial transcription
- `ping` / `pong` - Heartbeat messages

---

*This documentation is auto-generated by `tools/ci/generate-api-docs.py`.*
"""

    return content


def check_docs_uptodate(endpoints_md: Path, generated: str) -> bool:
    """Check if the generated docs match the current file."""
    if not endpoints_md.exists():
        return False

    current = endpoints_md.read_text(encoding="utf-8")

    # Extract generated section from current
    match_current = re.search(
        r"<!-- GENERATED: api-routes -->(.+?)<!-- END GENERATED -->",
        current,
        re.DOTALL,
    )
    match_generated = re.search(
        r"<!-- GENERATED: api-routes -->(.+?)<!-- END GENERATED -->",
        generated,
        re.DOTALL,
    )

    if not match_current or not match_generated:
        return False

    return match_current.group(1).strip() == match_generated.group(1).strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate API endpoint documentation")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if docs are up to date (exit 0 if yes, 1 if no)",
    )
    parser.add_argument(
        "--stdout",
        action="store_true",
        help="Print to stdout instead of writing file",
    )
    parser.add_argument(
        "--server-path",
        type=Path,
        default=Path("app/api/server.py"),
        help="Path to server.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/api/endpoints.md"),
        help="Output path for endpoints.md",
    )
    args = parser.parse_args()

    if not args.server_path.exists():
        print(f"Error: Server file not found: {args.server_path}", file=sys.stderr)
        return 1

    rest_routes, ws_routes, sse_routes = extract_routes(args.server_path)

    source_of_truth = ["app/api/server.py", "app/api/websocket_server.py"]
    generated = generate_markdown(rest_routes, ws_routes, sse_routes, source_of_truth)

    if args.stdout:
        print(generated)
        return 0

    if args.check:
        if check_docs_uptodate(args.output, generated):
            print("[OK] API documentation is up to date")
            return 0
        else:
            print("[FAIL] API documentation is out of date. Run without --check to regenerate.")
            print(f"  Found {len(rest_routes)} REST routes")
            print(f"  Found {len(ws_routes)} WebSocket routes")
            print(f"  Found {len(sse_routes)} SSE routes")
            return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(generated, encoding="utf-8")
    print(f"[OK] Generated {args.output}")
    print(f"  Found {len(rest_routes)} REST routes")
    print(f"  Found {len(ws_routes)} WebSocket routes")
    print(f"  Found {len(sse_routes)} SSE routes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
