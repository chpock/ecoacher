import difflib
import html
import re


def build_word_diff_html(original_text: str, corrected_text: str) -> str:
    if not corrected_text:
        return ""

    token_pattern = re.compile(r"\w+|[^\w\s]+|\s+", flags=re.UNICODE)
    word_pattern = re.compile(r"\w+", flags=re.UNICODE)

    original_tokens = token_pattern.findall(original_text)
    corrected_tokens = token_pattern.findall(corrected_text)
    original_words = [token for token in original_tokens if word_pattern.fullmatch(token)]
    corrected_words = [token for token in corrected_tokens if word_pattern.fullmatch(token)]

    highlighted_word_indices: set[int] = set()
    matcher = difflib.SequenceMatcher(a=original_words, b=corrected_words, autojunk=False)
    for opcode, _i1, _i2, j1, j2 in matcher.get_opcodes():
        if opcode in ("insert", "replace"):
            highlighted_word_indices.update(range(j1, j2))

    parts: list[str] = []
    corrected_word_index = 0
    for token in corrected_tokens:
        escaped = html.escape(token)
        if not word_pattern.fullmatch(token):
            parts.append(escaped)
            continue

        if corrected_word_index in highlighted_word_indices:
            parts.append(f"<span style='color:#1b8f3a'>{escaped}</span>")
        else:
            parts.append(escaped)
        corrected_word_index += 1

    return "<div style='white-space: pre-wrap;'>" + "".join(parts) + "</div>"
