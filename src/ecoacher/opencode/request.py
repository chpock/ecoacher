import html
from typing import Any

from PySide6.QtCore import QThread, Signal

from ..config.constants import CHECK_SCHEMA
from .client import OpencodeClient, OpencodeSDKError


class CheckWorker(QThread):
    statusChanged = Signal(str)
    success = Signal(str, str, str, str)
    failed = Signal(str)

    def __init__(self, client: OpencodeClient, input_text: str) -> None:
        super().__init__()
        self._client = client
        self._input_text = input_text

    def run(self) -> None:
        session_id: str | None = None
        corrected = ""
        understood_meaning_ru = ""
        summary_ru = ""
        corrections_text = ""
        error_message: str | None = None

        try:
            self.statusChanged.emit("create session")
            session_id = self._client.create_session(title="ecoacher-check")

            self.statusChanged.emit("send request")
            prompt = f"Process this text:\n\n{self._input_text}"

            self.statusChanged.emit("waiting for response")
            structured = self._client.prompt_structured(
                session_id=session_id,
                agent="ecoacher",
                prompt=prompt,
                schema=CHECK_SCHEMA,
            )

            corrected = str(structured.get("corrected_phrase", "")).strip()
            understood_meaning_ru = str(structured.get("understood_meaning_ru", "")).strip()
            summary_ru = str(structured.get("summary_ru", "")).strip()
            corrections_text = self._format_corrections(structured.get("corrections", []))
        except OpencodeSDKError as exc:
            error_message = str(exc)
        except Exception as exc:  # noqa: BLE001
            error_message = f"unexpected check error: {exc}"

        if session_id is not None:
            self.statusChanged.emit("cleanup session")
            try:
                self._client.delete_session(session_id)
                self.statusChanged.emit("session cleaned")
            except OpencodeSDKError as exc:
                cleanup_error = str(exc)
                self.statusChanged.emit("session cleanup failed")
                if error_message is None:
                    error_message = cleanup_error
                else:
                    error_message = f"{error_message}; {cleanup_error}"

        if error_message is not None:
            self.failed.emit(error_message)
            return

        self.success.emit(corrected, understood_meaning_ru, summary_ru, corrections_text)

    def _format_corrections(self, corrections: Any) -> str:
        if not isinstance(corrections, list) or not corrections:
            return ""

        blocks: list[str] = []
        for index, item in enumerate(corrections, start=1):
            if not isinstance(item, dict):
                continue

            original_fragment = str(item.get("original_fragment", "")).strip()
            corrected_fragment = str(item.get("corrected_fragment", "")).strip()
            category = str(item.get("category", "")).strip()
            explanation_ru = str(item.get("explanation_ru", "")).strip()

            title = html.escape(f"{index}. {category}" if category else f"{index}. Correction")
            item_lines: list[str] = [f"<b>{title}</b>"]
            if original_fragment:
                item_lines.append(
                    "Исходный фрагмент: "
                    f"<span style='color:#c62828'>{html.escape(original_fragment)}</span>"
                )
            if corrected_fragment:
                item_lines.append(
                    "Исправленный фрагмент: "
                    f"<span style='color:#1b8f3a'>{html.escape(corrected_fragment)}</span>"
                )
            if explanation_ru:
                item_lines.append(f"Пояснение: {html.escape(explanation_ru)}")

            blocks.append("<br>".join(item_lines))

        return "<br><br>".join(blocks)
