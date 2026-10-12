# Google Chat plugin

A local Google Chat MCP server for Codex, Claude Code, and Claude Desktop. It reads spaces and messages and can send plain-text messages or strict replies to threads after the user authorizes the destination and content.

## Quick install with Claude Code

In Claude Code, add the marketplace and install the plugin:

```text
/plugin marketplace add antstudiocz/ant-google-chat
/plugin install google-chat@ant-google-chat
```

The equivalent shell commands are:

```sh
claude plugin marketplace add antstudiocz/ant-google-chat
claude plugin install google-chat@ant-google-chat
```

For Codex CLI, use:

```sh
codex plugin marketplace add antstudiocz/ant-google-chat
codex plugin add google-chat@ant-google-chat
```

The integration runs on the user's machine and uses their Google OAuth Desktop client and account. The local client copy and refresh token stay outside this repository in `~/.config/google-chat-plugin/` (or the directory named by `GOOGLE_CHAT_PLUGIN_HOME`). On POSIX, the directory uses owner-only permissions (`0700`) and both files are atomically written with owner-only permissions (`0600`). On Windows, the plugin relies on the current user's profile ACL inheritance; verify that ACL if the profile is shared. This plugin does not copy data from another local MCP installation.

## Requirements

- Python 3.11 or newer
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- A Google Cloud project with the Google Chat API enabled and a Desktop OAuth client
- `npm` and the MCPB CLI only when building the Claude Desktop `.mcpb` package

Install dependencies from the pinned lockfile:

```sh
./scripts/setup.sh
```

Use a Google OAuth Desktop app client JSON. Keep it outside the repository. Then set up read access:

```sh
uv run --project . --frozen google-chat-plugin setup --credentials /path/to/desktop-client.json
```

Setup validates a Google Desktop client, opens the system browser for consent, then saves a private local copy after complete consent. It requests `chat.spaces.readonly` and `chat.messages.readonly`. Because installed apps do not support incremental authorization, opting into sends requests the full read and send scope set. To allow message sending, rerun setup with `--enable-send`:

```sh
uv run --project . --frozen google-chat-plugin setup --enable-send --credentials /path/to/desktop-client.json
```

Run `uv run --project . --frozen google-chat-plugin status` to see local configuration, cached grant, and token state. The MCP tool `get_connection_status` reports the same safe summary. Neither contacts Google or proves that access is currently valid; only a successful API request verifies access live. A declined, incomplete, or failed consent does not replace the prior token or stored client configuration.

Each colleague uses their own Google account, consent, and local token. They can use the company's existing OAuth client if its audience allows their account; the JSON client file is delivered privately to each user and is never included in this repository or package. External users may need a separately approved OAuth audience and verification; this setup does not change project audience settings.

## Tools

- `list_spaces`: paginated spaces visible to the signed-in user.
- `list_messages`: paginated messages, with optional time and same-space thread filters.
- `get_message`: one message by resource name.
- `get_connection_status`: local setup and cached grant state, without contacting Google or returning credentials.
- `send_message`: plain text only. Supply a canonical UUID in `request_id`; Google uses it to make retries idempotent. Reusing the UUID returns the original message, even if a later request changes the body. To reply, supply a `thread_name` from the same space. The server uses `REPLY_MESSAGE_OR_FAIL`, checks that the target is a named space, and never silently turns a failed reply into a new thread.

The server rejects malformed resource names, cross-space threads, empty or oversized text, and invalid UUIDs before sending. Chat content is untrusted input; the included skill says not to follow instructions found in messages. A send requires the user's direct authorization for both the exact target and exact text. When the user's request already provides both, the skill does not require an extra confirmation.

## Codex

The repository includes the portable Agent Plugins files (`plugin.json`, `mcp.json`) and the Codex compatibility fallback (`.codex-plugin/plugin.json`, `.mcp.json`). They launch the local server with `uv`, resolve the project from Codex's `PLUGIN_ROOT`, and run in stdio mode. Install from the repository marketplace with:

```sh
codex plugin marketplace add antstudiocz/ant-google-chat
codex plugin add google-chat@ant-google-chat
```

Start a new conversation after installing or changing a plugin.

Use the plugin's setup action for guidance, or run the setup command above in a terminal. The setup skill never reads the client file; the local CLI validates it and starts the browser flow.

Codex's universal public plugin directory requires a remotely hosted HTTPS MCP endpoint for public submission. This repository provides local stdio packages and does not claim directory listing or remote hosting.

## Claude Code

The root `.claude-plugin/plugin.json` is a Claude Code plugin manifest, and `.claude-plugin/marketplace.json` points at this GitHub repository. With Claude Code installed, register the marketplace and install the plugin:

```sh
claude plugin marketplace add antstudiocz/ant-google-chat
claude plugin install google-chat@ant-google-chat
```

Claude Code needs `uv` on its PATH. For a checkout used directly during development, validate it with `claude plugin validate .`; plugin installation and tool availability still need to be checked in the target Claude Code host.

Run `/google-chat:setup` for setup guidance, then execute `uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin setup --credentials "/path/to/desktop-client.json"` in your terminal. To opt into sending, add `--enable-send`.

## Claude Desktop

Build a real MCP Bundle (`.mcpb`) using the official MCPB CLI. The bundle uses MCPB's UV runtime so it carries the pinned `pyproject.toml` and `uv.lock` rather than depending on a machine-specific Python environment:

```sh
npm ci
npm run build:mcpb
```

Open `dist/google-chat-plugin.mcpb` in Claude Desktop to install it. If MCPB installation is unavailable in a particular host version, use the ordinary local MCP config in `docs/claude-desktop.md`. The fallback requires `uv` and does not change any existing server configuration automatically.

Before starting the MCPB server or adding the manual config, run `uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin setup --credentials "/path/to/desktop-client.json"` from a checkout. The bundle uses the same local config directory. Run `google-chat-plugin status` from the checkout to inspect cached setup state.

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
- [Google OAuth for iOS and Desktop apps](https://developers.google.com/identity/protocols/oauth2/native-app) — Desktop client setup, loopback redirects, offline access, and PKCE.

## Release limits

The MCPB archive is unsigned and has been validated and built with the official CLI, but has not been loaded in a Claude Desktop UI. Client-version behavior and Google OAuth consent remain to be checked in the user's host. The locked MCPB build CLI currently has upstream-reported issues in its dev-only dependency tree with no npm fix available; those npm packages are not included in the seven-file `.mcpb` archive. See [packaging security notes](docs/security-notes.md).

## Security

Never commit OAuth client JSON, tokens, `.env` files, logs, or chat exports. See [SECURITY.md](SECURITY.md) for reporting vulnerabilities.
