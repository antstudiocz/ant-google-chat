---
name: setup
description: Set up the local Google Chat plugin and explain its cached access status.
---

Help the user connect the local Google Chat plugin without handling their OAuth secrets.

1. Explain that the plugin needs a Google OAuth Desktop app client JSON and a Google account consent flow. The user or their administrator can provide an existing company client; this setup does not create a Cloud project or share client files. The OAuth app's audience still controls who can consent.
2. Ask the user to run `uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin setup --credentials "/path/to/desktop-client.json"` from a repository checkout in their own terminal. The command validates the Google Desktop client, opens the system browser for consent, and stores a private local copy after successful consent. It requests read-only scopes by default.
3. Never ask the user to paste, upload, or expose the JSON contents, client secret, access token, or refresh token in chat. Do not read the file or ask the user to copy its contents into a prompt. It stays on their machine.
4. Request sending access only when the user explicitly wants it. Explain that the user can rerun setup with `--enable-send`; Google then requests the full read plus send scope set. The token is replaced only after all requested scopes and a refresh token are received.
5. Suggest `uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin status` to inspect local setup state. It reports a cached grant and does not contact Google; it does not prove that the account or grant is currently valid. The MCP `get_connection_status` tool reports the same local state without exposing credentials.
6. If consent is declined, incomplete, or fails, explain that the prior saved login remains in place. Give only the safe error shown by the CLI. Never claim live access from cached status alone.

After setup, confirm the MCP tools are available. Do not perform a Google Chat read or send as part of setup. Any later send still requires the user's direct authorization for the exact destination and exact text.
