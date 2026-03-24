from ecoacher.opencode.client import OpencodeSDKError
from ecoacher.opencode.request import CheckWorker


class _FakeClient:
    def __init__(self):
        self.create_session_result = "ses_1"
        self.prompt_result = {
            "corrected_phrase": "Fixed",
            "summary_ru": "Summary",
            "corrections": [],
        }
        self.delete_error = None
        self.deleted = []

    def create_session(self, title: str) -> str:
        if isinstance(self.create_session_result, Exception):
            raise self.create_session_result
        return self.create_session_result

    def prompt_structured(self, session_id: str, agent: str, prompt: str, schema: dict):
        if isinstance(self.prompt_result, Exception):
            raise self.prompt_result
        return self.prompt_result

    def delete_session(self, session_id: str) -> None:
        self.deleted.append(session_id)
        if self.delete_error is not None:
            raise self.delete_error


def test_format_corrections_handles_invalid_or_empty():
    worker = CheckWorker(_FakeClient(), "text")
    assert worker._format_corrections(None) == ""
    assert worker._format_corrections([]) == ""
    assert worker._format_corrections(["x"]) == ""


def test_format_corrections_builds_rich_html():
    worker = CheckWorker(_FakeClient(), "text")
    html = worker._format_corrections(
        [
            {
                "original_fragment": "bad <tag>",
                "corrected_fragment": "good & fine",
                "category": "Grammar",
                "explanation_ru": "Use correct form",
            }
        ]
    )
    assert "<b>1. Grammar</b>" in html
    assert "bad &lt;tag&gt;" in html
    assert "good &amp; fine" in html
    assert "Пояснение:" in html


def test_check_worker_success_emits_signals():
    client = _FakeClient()
    client.prompt_result = {
        "corrected_phrase": "Fixed phrase",
        "summary_ru": "Кратко",
        "corrections": [
            {
                "original_fragment": "a",
                "corrected_fragment": "b",
                "category": "Word choice",
                "explanation_ru": "explain",
            }
        ],
    }
    worker = CheckWorker(client, "input")
    statuses = []
    failures = []
    successes = []
    worker.statusChanged.connect(statuses.append)
    worker.failed.connect(failures.append)
    worker.success.connect(lambda a, b, c: successes.append((a, b, c)))

    worker.run()

    assert failures == []
    assert successes
    corrected, summary, corrections_html = successes[0]
    assert corrected == "Fixed phrase"
    assert summary == "Кратко"
    assert "Word choice" in corrections_html
    assert statuses[:3] == ["create session", "send request", "waiting for response"]
    assert statuses[-2:] == ["cleanup session", "session cleaned"]
    assert client.deleted == ["ses_1"]


def test_check_worker_handles_sdk_error_and_generic_error():
    client = _FakeClient()
    client.create_session_result = OpencodeSDKError("cannot create")
    worker = CheckWorker(client, "input")
    failures = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures == ["cannot create"]

    client = _FakeClient()
    client.prompt_result = RuntimeError("boom")
    worker = CheckWorker(client, "input")
    failures = []
    worker.failed.connect(failures.append)
    worker.run()
    assert failures and failures[0].startswith("unexpected check error: boom")


def test_check_worker_cleanup_error_is_reported():
    client = _FakeClient()
    client.delete_error = OpencodeSDKError("cleanup failed")
    worker = CheckWorker(client, "input")
    statuses = []
    failures = []
    worker.statusChanged.connect(statuses.append)
    worker.failed.connect(failures.append)

    worker.run()

    assert "cleanup session" in statuses
    assert "session cleanup failed" in statuses
    assert failures == ["cleanup failed"]
