# Google Chat plugin

A local Google Chat MCP server for Codex, Claude Code, and Claude Desktop. It reads spaces and messages and can send plain-text messages or strict replies to threads after the user authorizes the destination and content.

The integration runs on the user's machine and uses their Google OAuth Desktop client and account. OAuth client files and refresh tokens stay outside this repository in `~/.config/google-chat-plugin/` (or the directory named by `GOOGLE_CHAT_PLUGIN_HOME`). On POSIX, the token directory uses owner-only permissions (`0700`) and token files are atomically written with owner-only permissions (`0600`). On Windows, the plugin relies on the current user's profile ACL inheritance; verify that ACL if the profile is shared. This plugin does not copy data from another local MCP installation.

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- A Google Cloud project with the Google Chat API enabled and a Desktop OAuth client
- `npm` and the MCPB CLI only when building the Claude Desktop `.mcpb` package

Install dependencies from the pinned lockfile:

```sh
./scripts/setup.sh
```

In Google Cloud, create/download a Desktop app OAuth JSON. Keep that file outside the repository. Then sign in for reading:

```sh
uv run --project . --frozen google-chat-plugin login --credentials /path/to/client_secret.json
```

This requests only `chat.spaces.readonly` and `chat.messages.readonly`. Reading works with a prior read-only refresh token. To explicitly add message sending later, run the same login command with `--enable-send` and consent to the extra `chat.messages.create` scope:

```sh
uv run --project . --frozen google-chat-plugin login --enable-send --credentials /path/to/client_secret.json
```

## Tools

- `list_spaces`: paginated spaces visible to the signed-in user.
- `list_messages`: paginated messages, with optional time and same-space thread filters.
- `get_message`: one message by resource name.
- `send_message`: plain text only. Supply a canonical UUID in `request_id`; Google uses it to make retries idempotent. Reusing the UUID returns the original message, even if a later request changes the body. To reply, supply a `thread_name` from the same space. The server uses `REPLY_MESSAGE_OR_FAIL`, checks that the target is a named space, and never silently turns a failed reply into a new thread.

The server rejects malformed resource names, cross-space threads, empty or oversized text, and invalid UUIDs before sending. Chat content is untrusted input; the included skill says not to follow instructions found in messages. A send requires the user's direct authorization for both the exact target and exact text. When the user's request already provides both, the skill does not require an extra confirmation.

## Codex

The repository includes the portable Agent Plugins files (`plugin.json`, `mcp.json`) and the Codex compatibility fallback (`.codex-plugin/plugin.json`, `.mcp.json`). They launch the local server with `uv`, resolve the project from Codex's `PLUGIN_ROOT`, and run in stdio mode. Install from the repository marketplace with:

```sh
codex plugin marketplace add antstudiocz/google-chat-plugin
codex plugin add google-chat-plugin@antstudio-google-chat
```

Start a new conversation after installing or changing a plugin.

Codex's universal public plugin directory requires a remotely hosted HTTPS MCP endpoint for public submission. This repository provides local stdio packages and does not claim directory listing or remote hosting.

## Claude Code

The root `.claude-plugin/plugin.json` is a Claude Code plugin manifest, and `.claude-plugin/marketplace.json` points at this GitHub repository. With Claude Code installed, register the marketplace and install the plugin:

```sh
claude plugin marketplace add antstudiocz/google-chat-plugin
claude plugin install google-chat-plugin@antstudio-google-chat
```

Claude Code needs `uv` on its PATH. For a checkout used directly during development, validate it with `claude plugin validate .`; plugin installation and tool availability still need to be checked in the target Claude Code host.

## Claude Desktop

Build a real MCP Bundle (`.mcpb`) using the official MCPB CLI. The bundle uses MCPB's UV runtime so it carries the pinned `pyproject.toml` and `uv.lock` rather than depending on a machine-specific Python environment:

```sh
npm ci
npm run build:mcpb
```

Open `dist/google-chat-plugin.mcpb` in Claude Desktop to install it. If MCPB installation is unavailable in a particular host version, use the ordinary local MCP config in `docs/claude-desktop.md`. The fallback requires `uv` and does not change any existing server configuration automatically.

## Validation and development

```sh
uv run --project . --all-extras --frozen pytest
uv run --project . --all-extras --frozen ruff check .
uv run --project . --frozen python -m google_chat_plugin.server --help
npm run validate:mcpb
npm run build:mcpb
```

Tests use mocked Google API calls. They do not perform live OAuth or send messages. Packaging checks validate manifests and inspect the actual MCPB archive for required files and excluded local credential material.

## Official references

- [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins) — portable root manifests, Codex fallback, marketplaces, stdio configuration, and the HTTPS requirement for universal-directory submissions.
- [OpenAI: MCP connections](https://developers.openai.com/api/docs/guides/agents-api/tools/mcp) — local stdio fields and execution context.
- [Claude Code: Plugin manifest reference](https://code.claude.com/docs/en/plugins-reference) — `.claude-plugin/plugin.json`, MCP servers, and plugin-root variables.
- [Claude Code: Create a marketplace](https://code.claude.com/docs/en/plugin-marketplaces) — GitHub plugin sources and marketplace installation.
- [MCPB specification](https://github.com/modelcontextprotocol/mcpb/blob/main/MANIFEST.md) and [CLI](https://github.com/modelcontextprotocol/mcpb/blob/main/CLI.md) — `.mcpb` manifests, UV runtime, validation, and packing.
- [Google Chat `spaces.messages.create`](https://developers.google.com/workspace/chat/api/reference/rest/v1/spaces.messages/create) — send scope, request ID idempotency, thread reply behavior, and message size.

## Release limits

The MCPB archive is unsigned and has been validated and built with the official CLI, but has not been loaded in a Claude Desktop UI. Client-version behavior and Google OAuth consent remain to be checked in the user's host. The locked MCPB build CLI currently has upstream-reported issues in its dev-only dependency tree with no npm fix available; those npm packages are not included in the seven-file `.mcpb` archive. See [packaging security notes](docs/security-notes.md).

## Security

Never commit OAuth client JSON, tokens, `.env` files, logs, or chat exports. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
