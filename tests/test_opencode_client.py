import pytest

from ecoacher.opencode import client as op_client


class _APIError(Exception):
    pass


class _FakeResponse:
    def __init__(self, payload, status_code: int = 200, json_raises: bool = False):
        self._payload = payload
        self.status_code = status_code
        self._json_raises = json_raises

    def json(self):
        if self._json_raises:
            raise ValueError("invalid json")
        return self._payload


class _FakeSDK:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.post_result = _FakeResponse({"id": "ses_1"})
        self.delete_error = None
        self.get_result = _FakeResponse({}, status_code=200)
        self.closed = False
        self.post_calls = []
        self.delete_calls = []
        self.get_calls = []

    def close(self):
        self.closed = True

    def post(self, url, cast_to=None, body=None):
        self.post_calls.append((url, body))
        if isinstance(self.post_result, Exception):
            raise self.post_result
        return self.post_result

    def delete(self, url, cast_to=None):
        self.delete_calls.append(url)
        if self.delete_error is not None:
            raise self.delete_error
        return _FakeResponse({})

    def get(self, url, cast_to=None):
        self.get_calls.append(url)
        if isinstance(self.get_result, Exception):
            raise self.get_result
        return self.get_result


def _make_client(monkeypatch):
    holder = {}

    def fake_opencode(**kwargs):
        sdk = _FakeSDK(**kwargs)
        holder["sdk"] = sdk
        return sdk

    monkeypatch.setattr(op_client, "Opencode", fake_opencode)
    monkeypatch.setattr(op_client.opencode_ai, "APIError", _APIError)
    client = op_client.OpencodeClient(base_url="http://localhost", directory="/tmp/my dir")
    return client, holder["sdk"]


def test_post_init_and_close(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    assert sdk.kwargs["base_url"] == "http://localhost"
    assert sdk.kwargs["timeout"] == 120.0
    client.close()
    assert sdk.closed is True


def test_create_session_success(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    sdk.post_result = _FakeResponse({"id": "ses_abc"})
    assert client.create_session("title") == "ses_abc"
    assert "directory=%2Ftmp%2Fmy%20dir" in sdk.post_calls[-1][0]
    assert sdk.post_calls[-1][1] == {"title": "title"}


def test_create_session_api_error(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    sdk.post_result = _APIError("boom")
    with pytest.raises(op_client.OpencodeSDKError, match="cannot create opencode session"):
        client.create_session("title")


def test_create_session_invalid_json(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    sdk.post_result = _FakeResponse({}, json_raises=True)
    with pytest.raises(op_client.OpencodeSDKError, match="invalid create-session response"):
        client.create_session("title")


def test_create_session_invalid_payload_shapes(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    sdk.post_result = _FakeResponse([])
    with pytest.raises(op_client.OpencodeSDKError, match="invalid create-session response"):
        client.create_session("title")

    sdk.post_result = _FakeResponse({"id": ""})
    with pytest.raises(op_client.OpencodeSDKError, match="invalid session id"):
        client.create_session("title")


def test_prompt_structured_success(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    sdk.post_result = _FakeResponse({"info": {"structured": {"ok": True}}})
    result = client.prompt_structured("ses_1", "ecoacher", "hello", {"type": "object"})
    assert result == {"ok": True}
    assert "/session/ses_1/message" in sdk.post_calls[-1][0]
    assert sdk.post_calls[-1][1]["agent"] == "ecoacher"


def test_prompt_structured_errors(monkeypatch):
    client, sdk = _make_client(monkeypatch)

    sdk.post_result = _APIError("x")
    with pytest.raises(op_client.OpencodeSDKError, match="opencode request failed"):
        client.prompt_structured("ses", "a", "p", {})

    sdk.post_result = _FakeResponse({}, json_raises=True)
    with pytest.raises(op_client.OpencodeSDKError, match="invalid JSON"):
        client.prompt_structured("ses", "a", "p", {})

    sdk.post_result = _FakeResponse([])
    with pytest.raises(op_client.OpencodeSDKError, match="unexpected response shape"):
        client.prompt_structured("ses", "a", "p", {})

    sdk.post_result = _FakeResponse({"info": {"structured": "nope"}})
    with pytest.raises(op_client.OpencodeSDKError, match="does not contain structured output"):
        client.prompt_structured("ses", "a", "p", {})


def test_delete_session_success_and_error(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    client.delete_session("ses_1")
    assert "/session/ses_1?directory=" in sdk.delete_calls[-1]

    sdk.delete_error = _APIError("delete")
    with pytest.raises(op_client.OpencodeSDKError, match="cannot delete opencode session"):
        client.delete_session("ses_1")


def test_ping_status_and_api_error(monkeypatch):
    client, sdk = _make_client(monkeypatch)
    sdk.get_result = _FakeResponse({}, status_code=204)
    assert client.ping() is True

    sdk.get_result = _FakeResponse({}, status_code=503)
    assert client.ping() is False

    sdk.get_result = _APIError("network")
    assert client.ping() is False
