from ecoacher.spellcheck import manager as spell_manager


class _FakeMatch:
    def __init__(self, issue_type, offset, length, replacements=None, context="", rule_id="rule"):
        self.rule_issue_type = issue_type
        self.offset = offset
        self.error_length = length
        self.replacements = replacements or []
        self.context = context
        self.rule_id = rule_id


class _FakeTool:
    def __init__(self, matches=None, check_error=None):
        self.matches = matches or []
        self.check_error = check_error
        self.closed = False

    def check(self, _text):
        if self.check_error is not None:
            raise self.check_error
        return self.matches

    def close(self):
        self.closed = True


class _FakeHighlighter:
    def __init__(self):
        self.spans = []

    def set_spans(self, spans):
        self.spans = list(spans)


class _FakeTextArea:
    def __init__(self, text):
        self.values = {"text": text, "cursorPosition": 0}

    def property(self, key):
        return self.values.get(key)

    def setProperty(self, key, value):
        self.values[key] = value


def test_merge_spans_and_extract_spans():
    assert spell_manager._merge_spans([]) == []
    assert spell_manager._merge_spans([(0, 2), (2, 3), (10, 1)]) == [(0, 5), (10, 1)]

    text = "bad-word"
    matches = [
        _FakeMatch("misspelling", 0, 3),
        _FakeMatch("grammar", 4, 4),
        _FakeMatch("misspelling", 4, 4),
    ]
    spans = spell_manager._extract_spans(text, matches)
    assert spans == [(0, 3), (4, 4)]


def test_spellcheck_worker_warmup_and_check_paths(monkeypatch):
    worker = spell_manager._SpellCheckWorker()
    tool = _FakeTool(matches=[_FakeMatch("misspelling", 0, 4, ["good"])])
    monkeypatch.setattr(worker, "_create_tool", lambda: tool)

    warmed = []
    completed = []
    failed = []
    worker.warmedUp.connect(lambda: warmed.append(True))
    worker.completed.connect(lambda a, b, c: completed.append((a, b, c)))
    worker.failed.connect(lambda a, b: failed.append((a, b)))

    worker.warmup()
    worker.check_text("tezt")
    worker.close_tool()

    assert warmed == [True]
    assert completed and completed[0][0] == "tezt"
    assert completed[0][2][0]["replacements"] == ["good"]
    assert failed == []
    assert tool.closed is True


def test_spellcheck_worker_failure_paths(monkeypatch):
    worker = spell_manager._SpellCheckWorker()
    monkeypatch.setattr(worker, "_create_tool", lambda: (_ for _ in ()).throw(RuntimeError("no tool")))
    failed = []
    worker.failed.connect(lambda text, message: failed.append((text, message)))
    worker.check_text("abc")
    assert "cannot start language tool" in failed[0][1]

    worker = spell_manager._SpellCheckWorker()
    monkeypatch.setattr(worker, "_create_tool", lambda: _FakeTool(check_error=RuntimeError("boom")))
    failed = []
    worker.failed.connect(lambda text, message: failed.append((text, message)))
    worker.check_text("abc")
    assert failed == [("abc", "spell checker request failed: boom")]


def _make_manager_for_logic(text="speling test"):
    manager = spell_manager.SpellCheckManager.__new__(spell_manager.SpellCheckManager)
    manager._input_text_area = _FakeTextArea(text)
    manager._highlighter = _FakeHighlighter()
    manager._latest_entries = []
    manager._current_spans = []
    manager._suspend_text_change_handling = False
    manager._enabled = True
    manager._active_text = None
    manager._pending_text = None
    manager._last_checked_text = ""
    manager._last_observed_text = text
    return manager


def test_suggestions_and_replacements_logic():
    manager = _make_manager_for_logic("speling test")
    manager._latest_entries = [{"start": 0, "length": 7, "replacements": ["spelling", "spieling"]}]
    manager._current_spans = [(0, 7)]

    assert manager.get_suggestions_at(-1) == []
    assert manager.has_suggestions_at(-1) is False
    assert manager.has_suggestions_at(1) is True
    assert manager.get_suggestions_at(1) == ["spelling", "spieling"]

    assert manager.apply_replacement_at(1, "spelling") is True
    assert manager._input_text_area.property("text") == "spelling test"
    assert manager._input_text_area.property("cursorPosition") == len("spelling")
    assert manager._latest_entries == []
    assert manager._highlighter.spans == []


def test_apply_replacement_invalid_inputs():
    manager = _make_manager_for_logic("abc")
    manager._latest_entries = [{"start": 0, "length": 1, "replacements": ["x"]}]
    assert manager.apply_replacement_at(-1, "x") is False
    assert manager.apply_replacement_at(0, "") is False


def test_local_edit_cleanup_and_span_updates():
    manager = _make_manager_for_logic("abcdef")
    manager._current_spans = [(0, 2), (4, 2)]
    manager._latest_entries = [
        {"start": 0, "length": 2, "replacements": ["ab"]},
        {"start": 4, "length": 2, "replacements": ["ef"]},
    ]

    manager._apply_local_edit_cleanup("abcdef", "abcXYZdef")
    assert manager._current_spans[0] == (0, 2)
    assert manager._latest_entries[0]["start"] == 0


def test_set_spans_guard_and_recompute():
    manager = _make_manager_for_logic("abc")
    manager._set_spans([(1, 1)])
    assert manager._highlighter.spans == [(1, 1)]
    assert manager._suspend_text_change_handling is False

    manager._current_spans = [(0, 2), (5, 1), (2, 2)]
    shifted = manager._recompute_spans_after_replacement(2, 2, 3)
    assert shifted == [(0, 2), (8, 1)]
