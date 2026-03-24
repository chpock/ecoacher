from ecoacher.text.diff import build_word_diff_html


def test_build_word_diff_html_returns_empty_when_no_corrected_text() -> None:
    assert build_word_diff_html("source", "") == ""


def test_build_word_diff_html_highlights_inserted_or_replaced_words() -> None:
    html = build_word_diff_html("I has a apple.", "I have an apple.")

    assert "I" in html
    assert "apple" in html
    assert "<span style='color:#1b8f3a'>have</span>" in html
    assert "<span style='color:#1b8f3a'>an</span>" in html
