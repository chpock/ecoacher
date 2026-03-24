import logging
import re
from typing import Any

import language_tool_python
import shiboken6
from PySide6.QtCore import QObject, QThread, QTimer, Signal, Slot
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat, QTextDocument
from PySide6.QtQml import QQmlProperty
from PySide6.QtQuick import QQuickTextDocument


logger = logging.getLogger(__name__)

_WORD_RE = re.compile(r"\b[\w']+\b", flags=re.UNICODE)
MAX_SPELLCHECK_TEXT_LENGTH = 1024
MAX_SUGGESTIONS_PER_WORD = 10
SPELLCHECK_DEBOUNCE_MS = 300
DISABLED_LANGUAGE_TOOL_RULE_IDS = ("UPPERCASE_SENTENCE_START",)


def _merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    if not spans:
        return []

    ordered = sorted(spans, key=lambda item: item[0])
    merged: list[tuple[int, int]] = []
    current_start, current_length = ordered[0]
    current_end = current_start + current_length

    for start, length in ordered[1:]:
        end = start + length
        if start <= current_end:
            current_end = max(current_end, end)
            continue

        merged.append((current_start, current_end - current_start))
        current_start = start
        current_end = end

    merged.append((current_start, current_end - current_start))
    return merged


def _extract_spans(text: str, matches: Any) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for match in matches:
        issue_type = str(
            getattr(match, "rule_issue_type", getattr(match, "ruleIssueType", "")) or ""
        ).lower()
        if issue_type and issue_type != "misspelling":
            continue

        offset = int(getattr(match, "offset", 0) or 0)
        length = int(
            getattr(match, "error_length", getattr(match, "errorLength", 0)) or 0
        )
        if length <= 0:
            continue

        segment = text[offset : offset + length]
        found_word = False
        for word_match in _WORD_RE.finditer(segment):
            found_word = True
            spans.append((offset + word_match.start(), word_match.end() - word_match.start()))

        if not found_word:
            spans.append((offset, length))

    return _merge_spans(spans)


class _SpellCheckHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument) -> None:
        super().__init__(document)
        self._spans: list[tuple[int, int]] = []
        self._format = QTextCharFormat()
        self._format.setUnderlineStyle(QTextCharFormat.SingleUnderline)
        self._format.setUnderlineColor(QColor("#d32f2f"))
        self._format.setFontUnderline(True)
        self._format.setForeground(QColor("#b71c1c"))

    def set_spans(self, spans: list[tuple[int, int]]) -> None:
        self._spans = spans
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:
        block_start = self.currentBlock().position()
        block_end = block_start + len(text)

        for start, length in self._spans:
            end = start + length
            if end <= block_start or start >= block_end:
                continue

            highlight_start = max(start, block_start)
            highlight_end = min(end, block_end)
            self.setFormat(
                highlight_start - block_start,
                highlight_end - highlight_start,
                self._format,
            )


class _SpellCheckWorker(QObject):
    completed = Signal(str, list, list)
    failed = Signal(str, str)
    warmedUp = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._tool: Any = None
        self._tool_failed = False

    def _create_tool(self) -> Any:
        return language_tool_python.LanguageTool(
            "en-US",
            config={
                "maxSpellingSuggestions": MAX_SUGGESTIONS_PER_WORD,
                "disabledRuleIds": ",".join(DISABLED_LANGUAGE_TOOL_RULE_IDS),
            },
        )

    @Slot()
    def warmup(self) -> None:
        if self._tool_failed:
            return

        if self._tool is None:
            try:
                self._tool = self._create_tool()
                logger.info("Spell-check language tool initialized during warmup")
            except Exception as exc:  # noqa: BLE001
                self._tool_failed = True
                logger.warning("Spell checker warmup failed: cannot start language tool (%s)", exc)
                return

        try:
            self._tool.check("warmup")
            logger.debug("Spell-check warmup request completed")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Spell checker warmup request failed: %s", exc)

        self.warmedUp.emit()

    @Slot(str)
    def check_text(self, text: str) -> None:
        logger.debug("Spell-check worker started (%d chars)", len(text))
        if self._tool_failed:
            self.failed.emit(text, "language tool unavailable")
            return

        if self._tool is None:
            try:
                self._tool = self._create_tool()
            except Exception as exc:  # noqa: BLE001
                self._tool_failed = True
                self.failed.emit(text, f"cannot start language tool ({exc})")
                return

        try:
            matches = self._tool.check(text)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(text, f"spell checker request failed: {exc}")
            return

        logger.debug("Spell-check worker completed (%d matches)", len(matches))
        entries: list[dict[str, Any]] = []
        for index, match in enumerate(matches, start=1):
            issue_type = str(
                getattr(match, "rule_issue_type", getattr(match, "ruleIssueType", "")) or ""
            )
            rule_id = str(getattr(match, "rule_id", getattr(match, "ruleId", "")) or "")
            offset = int(getattr(match, "offset", 0) or 0)
            length = int(
                getattr(match, "error_length", getattr(match, "errorLength", 0)) or 0
            )
            context = str(getattr(match, "context", "") or "")
            replacements = getattr(match, "replacements", []) or []
            replacements_preview = ", ".join(str(item) for item in replacements[:3])
            logger.debug(
                "Spell-check match %d: type=%s rule=%s offset=%d length=%d context=%r replacements=%r",
                index,
                issue_type,
                rule_id,
                offset,
                length,
                context,
                replacements_preview,
            )
            if issue_type.lower() == "misspelling" and length > 0:
                entries.append(
                    {
                        "start": offset,
                        "length": length,
                        "replacements": [
                            str(item)
                            for item in replacements[:MAX_SUGGESTIONS_PER_WORD]
                        ],
                    }
                )

        self.completed.emit(text, _extract_spans(text, matches), entries)

    @Slot()
    def close_tool(self) -> None:
        if self._tool is not None:
            try:
                self._tool.close()
            except Exception:  # noqa: BLE001
                pass
            self._tool = None


class SpellCheckManager(QObject):
    requestCheck = Signal(str)
    closeWorker = Signal()
    warmupWorker = Signal()

    def __init__(self, root_window: QObject) -> None:
        super().__init__(root_window)
        self._input_text_area = root_window.findChild(QObject, "inputTextArea")
        self._highlighter: _SpellCheckHighlighter | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SPELLCHECK_DEBOUNCE_MS)
        self._timer.timeout.connect(self._schedule_current_text)
        self._enabled = False

        self._active_text: str | None = None
        self._pending_text: str | None = None
        self._last_checked_text = ""
        self._last_observed_text: str | None = None
        self._latest_entries: list[dict[str, Any]] = []
        self._current_spans: list[tuple[int, int]] = []
        self._suspend_text_change_handling = False

        self._worker_thread = QThread(self)
        self._worker = _SpellCheckWorker()
        self._worker.moveToThread(self._worker_thread)
        self.requestCheck.connect(self._worker.check_text)
        self.closeWorker.connect(self._worker.close_tool)
        self.warmupWorker.connect(self._worker.warmup)
        self._worker.completed.connect(self._on_worker_completed)
        self._worker.failed.connect(self._on_worker_failed)
        self._worker.warmedUp.connect(self._on_worker_warmed_up)
        self._worker_thread.start()
        logger.debug("Spell-check worker thread started")
        self.warmupWorker.emit()

        if self._input_text_area is None:
            logger.warning("Spell checker disabled: inputTextArea not found")
            return

        try:
            quick_text_document_obj = QQmlProperty.read(self._input_text_area, "textDocument")
            if quick_text_document_obj is None:
                logger.warning("Spell checker disabled: input textDocument object unavailable")
                return

            ptr = shiboken6.getCppPointer(quick_text_document_obj)[0]
            quick_text_document = shiboken6.wrapInstance(ptr, QQuickTextDocument)
            if quick_text_document is None:
                logger.warning("Spell checker disabled: cannot wrap QQuickTextDocument")
                return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Spell checker disabled: cannot access QQuickTextDocument (%s)", exc)
            return

        document = quick_text_document.textDocument()
        if document is None:
            logger.warning("Spell checker disabled: QTextDocument is unavailable")
            return

        self._highlighter = _SpellCheckHighlighter(document)
        self._input_text_area.textChanged.connect(self._on_input_text_changed)
        self._enabled = True
        self._on_input_text_changed()
        logger.info("English spell checker initialized")

    def close(self) -> None:
        self._timer.stop()
        self._enabled = False
        self.closeWorker.emit()
        self._worker_thread.quit()
        self._worker_thread.wait(3000)

    def _on_input_text_changed(self) -> None:
        if not self._enabled:
            return

        if self._suspend_text_change_handling:
            logger.debug("Spell-check textChanged ignored during span update")
            return

        if self._input_text_area is None:
            return

        text = self._input_text_area.property("text")
        if not isinstance(text, str):
            return

        if text == self._last_observed_text:
            return

        previous_text = self._last_observed_text
        self._last_observed_text = text
        if previous_text is not None:
            self._apply_local_edit_cleanup(previous_text, text)

        logger.debug("Spell-check timer scheduled")
        self._timer.start()

    def _schedule_current_text(self) -> None:
        if not self._enabled or self._highlighter is None or self._input_text_area is None:
            return

        text = self._input_text_area.property("text")
        if not isinstance(text, str):
            return

        if not text.strip():
            self._active_text = None
            self._pending_text = None
            self._last_checked_text = text
            self._latest_entries = []
            self._current_spans = []
            self._set_spans([])
            logger.debug("Spell-check skipped: empty input")
            return

        if len(text) > MAX_SPELLCHECK_TEXT_LENGTH:
            logger.debug(
                "Skipping spell check for long input (%d > %d)",
                len(text),
                MAX_SPELLCHECK_TEXT_LENGTH,
            )
            self._active_text = None
            self._pending_text = None
            self._last_checked_text = text
            self._latest_entries = []
            self._current_spans = []
            self._set_spans([])
            return

        if self._active_text is not None:
            self._pending_text = text
            logger.debug("Spell-check queued while previous request is in flight")
            return

        if text == self._last_checked_text:
            logger.debug("Spell-check skipped: text unchanged")
            return

        self._active_text = text
        logger.debug("Spell-check request emitted (%d chars)", len(text))
        self.requestCheck.emit(text)

    @Slot(str, list, list)
    def _on_worker_completed(
        self,
        text: str,
        spans: list[tuple[int, int]],
        entries: list[dict[str, Any]],
    ) -> None:
        if not self._enabled or self._highlighter is None or self._input_text_area is None:
            self._active_text = None
            self._pending_text = None
            return

        current_text = self._input_text_area.property("text")
        if isinstance(current_text, str) and current_text == text:
            self._set_spans(spans)
            self._last_checked_text = text
            self._latest_entries = entries
            self._current_spans = spans
            logger.debug("Spell-check highlights applied (%d spans)", len(spans))
        else:
            logger.debug("Spell-check result ignored: input changed during check")

        self._active_text = None
        if self._pending_text is not None:
            pending = self._pending_text
            self._pending_text = None
            if pending != self._last_checked_text:
                self._active_text = pending
                self.requestCheck.emit(pending)

    @Slot(str, str)
    def _on_worker_failed(self, text: str, error_message: str) -> None:
        logger.warning("%s", error_message)
        if self._highlighter is not None and self._input_text_area is not None:
            current_text = self._input_text_area.property("text")
            if isinstance(current_text, str) and current_text == text:
                self._set_spans([])
                self._latest_entries = []
                self._current_spans = []

        self._active_text = None
        if self._pending_text is not None:
            pending = self._pending_text
            self._pending_text = None
            self._active_text = pending
            self.requestCheck.emit(pending)

    @Slot()
    def _on_worker_warmed_up(self) -> None:
        logger.debug("Spell-check worker warmup signal received")

    def _apply_local_edit_cleanup(self, old_text: str, new_text: str) -> None:
        if self._highlighter is None:
            return

        if old_text == new_text:
            return

        prefix = 0
        max_prefix = min(len(old_text), len(new_text))
        while prefix < max_prefix and old_text[prefix] == new_text[prefix]:
            prefix += 1

        old_suffix = len(old_text)
        new_suffix = len(new_text)
        while old_suffix > prefix and new_suffix > prefix and old_text[old_suffix - 1] == new_text[new_suffix - 1]:
            old_suffix -= 1
            new_suffix -= 1

        old_edit_start = prefix
        old_edit_end = old_suffix
        insertion_only = old_edit_start == old_edit_end
        delta = (new_suffix - prefix) - (old_suffix - prefix)

        updated_spans: list[tuple[int, int]] = []
        for start, length in self._current_spans:
            end = start + length

            is_before_edit = end < old_edit_start or (end == old_edit_start and not insertion_only)
            if is_before_edit:
                updated_spans.append((start, length))
                continue

            is_after_edit = start > old_edit_end or (start == old_edit_end and not insertion_only)
            if is_after_edit:
                updated_spans.append((start + delta, length))
                continue

        updated_entries: list[dict[str, Any]] = []
        for entry in self._latest_entries:
            start = int(entry.get("start", -1))
            length = int(entry.get("length", 0))
            if length <= 0:
                continue
            end = start + length

            is_before_edit = end < old_edit_start or (end == old_edit_start and not insertion_only)
            if is_before_edit:
                updated_entries.append(dict(entry))
                continue

            is_after_edit = start > old_edit_end or (start == old_edit_end and not insertion_only)
            if is_after_edit:
                shifted = dict(entry)
                shifted["start"] = start + delta
                updated_entries.append(shifted)
                continue

        if updated_spans != self._current_spans:
            logger.debug("Spell-check spans updated after local edit (%d -> %d)", len(self._current_spans), len(updated_spans))
            self._current_spans = updated_spans
            self._set_spans(updated_spans)

        self._latest_entries = updated_entries

    def _set_spans(self, spans: list[tuple[int, int]]) -> None:
        if self._highlighter is None:
            return

        self._suspend_text_change_handling = True
        try:
            self._highlighter.set_spans(spans)
        finally:
            self._suspend_text_change_handling = False

    def get_suggestions_at(self, position: int) -> list[str]:
        if position < 0:
            return []

        for entry in self._latest_entries:
            start = int(entry.get("start", -1))
            length = int(entry.get("length", 0))
            if length <= 0:
                continue
            if start <= position < start + length:
                replacements = entry.get("replacements", [])
                if isinstance(replacements, list):
                    return [str(item) for item in replacements if str(item)]

        return []

    def has_suggestions_at(self, position: int) -> bool:
        if position < 0:
            return False

        for entry in self._latest_entries:
            start = int(entry.get("start", -1))
            length = int(entry.get("length", 0))
            if length <= 0:
                continue
            if start <= position < start + length:
                replacements = entry.get("replacements", [])
                if isinstance(replacements, list) and len(replacements) > 0:
                    return True

        return False

    def apply_replacement_at(self, position: int, replacement: str) -> bool:
        if self._input_text_area is None or position < 0 or not replacement:
            return False

        text = self._input_text_area.property("text")
        if not isinstance(text, str):
            return False

        for entry in self._latest_entries:
            start = int(entry.get("start", -1))
            length = int(entry.get("length", 0))
            if length <= 0:
                continue
            if not (start <= position < start + length):
                continue

            new_text = text[:start] + replacement + text[start + length :]
            self._input_text_area.setProperty("text", new_text)

            new_cursor_position = start + len(replacement)
            self._input_text_area.setProperty("cursorPosition", new_cursor_position)

            delta = len(replacement) - length
            updated_entries: list[dict[str, Any]] = []
            for other in self._latest_entries:
                other_start = int(other.get("start", -1))
                other_length = int(other.get("length", 0))
                if other_length <= 0:
                    continue
                if other_start == start and other_length == length:
                    continue
                if other_start >= start + length:
                    shifted = dict(other)
                    shifted["start"] = other_start + delta
                    updated_entries.append(shifted)
                    continue

                updated_entries.append(dict(other))

            self._latest_entries = updated_entries

            self._current_spans = self._recompute_spans_after_replacement(start, length, delta)
            if self._highlighter is not None:
                self._highlighter.set_spans(self._current_spans)

            logger.debug(
                "Spell-check replacement applied at %d length %d -> %r",
                start,
                length,
                replacement,
            )
            return True

        return False

    def _recompute_spans_after_replacement(
        self,
        replaced_start: int,
        replaced_length: int,
        delta: int,
    ) -> list[tuple[int, int]]:
        replaced_end = replaced_start + replaced_length
        updated: list[tuple[int, int]] = []

        for start, length in self._current_spans:
            end = start + length

            if end <= replaced_start:
                updated.append((start, length))
                continue

            if start >= replaced_end:
                updated.append((start + delta, length))
                continue

        return updated
