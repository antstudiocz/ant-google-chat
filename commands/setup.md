---
description: Set up the local Google Chat plugin
---

Guide the user through setting up the local Google Chat plugin.

- Ask them to run `uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin setup --credentials "/path/to/desktop-client.json"` from a repository checkout in their own terminal. Do not ask them to paste or upload OAuth client JSON, client secrets, or tokens.
- Explain that setup validates the Desktop client, opens their system browser for Google consent, and saves a private local copy after complete consent. Read-only scopes are requested by default.
- Only include `--enable-send` if the user explicitly wants message sending. That flow requests the complete read and send scope set.
- After consent, suggest `uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin status`. Explain that status reports cached local grant state and does not check current Google access.
- Never inspect, print, or request the contents of the private OAuth file or token. Setup does not read or send messages.
