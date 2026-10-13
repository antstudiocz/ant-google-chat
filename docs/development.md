# Development and packaging

[Back to the overview](../README.md) · [Security notes](security-notes.md)

## Local development

The server uses Python 3.11 or newer and `uv`. Install dependencies from the pinned lockfile:

```sh
./scripts/setup.sh
```

Validate from the repository root:

```sh
uv run --project . --all-extras --frozen pytest
uv run --project . --all-extras --frozen ruff check .
uv run --project . --frozen python -m google_chat_plugin.server --help
claude plugin validate .
claude plugin validate .claude-plugin/plugin.json
```

Automated tests use synthetic credentials and mocked Google calls; they do not perform live OAuth or send messages. Packaging checks validate manifests and inspect the actual MCPB archive for required files and excluded local credential material. A separate live pilot has exercised Google consent and read requests; sending permission was granted, but no live test message was sent.

## Host manifests

The portable Agent Plugins files are `plugin.json` and `mcp.json`. The Codex fallback uses `.codex-plugin/plugin.json` and `.mcp.json`. They launch the local server with `uv`, resolve the project from `PLUGIN_ROOT`, and use stdio.

Claude Code uses `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`; its MCP launch uses `CLAUDE_PLUGIN_ROOT`.

Codex's universal public plugin directory requires a remotely hosted HTTPS MCP endpoint. This repository distributes local stdio packages and does not claim a universal-directory listing or remote hosting.

## Build the Claude Desktop bundle

Only bundle maintainers need npm and the official MCPB CLI:

```sh
npm ci
npm run validate:mcpb
npm run build:mcpb
REQUIRE_MCPB=1 uv run --project . --all-extras --frozen pytest tests/test_packaging.py
```

The output is `dist/google-chat-plugin.mcpb`. It uses MCPB's UV runtime and carries the pinned `pyproject.toml` and `uv.lock`, rather than a machine-specific Python environment. A positive allowlist includes seven files; local credentials, development dependencies, and unrelated files are excluded. README links point to GitHub so the bundled copy can still reach the full guides.

The archive is unsigned. It has been validated and built with the official CLI, but loading it in Claude Desktop's UI remains unverified. See the [Desktop guide](claude-desktop.md) for installation and the [packaging security notes](security-notes.md) for the pinned build CLI's development-only dependency advisories.

## Official references

- [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins) — portable manifests, Codex fallback, marketplaces, and host setup.
- [OpenAI: MCP connections](https://developers.openai.com/api/docs/guides/agents-api/tools/mcp) — local stdio fields and execution context.
- [Claude Code: Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference) — manifests, MCP servers, and plugin-root variables.
- [Claude Code: Create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces) — GitHub plugin sources and installation.
- [MCPB specification](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md) and [CLI](https://github.com/modelcontextprotocol/mcpb/blob/main/CLI.md) — manifests, UV runtime, validation, and packing.
- [Google Chat message creation](https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create) — sending semantics.
- [Google Desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app) — client setup, loopback redirects, offline access, and PKCE.
