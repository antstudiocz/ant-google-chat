# Claude Desktop

[Back to the overview](../README.md) · [Google sign-in](setup.md)

## Install the release bundle

1. Download `google-chat-plugin.mcpb` from the [latest release](https://github.com/antstudiocz/ant-google-chat/releases/latest).
2. Open it in Claude Desktop to install the plugin.
3. Complete [Google sign-in](setup.md) before using the read or send tools. A checkout can run the setup CLI; the bundle uses the same private configuration directory.

The bundle is unsigned and has been validated with the official MCPB CLI. Loading it in Claude Desktop's UI remains unverified. If your host version does not support the bundle, use the manual configuration below.

For building a bundle yourself, see [development and packaging](development.md).

## Manual MCP configuration

Install `uv`, clone this repository to a stable local path, and run `./scripts/setup.sh`. Before adding the server, run setup with the bundled project's locked environment. Replace the two paths with your checkout and privately downloaded Desktop client JSON:

```sh
uv run --project "/absolute/path/to/ant-google-chat" --frozen google-chat-plugin setup --credentials "/absolute/path/to/desktop-client.json"
```

This validates the client and opens the system browser for read-only consent. After complete consent, it stores a private local copy. Add the `google-chat` entry below to the existing `mcpServers` object in Claude Desktop's configuration, preserving other entries. Replace `/absolute/path/to/ant-google-chat` with the checkout path:

```json
{
  "mcpServers": {
    "google-chat": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/ant-google-chat",
        "--frozen",
        "python",
        "-m",
        "google_chat_plugin.server"
      ],
      "cwd": "/absolute/path/to/ant-google-chat"
    }
  }
}
```

Keep OAuth client JSON outside the repository. The server keeps its token under `~/.config/google-chat-plugin/` or `GOOGLE_CHAT_PLUGIN_HOME`. Restart Claude Desktop after changing its config. Confirm that all five tools appear before using them, including the local cached connection status. This documents the host configuration shape; it does not claim that a particular Claude Desktop build has loaded the server.

On POSIX, the token directory and file are restricted to the current user. On Windows, storage relies on the current user's profile ACL inheritance; verify that ACL if the profile is shared.

`uv run --project "/absolute/path/to/ant-google-chat" --frozen google-chat-plugin status` reports cached local setup state without contacting Google. To allow sends, rerun setup with `--enable-send`; the full read and send scope set is requested again. A declined or incomplete flow leaves the prior token and client config intact.
