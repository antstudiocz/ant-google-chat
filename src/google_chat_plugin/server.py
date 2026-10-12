"""Local stdio MCP server for reading and explicitly authorized Google Chat sends."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from google.auth.exceptions import GoogleAuthError, RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

READ_SCOPES = (
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.messages.readonly",
)
SEND_SCOPE = "https://www.googleapis.com/auth/chat.messages.create"
RESOURCE_RE = re.compile(r"^spaces/[A-Za-z0-9._-]+(?:/(?:threads|messages)/[A-Za-z0-9._-]+)?$")
CONFIG_DIR = Path(
    os.environ.get("GOOGLE_CHAT_PLUGIN_HOME", "~/.config/google-chat-plugin")
).expanduser()
TOKEN_PATH = CONFIG_DIR / "token.json"
DEFAULT_CREDENTIALS_PATH = CONFIG_DIR / "client_secret.json"

mcp = FastMCP("google-chat")


def _secure_config_dir() -> None:
    CONFIG_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        CONFIG_DIR.chmod(0o700)


def _atomic_write_private_file(path: Path, contents: str) -> None:
    _secure_config_dir()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}-", dir=CONFIG_DIR)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "posix":
            temporary.chmod(0o600)
        temporary.replace(path)
        if os.name == "posix":
            path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_token(contents: str) -> None:
    _atomic_write_private_file(TOKEN_PATH, contents)


def _effective_scopes(credentials: Credentials) -> tuple[str, ...]:
    scopes = credentials.granted_scopes
    if scopes is None:
        scopes = credentials.scopes or ()
    if isinstance(scopes, str):
        scopes = scopes.split()
    return tuple(scope for scope in scopes if isinstance(scope, str))


def _google_endpoint(value: Any, hosts: set[str], paths: set[str]) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return (
            parsed.scheme == "https"
            and parsed.hostname in hosts
            and parsed.path in paths
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        return False


def _read_oauth_client(path: Path) -> dict[str, Any]:
    try:
        client_file = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise RuntimeError("OAuth client file could not be read as valid JSON.") from None
    if not isinstance(client_file, dict) or not isinstance(client_file.get("installed"), dict):
        raise RuntimeError("Use a Google OAuth Desktop app client JSON file.")  # noqa: TRY004

    installed = client_file["installed"]
    if (
        not isinstance(installed.get("client_id"), str)
        or not installed["client_id"].endswith(".apps.googleusercontent.com")
        or not isinstance(installed.get("client_secret"), str)
        or not installed["client_secret"]
        or not _google_endpoint(
            installed.get("auth_uri"),
            {"accounts.google.com"},
            {"/o/oauth2/auth", "/o/oauth2/v2/auth"},
        )
        or not _google_endpoint(
            installed.get("token_uri"),
            {"oauth2.googleapis.com", "www.googleapis.com"},
            {"/token", "/oauth2/v4/token"},
        )
    ):
        raise RuntimeError(
            "OAuth client file must contain a valid Google Desktop client configuration."
        )

    redirect_uris = installed.get("redirect_uris")
    if not isinstance(redirect_uris, list) or not redirect_uris:
        raise RuntimeError("OAuth client file must contain a Desktop redirect URI.")
    for redirect_uri in redirect_uris:
        if not isinstance(redirect_uri, str):
            raise RuntimeError("OAuth client file must contain a Desktop redirect URI.")  # noqa: TRY004
        try:
            parsed = urlsplit(redirect_uri)
        except ValueError:
            raise RuntimeError("OAuth client file must contain a Desktop redirect URI.") from None
        if parsed.scheme != "http" or parsed.hostname not in {
            "localhost",
            "127.0.0.1",
            "[::1]",
            "::1",
        }:
            raise RuntimeError("OAuth client file must use a local Desktop redirect URI.")

    # Keep only the fields consumed by the installed-app flow.
    return {
        "installed": {
            key: installed[key]
            for key in ("client_id", "client_secret", "auth_uri", "token_uri", "redirect_uris")
        }
    }


def setup(credentials_path: Path, enable_send: bool = False) -> None:
    """Validate a Desktop client, complete OAuth, and store it after successful consent."""
    client_config = _read_oauth_client(credentials_path)
    token_contents = _authorized_token(client_config, enable_send)
    _atomic_write_token(token_contents)
    _atomic_write_private_file(
        DEFAULT_CREDENTIALS_PATH,
        json.dumps(client_config, separators=(",", ":")),
    )
    print(f"Google Chat login saved in {TOKEN_PATH}.")


def _authorized_token(client_config: dict[str, Any], enable_send: bool) -> str:
    scopes = (*READ_SCOPES, SEND_SCOPE) if enable_send else READ_SCOPES
    try:
        flow = InstalledAppFlow.from_client_config(
            client_config,
            list(scopes),
            autogenerate_code_verifier=True,
        )
        print("Opening Google authorization in your browser…")
        credentials = flow.run_local_server(
            host="127.0.0.1",
            port=0,
            open_browser=True,
            authorization_prompt_message=None,
            prompt="consent",
        )
        granted_scopes = _effective_scopes(credentials)
        if not set(scopes).issubset(granted_scopes) or not credentials.refresh_token:
            raise RuntimeError("Google did not return the complete requested grant.")
        token_data = json.loads(credentials.to_json())
        token_data["scopes"] = list(granted_scopes)
        return json.dumps(token_data)
    except Exception:  # noqa: BLE001 - OAuth providers can expose secrets in arbitrary exception text.
        raise RuntimeError(
            "Google OAuth login failed or did not grant all requested access. The saved login was not changed. "
            "Check the Desktop client, Chat API access, and consent screen."
        ) from None


def login(credentials_path: Path, enable_send: bool = False) -> None:
    """Complete local OAuth; only request the send scope when explicitly selected."""
    if not credentials_path.is_file():
        raise RuntimeError(
            "Google OAuth Desktop client JSON was not found. Download one from Google Cloud "
            "and pass its path with --credentials."
        )
    client_config = _read_oauth_client(credentials_path)
    token_contents = _authorized_token(client_config, enable_send)
    _atomic_write_token(token_contents)
    print(f"Google Chat login saved in {TOKEN_PATH}.")


def connection_status() -> dict[str, Any]:
    """Report local cached setup state without contacting Google or exposing credentials."""
    try:
        _read_oauth_client(DEFAULT_CREDENTIALS_PATH)
        configured = True
    except RuntimeError:
        configured = False
    status: dict[str, Any] = {
        "configured": configured,
        "signed_in": False,
        "grant": "none",
        "token_state": "missing",
        "live_verified": False,
    }
    if not TOKEN_PATH.is_file():
        return status
    try:
        token_data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        if not isinstance(token_data, dict):
            raise TypeError("OAuth token must be a JSON object.")
        raw_scopes = token_data.get("scopes")
        scopes = (
            set(raw_scopes)
            if isinstance(raw_scopes, list) and all(isinstance(scope, str) for scope in raw_scopes)
            else set()
        )
        if scopes.issuperset((*READ_SCOPES, SEND_SCOPE)):
            grant = "read_and_send"
        elif scopes.issuperset(READ_SCOPES):
            grant = "read_only"
        else:
            grant = "unknown"
        has_refresh = isinstance(token_data.get("refresh_token"), str) and bool(
            token_data.get("refresh_token")
        )
        expiry = token_data.get("expiry")
        expired = False
        if isinstance(expiry, str):
            try:
                expiry_time = datetime.fromisoformat(expiry)
                if expiry_time.tzinfo is None:
                    expiry_time = expiry_time.replace(tzinfo=UTC)
                expired = expiry_time <= datetime.now(UTC)
            except ValueError:
                grant = "unknown"
        elif expiry is not None:
            grant = "unknown"
            status["token_state"] = "unreadable"
        if status["token_state"] == "unreadable":
            token_state = "unreadable"
        elif expired and has_refresh:
            token_state = "refreshable"
        elif expired:
            token_state = "expired"
        else:
            token_state = "cached"
        status.update(
            signed_in=has_refresh or bool(token_data.get("token")),
            grant=grant,
            token_state=token_state,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        status["token_state"] = "unreadable"
        status["grant"] = "unknown"
    return status


def load_credentials() -> Credentials:
    if not TOKEN_PATH.is_file():
        raise RuntimeError("No Google Chat login found. Run `google-chat-plugin login` first.")
    try:
        # Preserve the exact saved scope grant; supplying broader requested scopes here could
        # make a read-only token appear write-capable without Google's consent.
        token_data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        saved_scopes = token_data.get("scopes")
        if saved_scopes is None:
            saved_scopes = READ_SCOPES
        credentials = Credentials.from_authorized_user_file(str(TOKEN_PATH), saved_scopes)
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            token_data = json.loads(credentials.to_json())
            token_data["scopes"] = list(_effective_scopes(credentials))
            _atomic_write_token(json.dumps(token_data))
        if not credentials.valid:
            raise RuntimeError("Saved Google credentials are no longer valid. Run login again.")
        return credentials
    except RefreshError:
        raise RuntimeError(
            "Google OAuth refresh failed. Run login again and grant the requested access."
        ) from None
    except (ValueError, OSError):
        raise RuntimeError("Saved Google OAuth token is unreadable. Run login again.") from None


def _has_scope(credentials: Credentials, scope: str) -> bool:
    return scope in _effective_scopes(credentials)


def _chat_service(*, for_send: bool = False) -> Any:
    try:
        credentials = load_credentials()
        if for_send and not _has_scope(credentials, SEND_SCOPE):
            raise RuntimeError(
                "Google Chat send permission is not enabled. Run `google-chat-plugin login --enable-send` "
                "and grant the additional chat.messages.create permission. Read tools still use your existing access."
            )
        return build("chat", "v1", credentials=credentials, cache_discovery=False)
    except GoogleAuthError:
        raise RuntimeError(
            "Google authentication failed. Run login again and check Workspace access."
        ) from None


def _api_execute(request: Any) -> dict[str, Any]:
    try:
        return request.execute()
    except HttpError as exc:
        status = getattr(getattr(exc, "resp", None), "status", None)
        if status in (401, 403):
            raise RuntimeError(
                "Google Chat denied this request. Check account access, API enablement, and OAuth permissions."
            ) from None
        if status == 404:
            raise RuntimeError(
                "Google Chat could not find that space, message, or thread, or access was denied."
            ) from None
        raise RuntimeError(
            f"Google Chat API request failed (HTTP {status or 'unknown'}). Try again later."
        ) from None
    except (TimeoutError, OSError):
        raise RuntimeError(
            "Could not reach the Google Chat API. Check the network connection and try again."
        ) from None
    except GoogleAuthError:
        raise RuntimeError(
            "Google authentication failed. Run login again and check Workspace access."
        ) from None


def _validated_resource(value: str, label: str, expected_kind: str | None = None) -> str:
    if not RESOURCE_RE.fullmatch(value or ""):
        raise ValueError(f"{label} must be a valid Google Chat resource name.")
    if expected_kind is None and "/" in value.removeprefix("spaces/"):
        raise ValueError(f"{label} must identify a space, such as spaces/AAAA.")
    if expected_kind and f"/{expected_kind}/" not in value:
        raise ValueError(f"{label} must identify a {expected_kind[:-1]} resource.")
    return value


def _validate_time(value: str | None, label: str) -> str | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO 8601 timestamp with a timezone.") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone, such as Z or +02:00.")
    return parsed.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _compact(resource: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {key: resource[key] for key in fields if key in resource}


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def get_connection_status() -> dict[str, Any]:
    """Show whether local setup and a cached grant exist; this does not contact Google."""
    return connection_status()


def _space_from_child(resource: str) -> str:
    return resource.split("/", 2)[0] + "/" + resource.split("/", 2)[1]


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def list_spaces(page_size: int = 100, page_token: str | None = None) -> dict[str, Any]:
    """List spaces visible to the logged-in user. Use nextPageToken to continue."""
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000.")
    params: dict[str, Any] = {"pageSize": page_size}
    if page_token is not None:
        params["pageToken"] = page_token
    result = _api_execute(_chat_service().spaces().list(**params))
    output: dict[str, Any] = {}
    if "spaces" in result:
        output["spaces"] = [
            _compact(space, ("name", "displayName", "spaceType", "membershipCount"))
            for space in result["spaces"]
        ]
    if "nextPageToken" in result:
        output["nextPageToken"] = result["nextPageToken"]
    return output


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def list_messages(
    space_name: str,
    page_size: int = 100,
    page_token: str | None = None,
    after: str | None = None,
    before: str | None = None,
    thread_name: str | None = None,
) -> dict[str, Any]:
    """List one space page, optionally filtered by time and a thread in that same space."""
    _validated_resource(space_name, "space_name")
    if not 1 <= page_size <= 1000:
        raise ValueError("page_size must be between 1 and 1000.")
    after_value = _validate_time(after, "after")
    before_value = _validate_time(before, "before")
    if after_value and before_value and after_value >= before_value:
        raise ValueError("after must be earlier than before.")
    if thread_name is not None:
        _validated_resource(thread_name, "thread_name", "threads")
        if _space_from_child(thread_name) != space_name:
            raise ValueError("thread_name must belong to space_name.")
    clauses = []
    if after_value:
        clauses.append(f'createTime > "{after_value}"')
    if before_value:
        clauses.append(f'createTime < "{before_value}"')
    if thread_name:
        clauses.append(f'thread.name = "{thread_name}"')
    params: dict[str, Any] = {"parent": space_name, "pageSize": page_size}
    if page_token is not None:
        params["pageToken"] = page_token
    if clauses:
        params["filter"] = " AND ".join(clauses)
    result = _api_execute(_chat_service().spaces().messages().list(**params))
    output: dict[str, Any] = {}
    if "messages" in result:
        output["messages"] = [
            _compact(message, ("name", "thread", "sender", "text", "createTime", "lastUpdateTime"))
            for message in result["messages"]
        ]
    if "nextPageToken" in result:
        output["nextPageToken"] = result["nextPageToken"]
    return output


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False))
def get_message(name: str) -> dict[str, Any]:
    """Get one message by its full Google Chat resource name."""
    _validated_resource(name, "name", "messages")
    result = _api_execute(_chat_service().spaces().messages().get(name=name))
    return _compact(result, ("name", "thread", "sender", "text", "createTime", "lastUpdateTime"))


@mcp.tool(
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True)
)
def send_message(
    space_name: str, text: str, request_id: str, thread_name: str | None = None
) -> dict[str, Any]:
    """Send plain text to a space using a caller-supplied UUID for Google-side idempotency.

    To reply, provide a thread resource in the same space; replies fail if that thread is missing.
    """
    _validated_resource(space_name, "space_name")
    if not text or not text.strip():
        raise ValueError("text must contain a non-whitespace character.")
    if len(text.encode("utf-8")) > 32_000:
        raise ValueError("text must be at most 32,000 UTF-8 bytes.")
    try:
        parsed_id = uuid.UUID(request_id)
    except (ValueError, AttributeError) as exc:
        raise ValueError("request_id must be a UUID used to make retries idempotent.") from exc
    if str(parsed_id) != request_id.lower():
        raise ValueError("request_id must use the canonical UUID form.")
    body: dict[str, Any] = {"text": text}
    params: dict[str, Any] = {"parent": space_name, "body": body, "requestId": str(parsed_id)}
    service = _chat_service(for_send=True)
    if thread_name is not None:
        _validated_resource(thread_name, "thread_name", "threads")
        if _space_from_child(thread_name) != space_name:
            raise ValueError("thread_name must belong to space_name.")
        space = _api_execute(service.spaces().get(name=space_name))
        if space.get("spaceType") != "SPACE":
            raise ValueError("thread replies are supported only in named spaces (spaceType=SPACE).")
        body["thread"] = {"name": thread_name}
        params["messageReplyOption"] = "REPLY_MESSAGE_OR_FAIL"
    response = _api_execute(service.spaces().messages().create(**params))
    return _compact(response, ("name", "thread", "text", "createTime"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    setup_parser = commands.add_parser(
        "setup", help="Store a Google OAuth Desktop client and sign in"
    )
    setup_parser.add_argument("--credentials", type=Path, required=True)
    setup_parser.add_argument(
        "--enable-send",
        action="store_true",
        help="also request the chat.messages.create OAuth scope",
    )
    login_parser = commands.add_parser("login", help="Sign in to Google Chat")
    login_parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS_PATH)
    login_parser.add_argument(
        "--enable-send",
        action="store_true",
        help="also request the chat.messages.create OAuth scope",
    )
    commands.add_parser("status", help="Show local setup and cached permission status")
    args = parser.parse_args()
    if args.command in {"setup", "login"}:
        try:
            if args.command == "setup":
                setup(args.credentials.expanduser(), args.enable_send)
            else:
                login(args.credentials.expanduser(), args.enable_send)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            raise SystemExit(1) from None
        return
    if args.command == "status":
        print(json.dumps(connection_status(), indent=2, sort_keys=True))
        return
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
