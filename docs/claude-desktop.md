# Claude Desktop MCP configuration fallback

The recommended path is opening `dist/google-chat-plugin.mcpb` in Claude Desktop. This manual fallback is for hosts where MCPB is unavailable.

Install `uv`, clone this repository to a stable local path, and run `./scripts/setup.sh`. Run `google-chat-plugin login` using the bundled project's locked environment, then add this server entry to Claude Desktop's MCP configuration. Replace `/absolute/path/to/google-chat-plugin` with the checkout path:

```json
{
  "mcpServers": {
    "google-chat": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/absolute/path/to/google-chat-plugin",
        "--frozen",
        "python",
        "-m",
        "google_chat_plugin.server"
      ],
      "cwd": "/absolute/path/to/google-chat-plugin"
    }
  }
}
```

Keep OAuth client JSON outside the repository. The server keeps its token under `~/.config/google-chat-plugin/` or `GOOGLE_CHAT_PLUGIN_HOME`. Restart Claude Desktop after changing its config. Confirm that all four tools appear before using them. This documents the host configuration shape; it does not claim that a particular Claude Desktop build has loaded the server.

On POSIX, the token directory and file are restricted to the current user. On Windows, storage relies on the current user's profile ACL inheritance; verify that ACL if the profile is shared.
