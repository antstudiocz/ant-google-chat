from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def read_json(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_platform_manifests_declare_server_and_plugin_consistently():
    portable = read_json("plugin.json")
    codex = read_json(".codex-plugin/plugin.json")
    claude = read_json(".claude-plugin/plugin.json")
    openai_mcp = read_json("mcp.json")
    codex_mcp = read_json(".mcp.json")

    assert portable["name"] == codex["name"] == claude["name"] == "google-chat-plugin"
    assert openai_mcp["mcpServers"]["google-chat"]["type"] == "stdio"
    assert codex_mcp["mcpServers"]["google-chat"]["command"] == "uv"
    assert claude["mcpServers"]["google-chat"]["command"] == "uv"
    assert "PLUGIN_ROOT" in " ".join(openai_mcp["mcpServers"]["google-chat"]["args"])
    assert "CLAUDE_PLUGIN_ROOT" in " ".join(claude["mcpServers"]["google-chat"]["args"])


def test_mcpb_uses_uv_runtime_and_pinned_project_lock():
    manifest = read_json("manifest.json")
    assert manifest["manifest_version"] == "0.4"
    assert manifest["server"]["type"] == "uv"
    assert (ROOT / "uv.lock").is_file()


def test_built_mcpb_contains_runtime_source_and_excludes_local_secrets():
    bundle = ROOT / "dist/google-chat-plugin.mcpb"
    if not bundle.exists():
        if os.environ.get("REQUIRE_MCPB"):
            pytest.fail("CI must build the MCPB bundle before checking its archive contents")
        pytest.skip("build the MCPB bundle to inspect its archive")
    with zipfile.ZipFile(bundle) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "pyproject.toml" in names
        assert "uv.lock" in names
        assert "src/google_chat_plugin/server.py" in names
        assert not any(
            ".private/" in name or "token.json" in name or "client_secret" in name for name in names
        )


def test_mcpb_staging_uses_a_positive_file_allowlist(tmp_path):
    source = tmp_path / "source"
    stage = tmp_path / "stage"
    (source / "src/google_chat_plugin").mkdir(parents=True)
    (source / "src/google_chat_plugin/server.py").write_text("safe source", encoding="utf-8")
    (source / "src/google_chat_plugin/__init__.py").write_text("safe source", encoding="utf-8")
    for filename in ("manifest.json", "pyproject.toml", "uv.lock", "README.md", "LICENSE"):
        (source / filename).write_text("safe metadata", encoding="utf-8")
    (source / ".env").write_text("sentinel-env-secret", encoding="utf-8")
    (source / ".private").mkdir()
    (source / ".private/token.json").write_text("sentinel-token-secret", encoding="utf-8")
    (source / "oauth/client_secret-prod.json").parent.mkdir(parents=True)
    (source / "oauth/client_secret-prod.json").write_text(
        "sentinel-client-secret", encoding="utf-8"
    )
    (source / "archive/chat-export.json").parent.mkdir(parents=True)
    (source / "archive/chat-export.json").write_text("sentinel-chat-export", encoding="utf-8")
    (source / "src/google_chat_plugin/token.json").write_text(
        "sentinel-nested-token", encoding="utf-8"
    )
    (source / "src/google_chat_plugin/unexpected.py").write_text(
        "sentinel-nested-file", encoding="utf-8"
    )

    import subprocess

    subprocess.run([str(ROOT / "scripts/stage-mcpb.sh"), str(source), str(stage)], check=True)
    paths = {path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_file()}
    assert paths == {
        "LICENSE",
        "README.md",
        "manifest.json",
        "pyproject.toml",
        "uv.lock",
        "src/google_chat_plugin/server.py",
        "src/google_chat_plugin/__init__.py",
    }
    contents = "\n".join(
        path.read_text(encoding="utf-8") for path in stage.rglob("*") if path.is_file()
    )
    assert "sentinel-" not in contents
