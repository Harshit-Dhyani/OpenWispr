from __future__ import annotations

from pathlib import Path

from tests._contracts import filtered_call, first_method, instantiate, read_text, resolve_symbol

SESSION_MODULES = [
    "app.storage.session_writer",
    "app.storage.sessions",
    "app.storage.writer",
]

SESSION_SYMBOLS = [
    "SessionWriter",
    "persist_session",
    "write_session",
    "save_session",
]


def test_session_writer_persists_a_local_session_payload(tmp_path: Path):
    target = resolve_symbol(SESSION_MODULES, SESSION_SYMBOLS)
    payload = {
        "session_id": "sess-001",
        "audio_path": r"C:\recordings\demo.wav",
        "transcript": "The quick brown fox.",
        "chunks": [{"text": "The quick brown fox."}],
    }

    if isinstance(target, type):
        instance = instantiate(target, root=tmp_path, output_dir=tmp_path, session_dir=tmp_path)
        writer = first_method(instance, ["write", "persist", "save", "append_session"])
        result = filtered_call(
            writer,
            payload,
            session=payload,
            session_data=payload,
            output_dir=tmp_path,
            root=tmp_path,
            destination=tmp_path,
        )
    else:
        result = filtered_call(
            target,
            payload,
            session=payload,
            session_data=payload,
            output_dir=tmp_path,
            root=tmp_path,
            destination=tmp_path,
        )

    materialized = list(tmp_path.rglob("*"))
    assert materialized, "Expected session persistence to create at least one local artifact."

    files = [path for path in materialized if path.is_file()]
    assert files, "Expected session persistence to materialize at least one file."

    serialized = "\n".join(read_text(path) for path in files)
    assert "sess-001" in serialized
    assert "The quick brown fox." in serialized

    if result is not None and isinstance(result, (str, Path)):
        assert Path(result).exists()
