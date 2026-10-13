# Installation and updates

[Back to the overview](../README.md) · [Connect your account](setup.md)

## Requirements

For Codex, Claude Code, or the manual Desktop configuration, install [uv](https://docs.astral.sh/uv/getting-started/installation/) and make sure it is available on your PATH. The plugin requires Python 3.11 or newer and uses a pinned dependency lockfile.

You also need a Google OAuth Desktop client configuration and individual Google consent. For company users, ask your administrator for the client file privately. See [Google sign-in](setup.md); installing the plugin alone does not connect your account.

## Codex CLI and desktop app

Run in your terminal:

```sh
codex plugin marketplace add antstudiocz/ant-google-chat
codex plugin add google-chat@ant-google-chat
```

For the desktop app, restart Codex after these commands. Start a new conversation after installing or updating the plugin, so the host refreshes its tools. Use the plugin's setup guide to connect your account.

To update an existing installation:

```sh
codex plugin marketplace upgrade ant-google-chat
codex plugin add google-chat@ant-google-chat
```

If the marketplace is already registered from another URL for this repository, upgrade the existing registration rather than adding a second one.

## Claude Code

Run inside Claude Code:

```text
/plugin marketplace add antstudiocz/ant-google-chat
/plugin install google-chat@ant-google-chat
```

Or use the equivalent terminal commands:

```sh
claude plugin marketplace add antstudiocz/ant-google-chat
claude plugin install google-chat@ant-google-chat
```

Run `/google-chat:setup` for the sign-in guide. Claude Code needs `uv` on its PATH.

## Claude Desktop

Follow the [Desktop guide](claude-desktop.md) to install the release bundle or use the manual MCP configuration.

## Verify the connection

The plugin exposes five tools, including `get_connection_status`. That tool reports local configuration and cached permissions; a successful read request is what confirms access to Google live. Sending still requires your authorization for the destination and exact text.

The local Codex installation has been exercised through an actual MCP session and Google Chat reads. Native manifests and the Desktop bundle have been validated; loading the bundle in Claude Desktop's UI remains unverified.
