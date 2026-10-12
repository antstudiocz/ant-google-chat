from __future__ import annotations

import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.errors import HttpError

from google_chat_plugin import server as app


class Request:
    def __init__(self, result=None, error=None):
        self.result = result or {}
        self.error = error

    def execute(self):
        if self.error:
            raise self.error
        return self.result


class Messages:
    def __init__(self, listed=None, fetched=None, created=None):
        self.listed = listed or {}
        self.fetched = fetched or {}
        self.created = created or {"name": "spaces/S/messages/M", "text": "hello"}
        self.list_args = None
        self.get_args = None
        self.create_args = None
        self.create_calls = 0

    def list(self, **kwargs):
        self.list_args = kwargs
        return Request(self.listed)

    def get(self, **kwargs):
        self.get_args = kwargs
        return Request(self.fetched)

    def create(self, **kwargs):
        self.create_args = kwargs
        self.create_calls += 1
        return Request(self.created)


class Spaces:
    def __init__(self, messages, space=None):
        self.messages_api = messages
        self.space = space or {"name": "spaces/S", "spaceType": "SPACE"}
        self.get_args = None

    def messages(self):
        return self.messages_api

    def get(self, **kwargs):
        self.get_args = kwargs
        return Request(self.space)

    def list(self, **kwargs):
        return Request({"spaces": [{"name": "spaces/S", "displayName": "Example"}]})


class Service:
    def __init__(self, spaces):
        self.spaces_api = spaces

    def spaces(self):
        return self.spaces_api


def valid_credentials(scopes=None):
    effective_scopes = list(app.READ_SCOPES if scopes is None else scopes)
    return Credentials(
        token="synthetic",
        refresh_token="synthetic-refresh",
        scopes=effective_scopes,
        granted_scopes=effective_scopes,
    )


def test_list_spaces_and_message_filters_are_compact(monkeypatch):
    messages = Messages(listed={"messages": [{"name": "spaces/S/messages/M", "text": ""}]})
    spaces = Spaces(messages)
    monkeypatch.setattr(app, "_chat_service", lambda **kwargs: Service(spaces))

    assert app.list_spaces() == {"spaces": [{"name": "spaces/S", "displayName": "Example"}]}
    result = app.list_messages(
        "spaces/S",
        after="2026-10-12T10:00:00+02:00",
        before="2026-10-12T12:00:00Z",
        thread_name="spaces/S/threads/T",
    )
    assert messages.list_args == {
        "parent": "spaces/S",
        "pageSize": 100,
        "filter": 'createTime > "2026-10-12T08:00:00.000Z" AND createTime < "2026-10-12T12:00:00.000Z" AND thread.name = "spaces/S/threads/T"',
    }
    assert result == {"messages": [{"name": "spaces/S/messages/M", "text": ""}]}


def test_get_message_accepts_dotted_api_ids(monkeypatch):
    message_api = Messages(fetched={"name": "spaces/AAAA/messages/BBBB.CCCC", "text": "hi"})
    monkeypatch.setattr(app, "_chat_service", lambda **kwargs: Service(Spaces(message_api)))
    assert app.get_message("spaces/AAAA/messages/BBBB.CCCC") == {
        "name": "spaces/AAAA/messages/BBBB.CCCC",
        "text": "hi",
    }


@pytest.mark.parametrize(
    "args",
    [
        {"space_name": 'spaces/S" OR true'},
        {"space_name": "spaces/S", "thread_name": 'spaces/S/threads/T" OR true'},
        {"space_name": "spaces/S", "thread_name": "spaces/OTHER/threads/T"},
    ],
)
def test_bad_resource_and_cross_space_thread_rejected_before_google(monkeypatch, args):
    service = Mock()
    monkeypatch.setattr(app, "_chat_service", lambda **kwargs: service)
    with pytest.raises(ValueError):
        app.list_messages(**args)
    service.spaces.assert_not_called()


def test_invalid_send_identity_and_oversized_text_never_call_api(monkeypatch):
    service_factory = Mock()
    monkeypatch.setattr(app, "_chat_service", service_factory)
    for values in (
        {"space_name": "spaces/S", "text": "hello", "request_id": "not-a-uuid"},
        {
            "space_name": "spaces/S",
            "text": "x" * 32_001,
            "request_id": "123e4567-e89b-12d3-a456-426614174000",
        },
        {
            "space_name": "spaces/S",
            "text": "é" * 16_001,
            "request_id": "123e4567-e89b-12d3-a456-426614174000",
        },
        {
            "space_name": "spaces/S",
            "text": "  ",
            "request_id": "123e4567-e89b-12d3-a456-426614174000",
        },
    ):
        with pytest.raises(ValueError):
            app.send_message(**values)
    service_factory.assert_not_called()


def test_send_uses_user_uuid_and_strict_same_space_thread_reply(monkeypatch):
    messages = Messages(
        created={
            "name": "spaces/S/messages/M",
            "text": "hello",
            "thread": {"name": "spaces/S/threads/T"},
        }
    )
    spaces = Spaces(messages)
    service = Service(spaces)
    monkeypatch.setattr(app, "_chat_service", lambda **kwargs: service)
    request_id = "123e4567-e89b-12d3-a456-426614174000"

    result = app.send_message("spaces/S", "hello", request_id, "spaces/S/threads/T")

    assert spaces.get_args == {"name": "spaces/S"}
    assert messages.create_args == {
        "parent": "spaces/S",
        "body": {"text": "hello", "thread": {"name": "spaces/S/threads/T"}},
        "requestId": request_id,
        "messageReplyOption": "REPLY_MESSAGE_OR_FAIL",
    }
    assert result["name"] == "spaces/S/messages/M"


def test_thread_reply_fails_closed_outside_named_space(monkeypatch):
    messages = Messages()
    spaces = Spaces(messages, space={"name": "spaces/S", "spaceType": "GROUP_CHAT"})
    monkeypatch.setattr(app, "_chat_service", lambda **kwargs: Service(spaces))
    with pytest.raises(ValueError, match="named spaces"):
        app.send_message(
            "spaces/S", "hello", "123e4567-e89b-12d3-a456-426614174000", "spaces/S/threads/T"
        )
    assert messages.create_calls == 0


def test_missing_thread_api_error_never_falls_back_to_a_new_message(monkeypatch):
    error = HttpError(resp=Mock(status=404), content=b"private thread details")
    messages = Messages()
    messages.create = lambda **kwargs: (
        setattr(messages, "create_calls", messages.create_calls + 1) or Request(error=error)
    )
    monkeypatch.setattr(app, "_chat_service", lambda **kwargs: Service(Spaces(messages)))
    with pytest.raises(RuntimeError, match="could not find") as raised:
        app.send_message(
            "spaces/S", "reply", "123e4567-e89b-12d3-a456-426614174000", "spaces/S/threads/T"
        )
    assert messages.create_calls == 1
    assert "private thread" not in "".join(traceback.format_exception(raised.value))


def test_missing_write_scope_does_not_block_read_credentials(monkeypatch):
    creds = valid_credentials()
    monkeypatch.setattr(app, "load_credentials", lambda: creds)
    monkeypatch.setattr(app, "build", lambda *args, **kwargs: "service")
    assert app._chat_service() == "service"
    with pytest.raises(RuntimeError, match="login --enable-send"):
        app._chat_service(for_send=True)


@pytest.mark.parametrize("saved_scopes", [list(app.READ_SCOPES), []])
def test_load_preserves_scopes_recorded_in_local_token_without_upgrading(
    monkeypatch, tmp_path, saved_scopes
):
    token_path = tmp_path / "token.json"
    token_path.write_text(
        json.dumps({"scopes": saved_scopes, "refresh_token": "synthetic"}), encoding="utf-8"
    )
    received = {}

    def fake_load(_path, scopes):
        received["scopes"] = tuple(scopes)
        return valid_credentials(scopes)

    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    monkeypatch.setattr(Credentials, "from_authorized_user_file", fake_load)
    assert app.load_credentials().valid
    assert received["scopes"] == tuple(saved_scopes)
    assert app.SEND_SCOPE not in received["scopes"]


def test_empty_explicit_grant_does_not_fall_back_to_requested_send_scope():
    credentials = Credentials(
        token="synthetic",
        scopes=[*app.READ_SCOPES, app.SEND_SCOPE],
        granted_scopes=[],
    )
    assert not app._has_scope(credentials, app.SEND_SCOPE)


def test_refresh_persists_effective_grant_when_provider_reduces_scopes(monkeypatch, tmp_path):
    token_path = tmp_path / "token.json"
    scopes = [*app.READ_SCOPES, app.SEND_SCOPE]
    token_path.write_text(json.dumps({"scopes": scopes}), encoding="utf-8")
    credentials = Credentials(
        token="old-token",
        refresh_token="synthetic-refresh",
        scopes=scopes,
        granted_scopes=scopes,
        expiry=(datetime.now(UTC) - timedelta(minutes=1)).replace(tzinfo=None),
    )
    persisted = {}

    def from_file(_path, _scopes):
        return credentials

    def refresh(instance, _request):
        instance.token = "new-token"
        instance.expiry = (datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None)
        instance._granted_scopes = list(app.READ_SCOPES)

    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    monkeypatch.setattr(Credentials, "from_authorized_user_file", from_file)
    monkeypatch.setattr(Credentials, "refresh", refresh)
    monkeypatch.setattr(
        app, "_atomic_write_token", lambda contents: persisted.update(value=contents)
    )

    result = app.load_credentials()

    saved = json.loads(persisted["value"])
    assert saved["scopes"] == list(app.READ_SCOPES)
    assert not app._has_scope(result, app.SEND_SCOPE)


@pytest.mark.parametrize("enable_send", [False, True])
def test_login_requests_exact_scope_set_and_persists_only_a_complete_grant(
    monkeypatch, tmp_path, enable_send
):
    requested = {}

    class FakeFlow:
        @classmethod
        def from_client_config(cls, _config, scopes, **kwargs):
            requested["scopes"] = tuple(scopes)
            requested["pkce"] = kwargs
            return cls()

        def run_local_server(self, **kwargs):
            requested["flow_options"] = kwargs
            return valid_credentials(requested["scopes"])

    monkeypatch.setattr(app, "InstalledAppFlow", FakeFlow)
    monkeypatch.setattr(app, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(app, "TOKEN_PATH", tmp_path / "config" / "token.json")
    monkeypatch.setattr(app, "_atomic_write_token", lambda value: requested.update(token=value))
    client = tmp_path / "desktop-client.json"
    client.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "synthetic.apps.googleusercontent.com",
                    "client_secret": "synthetic-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }
        ),
        encoding="utf-8",
    )

    app.login(client, enable_send)

    expected = (*app.READ_SCOPES, app.SEND_SCOPE) if enable_send else app.READ_SCOPES
    assert requested["scopes"] == expected
    assert requested["pkce"] == {"autogenerate_code_verifier": True}
    assert requested["flow_options"] == {
        "host": "127.0.0.1",
        "port": 0,
        "open_browser": True,
        "authorization_prompt_message": None,
        "prompt": "consent",
    }
    assert json.loads(requested["token"])["refresh_token"] == "synthetic-refresh"
    assert json.loads(requested["token"])["scopes"] == list(expected)


def oauth_client_json():
    return json.dumps(
        {
            "installed": {
                "client_id": "synthetic.apps.googleusercontent.com",
                "client_secret": "synthetic-secret",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
    )


def test_setup_stores_only_validated_google_client_with_private_permissions(monkeypatch, tmp_path):
    source = tmp_path / "provided.json"
    source.write_text(oauth_client_json(), encoding="utf-8")
    config_dir = tmp_path / "config"
    token_path = config_dir / "token.json"
    monkeypatch.setattr(app, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(app, "DEFAULT_CREDENTIALS_PATH", config_dir / "client_secret.json")
    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    login_calls = []
    monkeypatch.setattr(
        app,
        "_authorized_token",
        lambda config, send: login_calls.append((config, send)) or '{"token":"synthetic"}',
    )

    app.setup(source, enable_send=True)

    stored = json.loads((config_dir / "client_secret.json").read_text())
    assert stored == json.loads(oauth_client_json())
    assert (config_dir / "client_secret.json").stat().st_mode & 0o777 == 0o600
    assert config_dir.stat().st_mode & 0o777 == 0o700
    assert login_calls == [(json.loads(oauth_client_json()), True)]


def test_setup_rejects_non_google_endpoint_without_changing_saved_client(monkeypatch, tmp_path):
    source = tmp_path / "provided.json"
    value = json.loads(oauth_client_json())
    value["installed"]["token_uri"] = "https://example.invalid/token"
    source.write_text(json.dumps(value), encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    saved_client = config_dir / "client_secret.json"
    saved_client.write_text("previous-client", encoding="utf-8")
    monkeypatch.setattr(app, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(app, "DEFAULT_CREDENTIALS_PATH", saved_client)

    with pytest.raises(RuntimeError, match="valid Google Desktop"):
        app.setup(source)

    assert saved_client.read_text(encoding="utf-8") == "previous-client"


@pytest.mark.parametrize("failure", ["declined", "partial", "no_refresh"])
def test_failed_or_incomplete_login_preserves_existing_token(monkeypatch, tmp_path, failure):
    class FakeFlow:
        @classmethod
        def from_client_config(cls, _config, scopes, **_kwargs):
            cls.scopes = scopes
            return cls()

        def run_local_server(self, **_kwargs):
            if failure == "declined":
                raise RuntimeError("private-provider-response")
            scopes = self.scopes[:-1] if failure == "partial" else self.scopes
            if failure == "no_refresh":
                return Credentials(
                    token="synthetic",
                    scopes=list(scopes),
                    granted_scopes=list(scopes),
                )
            if failure == "partial":
                return Credentials(
                    token="synthetic",
                    refresh_token="synthetic-refresh",
                    scopes=list(self.scopes),
                    granted_scopes=list(scopes),
                )
            credentials = valid_credentials(scopes)
            return credentials

    monkeypatch.setattr(app, "InstalledAppFlow", FakeFlow)
    config_dir = tmp_path / "config"
    token_path = config_dir / "token.json"
    monkeypatch.setattr(app, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    token_path.parent.mkdir()
    token_path.write_text("existing-token-sentinel", encoding="utf-8")
    client = tmp_path / "client.json"
    client.write_text(oauth_client_json(), encoding="utf-8")

    with pytest.raises(RuntimeError) as raised:
        app.login(client, enable_send=True)

    assert "private-provider-response" not in str(raised.value)
    assert raised.value.__suppress_context__ is True
    assert token_path.read_text(encoding="utf-8") == "existing-token-sentinel"


def test_setup_cancellation_preserves_saved_client_and_token(monkeypatch, tmp_path):
    source = tmp_path / "provided.json"
    source.write_text(oauth_client_json(), encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    client_path = config_dir / "client_secret.json"
    client_path.write_text("previous-client-sentinel", encoding="utf-8")
    token_path = config_dir / "token.json"
    token_path.write_text("previous-token-sentinel", encoding="utf-8")
    monkeypatch.setattr(app, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(app, "DEFAULT_CREDENTIALS_PATH", client_path)
    monkeypatch.setattr(app, "TOKEN_PATH", token_path)

    def canceled_login(*_args, **_kwargs):
        raise RuntimeError("safe login error")

    monkeypatch.setattr(app, "_authorized_token", canceled_login)
    with pytest.raises(RuntimeError, match="safe login error"):
        app.setup(source)

    assert client_path.read_text(encoding="utf-8") == "previous-client-sentinel"
    assert token_path.read_text(encoding="utf-8") == "previous-token-sentinel"


def test_connection_status_reports_cached_grant_without_token_values(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    token_path = config_dir / "token.json"
    token_path.write_text(
        json.dumps(
            {
                "token": "access-secret-sentinel",
                "refresh_token": "refresh-secret-sentinel",
                "scopes": list(app.READ_SCOPES),
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(app, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    monkeypatch.setattr(app, "DEFAULT_CREDENTIALS_PATH", config_dir / "client_secret.json")

    status = app.connection_status()

    assert status == {
        "configured": False,
        "signed_in": True,
        "grant": "read_only",
        "token_state": "cached",
        "live_verified": False,
    }
    assert "secret-sentinel" not in json.dumps(status)


def test_connection_status_handles_malformed_cache_without_exposing_contents(monkeypatch, tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    token_path = config_dir / "token.json"
    token_path.write_text(
        json.dumps({"scopes": [{"private": "sentinel"}], "expiry": "not-a-date"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(app, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    monkeypatch.setattr(app, "DEFAULT_CREDENTIALS_PATH", config_dir / "client_secret.json")

    status = app.connection_status()

    assert status["grant"] == "unknown"
    assert status["live_verified"] is False
    assert "sentinel" not in json.dumps(status)


def test_cli_status_is_safe_json_and_does_not_contact_google(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "token.json").write_text(
        json.dumps(
            {
                "token": "access-secret-sentinel",
                "refresh_token": "refresh-secret-sentinel",
                "scopes": list(app.READ_SCOPES),
            }
        ),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["GOOGLE_CHAT_PLUGIN_HOME"] = str(config_dir)
    completed = subprocess.run(
        [sys.executable, "-m", "google_chat_plugin.server", "status"],
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        timeout=10,
        env=env,
    )

    assert completed.returncode == 0
    assert json.loads(completed.stdout) == {
        "configured": False,
        "signed_in": True,
        "grant": "read_only",
        "token_state": "cached",
        "live_verified": False,
    }
    assert "secret-sentinel" not in completed.stdout + completed.stderr


def test_invalid_time_filter_rejected_before_google(monkeypatch):
    service = Mock()
    monkeypatch.setattr(app, "_chat_service", lambda **kwargs: service)
    with pytest.raises(ValueError, match="timezone"):
        app.list_messages("spaces/S", after="2026-10-12T10:00:00")
    with pytest.raises(ValueError, match="earlier than before"):
        app.list_messages("spaces/S", after="2026-10-12T12:00:00Z", before="2026-10-12T12:00:00Z")
    service.spaces.assert_not_called()


def test_api_errors_hide_provider_body_from_message_and_traceback():
    private = "private-sentinel-token-body"
    error = HttpError(resp=Mock(status=403), content=private.encode())
    with pytest.raises(RuntimeError) as raised:
        app._api_execute(Request(error=error))
    rendered = "".join(traceback.format_exception(raised.value))
    assert "denied" in str(raised.value)
    assert private not in rendered
    assert raised.value.__suppress_context__ is True


def test_refresh_error_during_api_call_is_sanitized():
    with pytest.raises(RuntimeError) as raised:
        app._api_execute(Request(error=RefreshError("refresh-token-sentinel")))
    assert "authentication failed" in str(raised.value)
    assert raised.value.__suppress_context__ is True
    assert raised.value.__cause__ is None


def test_oauth_login_errors_are_sanitized(monkeypatch, tmp_path):
    class Flow:
        @classmethod
        def from_client_config(cls, *_args, **_kwargs):
            raise RuntimeError("private-sentinel-token-body")

    monkeypatch.setattr(app, "InstalledAppFlow", Flow)
    monkeypatch.setattr(app, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(app, "TOKEN_PATH", tmp_path / "config" / "token.json")
    client = tmp_path / "oauth.json"
    client.write_text(oauth_client_json(), encoding="utf-8")
    with pytest.raises(RuntimeError) as raised:
        app.login(client)
    assert "private-sentinel" not in str(raised.value)
    assert raised.value.__suppress_context__ is True


def test_atomic_token_writes_use_owner_only_permissions(monkeypatch, tmp_path):
    token_dir = tmp_path / "oauth"
    token_path = token_dir / "token.json"
    monkeypatch.setattr(app, "CONFIG_DIR", token_dir)
    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    app._atomic_write_token(json.dumps({"token": "synthetic"}))
    assert token_path.read_text(encoding="utf-8") == '{"token": "synthetic"}'
    assert token_dir.stat().st_mode & 0o777 == 0o700
    assert token_path.stat().st_mode & 0o777 == 0o600


def test_stdio_lists_expected_tools():
    script = r"""
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

async def main():
    async with stdio_client(StdioServerParameters(command=sys.executable, args=["-m", "google_chat_plugin.server"])) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print(json.dumps(sorted(tool.name for tool in (await session.list_tools()).tools)))

asyncio.run(main())
"""
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=root,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout.strip().splitlines()[-1]) == [
        "get_connection_status",
        "get_message",
        "list_messages",
        "list_spaces",
        "send_message",
    ]
