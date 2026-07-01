"""Tests for :mod:`omnigent.onboarding.sandboxes.docker`.

Focused on ``_resolve_sandbox_env`` — the per-enterprise credential
resolution seam: a mounted ``<enterprise_id>.json`` supplies VALUES per
enterprise (file wins over the global server env), with a global fallback
when the file/value is absent, and a path-traversal guard on the
(untrusted-ish) ``enterprise_id`` that selects the filename.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnigent.onboarding.sandboxes.docker import (
    MODEL_CREDENTIALS_DIR_ENV_VAR,
    DockerSandboxLauncher,
)


def _write_creds(creds_dir: Path, enterprise_id: str, mapping: dict[str, str]) -> None:
    """Write ``<creds_dir>/<enterprise_id>.json`` as a flat name→value map."""
    creds_dir.mkdir(parents=True, exist_ok=True)
    (creds_dir / f"{enterprise_id}.json").write_text(json.dumps(mapping), encoding="utf-8")


def test_enterprise_file_value_wins_over_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A per-enterprise file value overrides the global server env value."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    _write_creds(tmp_path, "ent-a", {"OPENAI_API_KEY": "sk-ent-a"})

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-a")

    assert resolved == {"OPENAI_API_KEY": "sk-ent-a"}


def test_no_file_falls_back_to_global_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An enterprise with no credential file gets the global env values."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    # No file written for ent-nofile.

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-nofile")

    assert resolved == {"OPENAI_API_KEY": "sk-GLOBAL"}


def test_no_enterprise_uses_global_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No enterprise_id (backward-compatible default) → global env only."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    _write_creds(tmp_path, "ent-a", {"OPENAI_API_KEY": "sk-ent-a"})

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env()

    assert resolved == {"OPENAI_API_KEY": "sk-GLOBAL"}


def test_partial_file_falls_back_per_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Names absent from the file resolve from the global env; present ones win."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-GLOBAL")
    _write_creds(tmp_path, "ent-a", {"OPENAI_API_KEY": "sk-ent-a"})

    launcher = DockerSandboxLauncher(
        env=["OPENAI_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]
    )
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-a")

    assert resolved == {
        "OPENAI_API_KEY": "sk-ent-a",  # file wins
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth-GLOBAL",  # global fallback
    }


def test_name_with_no_value_anywhere_is_not_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A whitelisted name with no file value and no global env is skipped."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    _write_creds(tmp_path, "ent-a", {"OPENAI_API_KEY": "sk-ent-a"})

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY", "GEMINI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-a")

    # GEMINI_API_KEY has no value anywhere → not injected (no empty env).
    assert resolved == {"OPENAI_API_KEY": "sk-ent-a"}
    assert "GEMINI_API_KEY" not in resolved


def test_empty_global_value_not_injected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty global env value is treated as absent (not injected)."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "")

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-none")

    assert resolved == {}


@pytest.mark.parametrize(
    "bad_id",
    [
        "../../etc/x",
        "a/b",
        "..",
        ".",
        "ent a",
        "ent.json",
        "",  # empty is falsy → no file read, global fallback
    ],
)
def test_path_traversal_guard_falls_back_to_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bad_id: str
) -> None:
    """A malformed / traversal enterprise_id reads no file → global fallback."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    # Plant a file OUTSIDE + a decoy the traversal must not reach.
    (tmp_path.parent / "x.json").write_text(
        json.dumps({"OPENAI_API_KEY": "sk-ESCAPED"}), encoding="utf-8"
    )

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id=bad_id)

    # Never reads an arbitrary path; falls back to the global env value.
    assert resolved == {"OPENAI_API_KEY": "sk-GLOBAL"}


def test_bad_json_file_falls_back_to_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A malformed credential file must not crash provision — global fallback."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "ent-a.json").write_text("{ not json", encoding="utf-8")

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-a")

    assert resolved == {"OPENAI_API_KEY": "sk-GLOBAL"}


def test_non_object_json_falls_back_to_global(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file whose top level isn't an object → global fallback, no crash."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "ent-a.json").write_text(json.dumps(["not", "a", "map"]), encoding="utf-8")

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-a")

    assert resolved == {"OPENAI_API_KEY": "sk-GLOBAL"}


def test_non_string_file_value_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-string value in the file is skipped → global fallback for it."""
    monkeypatch.setenv(MODEL_CREDENTIALS_DIR_ENV_VAR, str(tmp_path))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")
    _write_creds(tmp_path, "ent-a", {"OPENAI_API_KEY": 12345})  # type: ignore[dict-item]

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-a")

    assert resolved == {"OPENAI_API_KEY": "sk-GLOBAL"}


def test_missing_creds_dir_env_uses_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no creds dir configured, the default path is used (absent → global)."""
    monkeypatch.delenv(MODEL_CREDENTIALS_DIR_ENV_VAR, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-GLOBAL")

    launcher = DockerSandboxLauncher(env=["OPENAI_API_KEY"])
    # The default /config/model-credentials/ent-a.json almost certainly does
    # not exist in the test env → global fallback, no crash.
    resolved = launcher._resolve_sandbox_env(enterprise_id="ent-a")

    assert resolved == {"OPENAI_API_KEY": "sk-GLOBAL"}
