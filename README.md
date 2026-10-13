# Google Chat plugin

Use Google Chat from **Codex, Claude Code, or Claude Desktop**. Read spaces and messages, or ask your assistant to send a message on your behalf.

The plugin runs on your computer. Each person signs in with their own Google account; messages are sent only when you authorize the destination and text.

## Install

### Codex

Run in your terminal:

```sh
codex plugin marketplace add antstudiocz/ant-google-chat
codex plugin add google-chat@ant-google-chat
```

Then open a new chat or restart Codex. These commands also register the plugin for the Codex desktop app.

### Claude Code

Run inside Claude Code:

```text
/plugin marketplace add antstudiocz/ant-google-chat
/plugin install google-chat@ant-google-chat
```

### Claude Desktop

Download `google-chat-plugin.mcpb` from the [latest release](https://github.com/antstudiocz/ant-google-chat/releases/latest) and open it in Claude Desktop. See the [Desktop guide](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/claude-desktop.md) for setup and alternatives.

## Connect your Google account

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then follow the plugin's setup guide in Codex or run `/google-chat:setup` in Claude Code.

Your administrator provides the Google OAuth client file privately. You sign in through Google in your browser. Reading is enabled by default; sending needs the additional permission described in the [sign-in guide](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/setup.md).

## Try it

- “Show me the latest messages in the Vývoj space.”
- “Send ‘The release is ready for testing.’ to the Vývoj space.”

## Guides

- [Installation and updates](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/installation.md)
- [Google sign-in and troubleshooting](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/setup.md)
- [Claude Desktop](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/claude-desktop.md)
- [Tools and sending rules](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/tools.md)
- [Development, packaging, and references](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/development.md)
- [Security](https://github.com/antstudiocz/ant-google-chat/blob/main/SECURITY.md) and [packaging notes](https://github.com/antstudiocz/ant-google-chat/blob/main/docs/security-notes.md)
