# Google sign-in and troubleshooting

[Back to the overview](../README.md) · [Installation](installation.md)

Each person signs in with their own Google account and receives their own local token. Never paste OAuth files, client secrets, or tokens into an assistant conversation.

## Get the client configuration

For company users, ask your administrator for the Google OAuth **Desktop app** client JSON through a private channel. Keep it outside the repository. The application's audience must allow your Google account.

If you manage the Google application yourself, you need a Cloud project with the Google Chat API enabled and a Desktop OAuth client. The existing company application is configured for Internal users; this plugin does not widen its audience. External users may need a separately approved audience and verification. This plugin uses the normal Google Chat API and does not require Chat MCP Developer Preview membership.

## Sign in

Use the setup guide in Codex or `/google-chat:setup` in Claude Code. To run setup yourself, use the directory containing the installed plugin's `pyproject.toml`, or clone a checkout:

```sh
git clone https://github.com/antstudiocz/ant-google-chat.git
cd ant-google-chat
```

Replace both paths below with your local plugin directory and private client file:

```sh
uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin setup --credentials "/path/to/desktop-client.json"
```

Setup validates the Desktop client, opens your browser, and requests read access. It saves the local client copy and token only after complete consent. A declined, incomplete, or failed consent leaves your previous token and stored client configuration intact.

## Allow sending

Rerun setup with the extra flag:

```sh
uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin setup --credentials "/path/to/desktop-client.json" --enable-send
```

Google requests the complete read and send permission set. Sending access does not authorize the assistant to choose its own recipients or message text; see [sending rules](tools.md).

Once setup has stored your client configuration, you can sign in again without supplying the file:

```sh
uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin login --enable-send
```

## Check the connection

```sh
uv run --project "/path/to/ant-google-chat" --frozen google-chat-plugin status
```

The MCP tool `get_connection_status` returns the same safe summary. Both inspect cached local state without contacting Google. A cached token or permission is not proof of current access; only a successful API request verifies it live.

- **Not configured or signed in:** run setup with the Desktop client file.
- **Read-only grant:** rerun setup or login with `--enable-send` if you want sending.
- **Expired or revoked access:** sign in again. An expired token with a refresh token may refresh automatically during an API request.
- **Consent or Workspace access denied:** ask your administrator to check the app's audience, Chat API configuration, and Workspace access.
- **Tools missing after installation:** start a new conversation or restart the host.

## Private storage and permissions

The client copy and refresh token stay in `~/.config/google-chat-plugin/`, or the directory named by `GOOGLE_CHAT_PLUGIN_HOME`. On POSIX, the directory is owner-only (`0700`) and both files are atomically written with owner-only permissions (`0600`). On Windows, storage relies on the current user's profile ACL inheritance; verify the ACL if the profile is shared.

The plugin does not copy tokens from another local MCP installation. Do not commit client JSON, tokens, `.env` files, logs, or chat exports.

## OAuth scopes

Read access requests `chat.spaces.readonly` and `chat.messages.readonly`. Sending adds `chat.messages.create`. Installed apps do not support incremental authorization, so opting into sending requests the complete selected scope set again. The plugin preserves effective granted scopes through token refresh, including reduced or empty grants.

See [Google's Desktop OAuth documentation](https://developers.google.com/identity/protocols/oauth2/native-app) for administrator details.
