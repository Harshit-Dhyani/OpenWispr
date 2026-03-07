from __future__ import annotations

import os
from pathlib import Path, PureWindowsPath


def test_windows_style_session_paths_round_trip_cleanly(tmp_path: Path):
    session_path = PureWindowsPath(
        r"C:\Users\tester\AppData\Local\OpenWispr\sessions\demo-001.json"
    )
    assert session_path.drive == "C:"
    assert session_path.parts[-2:] == ("sessions", "demo-001.json")

    mirrored = tmp_path / "sessions" / "demo-001.json"
    mirrored.parent.mkdir(parents=True, exist_ok=True)
    mirrored.write_text('{"session_id":"demo-001"}', encoding="utf-8")

    assert mirrored.exists()
    assert "\\" in str(session_path)


def test_local_temp_workspace_is_writable_for_offline_runs(tmp_path: Path):
    artifact = tmp_path / "openwispr-local" / "run.log"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("ok", encoding="utf-8")

    assert artifact.exists()
    assert artifact.read_text(encoding="utf-8") == "ok"
    assert os.path.isabs(str(artifact))
