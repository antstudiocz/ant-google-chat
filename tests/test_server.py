from __future__ import annotations

import json
import subprocess
import sys
import traceback
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
    return Credentials(token="synthetic", scopes=list(scopes or app.READ_SCOPES))


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


def test_load_preserves_scopes_recorded_in_local_token_without_upgrading(monkeypatch, tmp_path):
    token_path = tmp_path / "token.json"
    token_path.write_text(
        json.dumps({"scopes": list(app.READ_SCOPES), "refresh_token": "synthetic"}),
        encoding="utf-8",
    )
    received = {}

    def fake_load(_path, scopes):
        received["scopes"] = tuple(scopes)
        return valid_credentials(scopes)

    monkeypatch.setattr(app, "TOKEN_PATH", token_path)
    monkeypatch.setattr(Credentials, "from_authorized_user_file", fake_load)
    assert app.load_credentials().valid
    assert received["scopes"] == app.READ_SCOPES
    assert app.SEND_SCOPE not in received["scopes"]


@pytest.mark.parametrize("enable_send", [False, True])
def test_login_requests_send_scope_only_when_opted_in(monkeypatch, tmp_path, enable_send):
    requested = {}

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, _path, scopes):
            requested["scopes"] = tuple(scopes)
            return cls()

        def run_local_server(self, **_kwargs):
            return Mock(to_json=lambda: "synthetic OAuth contents")

    monkeypatch.setattr(app, "InstalledAppFlow", FakeFlow)
    monkeypatch.setattr(app, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(app, "TOKEN_PATH", tmp_path / "config" / "token.json")
    monkeypatch.setattr(app, "_atomic_write_token", lambda value: requested.update(token=value))
    client = tmp_path / "desktop-client.json"
    client.write_text("{}", encoding="utf-8")

    app.login(client, enable_send)

    expected = (*app.READ_SCOPES, app.SEND_SCOPE) if enable_send else app.READ_SCOPES
    assert requested["scopes"] == expected
    assert requested["token"] == "synthetic OAuth contents"


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
        def from_client_secrets_file(cls, *_args, **_kwargs):
            raise RuntimeError("private-sentinel-token-body")

    monkeypatch.setattr(app, "InstalledAppFlow", Flow)
    monkeypatch.setattr(app, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(app, "TOKEN_PATH", tmp_path / "config" / "token.json")
    client = tmp_path / "oauth.json"
    client.write_text("{}", encoding="utf-8")
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
        "get_message",
        "list_messages",
        "list_spaces",
        "send_message",
    ]
