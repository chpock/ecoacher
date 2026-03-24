from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import httpx
import opencode_ai
from opencode_ai import Opencode


class OpencodeSDKError(RuntimeError):
    pass


@dataclass
class OpencodeClient:
    base_url: str
    directory: str
    timeout_seconds: float = 120.0
    _client: Opencode = field(init=False)

    def __post_init__(self) -> None:
        self._client = Opencode(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
        )

    def close(self) -> None:
        self._client.close()

    def create_session(self, title: str) -> str:
        try:
            response = self._client.post(
                f"/session?directory={quote(self.directory, safe='')}",
                cast_to=httpx.Response,
                body={"title": title},
            )
            payload = response.json()
        except opencode_ai.APIError as exc:
            raise OpencodeSDKError(f"cannot create opencode session: {exc}") from exc
        except ValueError as exc:
            raise OpencodeSDKError("invalid create-session response from opencode") from exc

        if not isinstance(payload, dict):
            raise OpencodeSDKError("invalid create-session response from opencode")

        session_id = payload.get("id", "")
        if not session_id:
            raise OpencodeSDKError("invalid session id returned by opencode")

        return session_id

    def prompt_structured(
        self,
        session_id: str,
        agent: str,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        body = {
            "agent": agent,
            "parts": [{"type": "text", "text": prompt}],
            "format": {
                "type": "json_schema",
                "schema": schema,
            },
        }

        try:
            response = self._client.post(
                f"/session/{session_id}/message?directory={quote(self.directory, safe='')}",
                cast_to=httpx.Response,
                body=body,
            )
            payload = response.json()
        except opencode_ai.APIError as exc:
            raise OpencodeSDKError(f"opencode request failed: {exc}") from exc
        except ValueError as exc:
            raise OpencodeSDKError("opencode returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise OpencodeSDKError("opencode returned unexpected response shape")

        info = payload.get("info", {})
        structured = info.get("structured")
        if not isinstance(structured, dict):
            raise OpencodeSDKError("opencode response does not contain structured output")

        return structured

    def delete_session(self, session_id: str) -> None:
        try:
            self._client.delete(
                f"/session/{session_id}?directory={quote(self.directory, safe='')}",
                cast_to=httpx.Response,
            )
        except opencode_ai.APIError as exc:
            raise OpencodeSDKError(f"cannot delete opencode session: {exc}") from exc

    def ping(self) -> bool:
        try:
            response = self._client.get(
                f"/session?directory={quote(self.directory, safe='')}&limit=1",
                cast_to=httpx.Response,
            )
        except opencode_ai.APIError:
            return False

        return 200 <= response.status_code < 300
